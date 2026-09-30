#pragma once

#include "operator.hpp"
#include "pinning.hpp"
#include "worker.hpp"
#include "metrics.hpp"

#include <chrono>
#include <algorithm>
#include <condition_variable>
#include <cstdint>
#include <exception>
#include <memory>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <vector>

namespace klstream {

enum class RuntimeState : std::uint8_t {
    Created, Configured, Starting, Running, Draining,
    Completed, Failed, Cancelled, Stopped
};

struct OperatorRegistration {
    IOperator* op;
    CoreAffinity affinity;
    int worker_id;
};

struct TopologyNode {
    std::uint64_t id{0};
    std::string name;
    int worker_id{-1};
    CoreAffinity affinity{CoreAffinity::Any};
};

struct TopologyEdge {
    std::uint64_t from{0};
    std::uint64_t to{0};
    std::string queue_type;
    std::size_t capacity{0};
};

struct TopologyManifest {
    std::vector<TopologyNode> nodes;
    std::vector<TopologyEdge> edges;

    [[nodiscard]] bool validate(std::string* reason = nullptr) const {
        std::unordered_set<std::uint64_t> ids;
        std::unordered_set<std::string> names;
        for (const auto& node : nodes) {
            if (node.name.empty() || node.worker_id < 0 || !ids.insert(node.id).second ||
                !names.insert(node.name).second) {
                if (reason) *reason = "node id/name/worker invariant violated";
                return false;
            }
        }
        for (const auto& edge : edges) {
            if (!ids.count(edge.from) || !ids.count(edge.to) || edge.from == edge.to ||
                edge.queue_type.empty() || edge.capacity < 2) {
                if (reason) *reason = "edge endpoint/type/capacity invariant violated";
                return false;
            }
        }
        return true;
    }

    [[nodiscard]] std::string to_json() const {
        std::ostringstream out;
        out << "{\"schema_version\":\"bpfeat.topology.v1\",\"nodes\":[";
        for (std::size_t i = 0; i < nodes.size(); ++i) {
            if (i) out << ',';
            out << "{\"id\":" << nodes[i].id << ",\"name\":\"" << nodes[i].name
                << "\",\"worker_id\":" << nodes[i].worker_id << "}";
        }
        out << "],\"edges\":[";
        for (std::size_t i = 0; i < edges.size(); ++i) {
            if (i) out << ',';
            out << "{\"from\":" << edges[i].from << ",\"to\":" << edges[i].to
                << ",\"queue_type\":\"" << edges[i].queue_type
                << "\",\"capacity\":" << edges[i].capacity << "}";
        }
        out << "]}";
        return out.str();
    }
};

// Runtime is a one-shot coordinator with explicit terminal state. It owns
// worker threads but not operators; callers retain operator storage.
class Runtime {
public:
    Runtime() = default;
    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;

    int add_worker(CoreAffinity default_affinity = CoreAffinity::Any) {
        std::lock_guard<std::mutex> lock(mu_);
        ensure_configurable("add_worker");
        const int idx = static_cast<int>(workers_.size());
        workers_.emplace_back(std::make_unique<WorkerThread>());
        workers_.back()->set_affinity(default_affinity);
        state_ = RuntimeState::Configured;
        return idx;
    }

    void register_op(IOperator* op, int worker_id,
                     CoreAffinity affinity = CoreAffinity::Any) {
        if (op == nullptr) throw std::invalid_argument("Runtime::register_op: null operator");
        std::lock_guard<std::mutex> lock(mu_);
        ensure_configurable("register_op");
        if (worker_id < 0 || worker_id >= static_cast<int>(workers_.size()))
            throw std::out_of_range("Runtime::register_op: invalid worker_id " + std::to_string(worker_id));
        if (registered_ptrs_.count(op) != 0)
            throw std::logic_error("Runtime::register_op: operator pointer already registered");
        if (registered_names_.count(op->name()) != 0)
            throw std::logic_error("Runtime::register_op: duplicate operator name " + op->name());
        op->id = next_op_id_++;
        if (affinity != CoreAffinity::Any) workers_[worker_id]->set_affinity(affinity);
        workers_[worker_id]->assign(op);
        registered_ptrs_.insert(op);
        registered_names_.insert(op->name());
        registrations_.push_back({op, affinity, worker_id});
        state_ = RuntimeState::Configured;
    }

