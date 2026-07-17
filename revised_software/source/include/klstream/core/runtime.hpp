// include/klstream/core/runtime.hpp
#pragma once
#include "operator.hpp"
#include "pinning.hpp"
#include "worker.hpp"
#include "metrics.hpp"
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>
#include <chrono>
#include <thread>
#include <atomic>

namespace klstream {

// ── OperatorRegistration ──────────────────────────────────────────────────
struct OperatorRegistration {
    IOperator*   op;
    CoreAffinity affinity;
    int          worker_id;
};

// ── Runtime ───────────────────────────────────────────────────────────────
//
// The top-level coordinator.
class Runtime {
public:
    int add_worker(CoreAffinity default_affinity = CoreAffinity::Any) {
        int idx = static_cast<int>(workers_.size());
        workers_.emplace_back(std::make_unique<WorkerThread>());
        workers_.back()->set_affinity(default_affinity);
        return idx;
    }

    void register_op(IOperator* op, int worker_id,
                     CoreAffinity affinity = CoreAffinity::Any)
    {
        if (worker_id < 0 ||
            worker_id >= static_cast<int>(workers_.size())) {
            throw std::out_of_range(
                "Runtime::register_op: invalid worker_id " +
                std::to_string(worker_id));
        }
        op->id = next_op_id_++;
        if (affinity != CoreAffinity::Any) {
            workers_[worker_id]->set_affinity(affinity);
        }
        workers_[worker_id]->assign(op);
    }

    MetricsReporter& metrics() { return reporter_; }

    void start() {
        if (started_) throw std::logic_error("Runtime::start() called twice");
        started_ = true;
        reporter_.start();
        for (auto& w : workers_) w->start();
    }

    template <typename Rep, typename Period>
    void wait_for(std::chrono::duration<Rep, Period> duration) {
        std::this_thread::sleep_for(duration);
    }

    // Block the calling thread until emitted count matches processed/written count.
    // This implements exact-count termination matching (INV-001).
    // Returns true if match is achieved, false if timeout occurs.
    bool wait_until_matched(const std::atomic<std::uint64_t>& emitted,
                            const std::atomic<std::uint64_t>& processed,
                            std::chrono::milliseconds poll_interval = std::chrono::milliseconds(5),
                            std::chrono::milliseconds timeout = std::chrono::seconds(10))
    {
        auto start_time = std::chrono::steady_clock::now();
        for (;;) {
            std::uint64_t em = emitted.load(std::memory_order_relaxed);
            std::uint64_t pr = processed.load(std::memory_order_relaxed);
            if (em > 0 && em == pr) {
                return true;
            }
            if (std::chrono::steady_clock::now() - start_time > timeout) {
                return false;
            }
            std::this_thread::sleep_for(poll_interval);
        }
    }

    void stop() {
        for (auto& w : workers_) w->stop();
        reporter_.stop();
    }

    ~Runtime() { if (started_) stop(); }

private:
    std::vector<std::unique_ptr<WorkerThread>> workers_;
    MetricsReporter                            reporter_;
    std::uint64_t                              next_op_id_{0};
    bool                                       started_{false};
};

} // namespace klstream
