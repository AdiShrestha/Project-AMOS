#pragma once
// Worker: runs a list of IOperator*s in a cooperative round-robin tick loop
// on one std::thread. Stops when stop() is called or all operators return Done.

#include "operator.hpp"
#include "pinning.hpp"
#include <atomic>
#include <thread>
#include <vector>

namespace klstream {

class Worker {
public:
    explicit Worker(std::vector<IOperator*> ops, int core_id = -1)
        : ops_(std::move(ops)), core_id_(core_id) {}

    void start() {
        thread_ = std::thread([this]{ run(); });
        if (core_id_ >= 0) pin_thread_to_core(thread_, core_id_);
    }

    void stop() noexcept { running_.store(false, std::memory_order_relaxed); }

    void join() { if (thread_.joinable()) thread_.join(); }

    ~Worker() { stop(); join(); }

private:
    void run() {
        while (running_.load(std::memory_order_relaxed)) {
            int idle_count = 0;
            for (auto* op : ops_) {
                auto s = op->tick();
                if (s == OpStatus::Idle || s == OpStatus::Blocked) ++idle_count;
            }
            // If every operator was idle/blocked this round, yield the CPU
            // briefly rather than burning a full spin.
            if (idle_count == static_cast<int>(ops_.size())) {
                std::this_thread::yield();
            }
        }
        for (auto* op : ops_) op->shutdown();
    }

    std::vector<IOperator*> ops_;
    int core_id_{-1};
    std::atomic<bool> running_{true};
    std::thread thread_;
};

} // namespace klstream