    MetricsReporter& metrics() { return reporter_; }
    AccountingLedger& accounting() { return ledger_; }
    [[nodiscard]] const AccountingLedger& accounting() const { return ledger_; }

    void start() {
        std::lock_guard<std::mutex> lock(mu_);
        if (started_) throw std::logic_error("Runtime::start() called twice");
        if (workers_.empty()) throw std::logic_error("Runtime::start(): no workers configured");
        started_ = true;
        completed_workers_ = 0;
        state_ = RuntimeState::Starting;
        reporter_.start();
        for (auto& worker : workers_) {
            worker->start(
                [this](WorkerThread& w, IOperator* op, std::exception_ptr ep) {
                    handle_failure(w, op, ep);
                },
                [this](WorkerThread& w) { handle_completion(w); },
                [this] { return cancellation_requested(); });
        }
        if (state_ == RuntimeState::Starting) state_ = RuntimeState::Running;
    }

    bool cancel() noexcept {
        std::vector<WorkerThread*> workers;
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (!started_ || is_terminal(state_)) return false;
            cancellation_requested_ = true;
            state_ = RuntimeState::Cancelled;
            for (auto& w : workers_) workers.push_back(w.get());
        }
        for (auto* w : workers) w->request_cancel();
        cv_.notify_all();
        return true;
    }

    bool request_cancel() noexcept { return cancel(); }

    template <typename Rep, typename Period>
    bool wait_for(std::chrono::duration<Rep, Period> duration) {
        std::unique_lock<std::mutex> lock(mu_);
        return cv_.wait_for(lock, duration, [this] { return is_terminal(state_); });
    }

    bool wait_until_terminal() {
        std::unique_lock<std::mutex> lock(mu_);
        cv_.wait(lock, [this] { return is_terminal(state_); });
        return true;
    }

    template <typename Rep, typename Period>
    bool wait_until_terminal_for(std::chrono::duration<Rep, Period> duration) {
        return wait_for(duration);
    }

