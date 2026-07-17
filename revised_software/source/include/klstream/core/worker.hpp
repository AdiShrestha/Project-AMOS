// include/klstream/core/worker.hpp
#pragma once
#include "operator.hpp"
#include "pinning.hpp"
#include "config.hpp"
#include <atomic>
#include <chrono>
#include <memory>
#include <thread>
#include <vector>

namespace klstream {

// ── WorkerThread ──────────────────────────────────────────────────────────
//
// One OS thread (std::thread) that owns a list of IOperator* and executes
// them cooperatively in a round-robin loop.
//
// Scheduling policy (cooperative round-robin with three-tier backoff):
//
//   while (running):
//       for each operator in assigned_operators:
//           status = operator.tick()
//           if status == Processed:  reset idle counter
//           else:                    increment idle counter
//       if all operators were Idle or Blocked this round:
//           apply_backoff(idle_rounds)
//
// The backoff escalates:
//   idle_rounds < SPIN_BEFORE_YIELD  →  ARM `yield` / x86 `pause`
//   idle_rounds < SPIN + YIELD_CAP   →  std::this_thread::yield()
//   idle_rounds >= above             →  sleep_for(SLEEP_NS nanoseconds)
class WorkerThread {
public:
    WorkerThread() = default;

    // Non-copyable, non-movable
    WorkerThread(const WorkerThread&)            = delete;
    WorkerThread& operator=(const WorkerThread&) = delete;
    WorkerThread(WorkerThread&&)                 = delete;
    WorkerThread& operator=(WorkerThread&&)      = delete;

    void assign(IOperator* op) {
        operators_.push_back(op);
    }

    void set_affinity(CoreAffinity aff) { affinity_ = aff; }

    void start() {
        running_.store(true, std::memory_order_relaxed);
        thread_ = std::thread([this]{ run(); });
    }

    void stop() {
        running_.store(false, std::memory_order_release);
        if (thread_.joinable()) thread_.join();
        for (auto* op : operators_) op->shutdown();
        operators_.clear();
    }

    ~WorkerThread() { stop(); }

private:
    void run() {
        apply_affinity(affinity_);

        for (auto* op : operators_) op->init();

        int idle_rounds = 0;
        const int YIELD_CAP = SPIN_BEFORE_YIELD + YIELD_BEFORE_SLEEP;

        while (running_.load(std::memory_order_relaxed)) {
            bool any_progress = false;
            for (auto* op : operators_) {
                OpStatus s = op->tick();
                if (s == OpStatus::Processed) any_progress = true;
            }
            if (!any_progress) {
                ++idle_rounds;
                if (idle_rounds < SPIN_BEFORE_YIELD) {
#if defined(__aarch64__)
                    __asm__ volatile("yield" ::: "memory");
#elif defined(__x86_64__)
                    __asm__ volatile("pause" ::: "memory");
#endif
                } else if (idle_rounds < YIELD_CAP) {
                    std::this_thread::yield();
                } else {
                    std::this_thread::sleep_for(
                        std::chrono::nanoseconds(SLEEP_NS));
                }
            } else {
                idle_rounds = 0;
            }
        }
    }

    std::vector<IOperator*>  operators_;
    CoreAffinity             affinity_{CoreAffinity::Any};
    std::atomic<bool>        running_{false};
    std::thread              thread_;
};

} // namespace klstream
