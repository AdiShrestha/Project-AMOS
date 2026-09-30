#pragma once

#include "operator.hpp"
#include "pinning.hpp"
#include "config.hpp"

#include <atomic>
#include <chrono>
#include <exception>
#include <functional>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <vector>

namespace klstream {

// One worker owns a cooperative scheduling loop. Coordinator callbacks are
// non-blocking: they may update Runtime state but must never join this worker.
class WorkerThread {
public:
    using FailureHandler = std::function<void(WorkerThread&, IOperator*, std::exception_ptr)>;
    using CompletionHandler = std::function<void(WorkerThread&)>;
    using CancelQuery = std::function<bool()>;

    WorkerThread() = default;
    WorkerThread(const WorkerThread&) = delete;
    WorkerThread& operator=(const WorkerThread&) = delete;
    WorkerThread(WorkerThread&&) = delete;
    WorkerThread& operator=(WorkerThread&&) = delete;

    void assign(IOperator* op) {
        if (op == nullptr) throw std::invalid_argument("WorkerThread::assign: null operator");
        std::lock_guard<std::mutex> lock(mu_);
        if (started_) throw std::logic_error("WorkerThread::assign after start");
        operators_.push_back(op);
    }

    void set_affinity(CoreAffinity aff) {
        std::lock_guard<std::mutex> lock(mu_);
        if (started_) throw std::logic_error("WorkerThread::set_affinity after start");
        affinity_ = aff;
    }

    void start(FailureHandler failure = {}, CompletionHandler completion = {},
               CancelQuery cancelled = {}) {
        std::lock_guard<std::mutex> lock(mu_);
        if (started_) throw std::logic_error("WorkerThread::start called twice");
        started_ = true;
        failure_handler_ = std::move(failure);
        completion_handler_ = std::move(completion);
        cancel_query_ = std::move(cancelled);
        running_.store(true, std::memory_order_release);
        thread_ = std::thread([this] { run(); });
    }

    void request_stop() noexcept { running_.store(false, std::memory_order_release); }

    void request_cancel() noexcept {
        cancel_requested_.store(true, std::memory_order_release);
        running_.store(false, std::memory_order_release);
    }

    void stop() noexcept {
        request_stop();
        if (thread_.joinable()) thread_.join();
        std::lock_guard<std::mutex> lock(mu_);
        if (!shutdown_called_) {
            for (auto* op : operators_) {
                try { op->shutdown(); } catch (...) { /* shutdown is best effort */ }
            }
            shutdown_called_ = true;
        }
    }

    [[nodiscard]] bool started() const noexcept { return started_; }
    [[nodiscard]] bool running() const noexcept { return running_.load(std::memory_order_acquire); }
    [[nodiscard]] std::size_t operator_count() const noexcept { return operators_.size(); }
    [[nodiscard]] CoreAffinity affinity() const noexcept { return affinity_; }

    ~WorkerThread() { stop(); }

private:
    void notify_failure(IOperator* op, std::exception_ptr ep) noexcept {
        if (failure_handler_) {
            try { failure_handler_(*this, op, ep); } catch (...) { /* coordinator must not unwind worker */ }
        }
    }

    void notify_completion() noexcept {
        if (completion_handler_) {
            try { completion_handler_(*this); } catch (...) { /* coordinator must not unwind worker */ }
        }
    }

    void invoke_cancellation_hooks() noexcept {
        if (cancel_notified_.exchange(true, std::memory_order_acq_rel)) return;
        for (auto* op : operators_) {
            try { op->on_cancel(); } catch (...) { /* cancellation is best effort */ }
        }
    }

    void run() noexcept {
        apply_affinity(affinity_);
        for (auto* op : operators_) {
            try {
                op->init();
            } catch (...) {
                auto ep = std::current_exception();
                try { op->on_error(ep); } catch (...) {}
                notify_failure(op, ep);
                running_.store(false, std::memory_order_release);
                return;
            }
        }

        int idle_rounds = 0;
        const int yield_cap = SPIN_BEFORE_YIELD + YIELD_BEFORE_SLEEP;
        while (running_.load(std::memory_order_acquire)) {
            if (cancel_requested_.load(std::memory_order_acquire) ||
                (cancel_query_ && cancel_query_())) {
                invoke_cancellation_hooks();
                return;
            }

            bool any_progress = false;
            bool all_terminal = true;
            for (auto* op : operators_) {
                if (op->is_complete() || op->is_failed() || op->is_cancelled()) continue;
                all_terminal = false;
                try {
                    const OpStatus status = op->tick();
                    if (status == OpStatus::Processed) any_progress = true;
                    if (status == OpStatus::Failed || op->is_failed()) {
                        auto ep = std::make_exception_ptr(std::runtime_error("operator returned Failed: " + op->name()));
                        try { op->on_error(ep); } catch (...) {}
                        notify_failure(op, ep);
                        running_.store(false, std::memory_order_release);
                        return;
                    }
                } catch (...) {
                    auto ep = std::current_exception();
                    try { op->on_error(ep); } catch (...) {}
                    notify_failure(op, ep);
                    running_.store(false, std::memory_order_release);
                    return;
                }
            }

            if (all_terminal) {
                running_.store(false, std::memory_order_release);
                notify_completion();
                return;
            }

            if (!any_progress) {
                ++idle_rounds;
                if (idle_rounds < SPIN_BEFORE_YIELD) {
#if defined(__aarch64__)
                    __asm__ volatile("yield" ::: "memory");
#elif defined(__x86_64__)
                    __asm__ volatile("pause" ::: "memory");
#endif
                } else if (idle_rounds < yield_cap) {
                    std::this_thread::yield();
                } else {
                    std::this_thread::sleep_for(std::chrono::nanoseconds(SLEEP_NS));
                }
            } else {
                idle_rounds = 0;
            }
        }

        if (cancel_requested_.load(std::memory_order_acquire)) invoke_cancellation_hooks();
    }

    mutable std::mutex mu_;
    std::vector<IOperator*> operators_;
    CoreAffinity affinity_{CoreAffinity::Any};
    std::atomic<bool> running_{false};
    std::atomic<bool> cancel_requested_{false};
    std::atomic<bool> cancel_notified_{false};
    bool started_{false};
    bool shutdown_called_{false};
    std::thread thread_;
    FailureHandler failure_handler_;
    CompletionHandler completion_handler_;
    CancelQuery cancel_query_;
};

} // namespace klstream