    void stop() noexcept {
        std::vector<WorkerThread*> workers;
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (!started_) return;
            for (auto& w : workers_) workers.push_back(w.get());
        }
        for (auto* w : workers) w->stop();
        reporter_.stop();
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (!is_terminal(state_)) state_ = RuntimeState::Stopped;
            stopped_ = true;
        }
        cv_.notify_all();
    }

    [[nodiscard]] RuntimeState state() const noexcept {
        std::lock_guard<std::mutex> lock(mu_);
        return state_;
    }

    [[nodiscard]] static const char* state_name(RuntimeState s) noexcept {
        switch (s) {
            case RuntimeState::Created: return "Created";
            case RuntimeState::Configured: return "Configured";
            case RuntimeState::Starting: return "Starting";
            case RuntimeState::Running: return "Running";
            case RuntimeState::Draining: return "Draining";
            case RuntimeState::Completed: return "Completed";
            case RuntimeState::Failed: return "Failed";
            case RuntimeState::Cancelled: return "Cancelled";
            case RuntimeState::Stopped: return "Stopped";
        }
        return "Unknown";
    }

    [[nodiscard]] std::exception_ptr terminal_error() const noexcept {
        std::lock_guard<std::mutex> lock(mu_);
        return terminal_error_;
    }

    [[nodiscard]] std::size_t worker_count() const noexcept { return workers_.size(); }
    [[nodiscard]] std::size_t operator_count() const noexcept { return registrations_.size(); }
    [[nodiscard]] const std::vector<OperatorRegistration>& registrations() const noexcept { return registrations_; }

    void set_expected_topology(TopologyManifest manifest) {
        std::string reason;
        if (!manifest.validate(&reason)) throw std::invalid_argument("invalid topology: " + reason);
        std::lock_guard<std::mutex> lock(mu_);
        ensure_configurable("set_expected_topology");
        expected_topology_ = std::move(manifest);
    }

    [[nodiscard]] TopologyManifest observed_topology() const {
        std::lock_guard<std::mutex> lock(mu_);
        TopologyManifest result;
        for (const auto& reg : registrations_)
            result.nodes.push_back({reg.op->id, reg.op->name(), reg.worker_id, reg.affinity});
        return result;
    }

    [[nodiscard]] bool validate_topology(std::string* reason = nullptr) const {
        const auto observed = observed_topology();
        if (!observed.validate(reason)) return false;
        std::lock_guard<std::mutex> lock(mu_);
        if (expected_topology_.nodes.empty() && expected_topology_.edges.empty()) return true;
        if (observed.nodes.size() != expected_topology_.nodes.size()) {
            if (reason) *reason = "observed/expected node count differs";
            return false;
        }
        for (const auto& expected : expected_topology_.nodes) {
            auto it = std::find_if(observed.nodes.begin(), observed.nodes.end(),
                [&](const TopologyNode& n) { return n.id == expected.id; });
            if (it == observed.nodes.end() || it->name != expected.name ||
                it->worker_id != expected.worker_id) {
                if (reason) *reason = "observed node differs from expected manifest";
                return false;
            }
        }
        return true;
    }

    ~Runtime() { stop(); }

private:
    static bool is_terminal(RuntimeState s) noexcept {
        return s == RuntimeState::Completed || s == RuntimeState::Failed ||
               s == RuntimeState::Cancelled || s == RuntimeState::Stopped;
    }

    void ensure_configurable(const char* action) const {
        if (started_) throw std::logic_error(std::string("Runtime::") + action + " after start");
    }

    bool cancellation_requested() const noexcept {
        std::lock_guard<std::mutex> lock(mu_);
        return cancellation_requested_;
    }

    void handle_failure(WorkerThread& source, IOperator*, std::exception_ptr ep) noexcept {
        std::vector<WorkerThread*> peers;
        {
            std::lock_guard<std::mutex> lock(mu_);
            if (state_ == RuntimeState::Failed) return;
            if (state_ == RuntimeState::Completed || state_ == RuntimeState::Cancelled) return;
            state_ = RuntimeState::Failed;
            terminal_error_ = ep;
            for (auto& w : workers_) if (w.get() != &source) peers.push_back(w.get());
        }
        for (auto* w : peers) w->request_stop();
        cv_.notify_all();
    }

    void handle_completion(WorkerThread&) noexcept {
        {
            std::lock_guard<std::mutex> lock(mu_);
            ++completed_workers_;
            if (completed_workers_ >= workers_.size() && !is_terminal(state_))
                state_ = RuntimeState::Completed;
            else if (!is_terminal(state_)) state_ = RuntimeState::Draining;
        }
        cv_.notify_all();
    }

    mutable std::mutex mu_;
    std::condition_variable cv_;
    std::vector<std::unique_ptr<WorkerThread>> workers_;
    std::vector<OperatorRegistration> registrations_;
    std::unordered_set<IOperator*> registered_ptrs_;
    std::unordered_set<std::string> registered_names_;
    MetricsReporter reporter_;
    AccountingLedger ledger_;
    RuntimeState state_{RuntimeState::Created};
    std::exception_ptr terminal_error_;
    std::uint64_t next_op_id_{0};
    std::size_t completed_workers_{0};
    bool started_{false};
    bool stopped_{false};
    bool cancellation_requested_{false};
    TopologyManifest expected_topology_;
};

} // namespace klstream
