#pragma once
// Runtime: registers operators, builds a single-worker cooperative scheduler,
// and runs until the source is exhausted (all registered operators return Done
// for a full round-trip) or stop() is called.
//
// For BPFeat's experiments all operators share one thread (matching Project 2's
// single-node, single-worker design), which gives clean causal attribution:
// the only wall-clock difference between architectures is the time spent inside
// ScoringFlushOp's O(W) hot loop.

#include "operator.hpp"
#include "worker.hpp"
#include <chrono>
#include <cstddef>
#include <thread>
#include <vector>

namespace klstream {

class Runtime {
public:
    Runtime() = default;

    void register_op(IOperator* op) { ops_.push_back(op); }

    // Runs the cooperative loop on the CALLER's thread (no extra thread created)
    // until a full round of all operators returns Done/Idle — i.e., the source
    // is exhausted and all queues have drained. This design keeps main.cpp
    // experiments single-threaded for reproducibility, exactly mirroring
    // Project 2's run_until_source_exhausted() semantics.
    void run_until_source_exhausted(std::size_t max_idle_rounds = 1'000'000) {
        std::size_t consecutive_idle = 0;
        while (true) {
            int done_count  = 0;
            int idle_count  = 0;
            for (auto* op : ops_) {
                auto s = op->tick();
                if (s == OpStatus::Done)                            ++done_count;
                if (s == OpStatus::Idle || s == OpStatus::Blocked)  ++idle_count;
            }
            if (done_count > 0 && idle_count == static_cast<int>(ops_.size()) - done_count) {
                // All non-Done operators are idle — pipeline has drained.
                ++consecutive_idle;
                if (consecutive_idle >= max_idle_rounds) break;
            } else {
                consecutive_idle = 0;
            }
            if (done_count == static_cast<int>(ops_.size())) break;
            if (idle_count == static_cast<int>(ops_.size())) {
                ++consecutive_idle;
                if (consecutive_idle >= max_idle_rounds) break;
                std::this_thread::yield();
            }
        }
        for (auto* op : ops_) op->shutdown();
    }

    // For multi-threaded use (harness.cpp): build workers and return control.
    Worker* build_worker(int core_id = -1) {
        workers_.emplace_back(std::make_unique<Worker>(ops_, core_id));
        return workers_.back().get();
    }

    void stop_all() { for (auto& w : workers_) w->stop(); }
    void join_all()  { for (auto& w : workers_) w->join();  }

private:
    std::vector<IOperator*>             ops_;
    std::vector<std::unique_ptr<Worker>> workers_;
};

} // namespace klstream
