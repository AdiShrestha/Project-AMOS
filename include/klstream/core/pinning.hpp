#pragma once
// CPU affinity helpers — pin a std::thread to a specific core.
// Silently no-ops on platforms that don't support pthread_setaffinity_np
// (e.g., macOS, which uses thread_policy_set instead; not implemented here
// since single-node experiments on macOS development machines do not require
// strict pinning for correctness, only for reproducibility in production
// benchmarks on Linux systems with known NUMA topology).

#include <thread>

#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#endif

namespace klstream {

inline void pin_thread_to_core(std::thread& t, int core_id) noexcept {
#ifdef __linux__
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(core_id, &cpuset);
    pthread_setaffinity_np(t.native_handle(), sizeof(cpu_set_t), &cpuset);
#else
    (void)t; (void)core_id; // no-op on macOS
#endif
}

inline int hardware_concurrency() noexcept {
    return static_cast<int>(std::thread::hardware_concurrency());
}

} // namespace klstream
