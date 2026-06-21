#pragma once
// KLStream runtime configuration constants.
// These are compile-time knobs; change them here, recompile everywhere.

#include <cstdint>
#include <cstddef>

namespace klstream {

// Queue sizing (power-of-two for SPSC modulo trick)
inline constexpr std::size_t DEFAULT_QUEUE_CAPACITY = 4096;
inline constexpr std::size_t BATCH_QUEUE_CAPACITY   = 64;

// Backpressure thresholds (fraction of queue capacity [0,1])
inline constexpr double BP_SOFT_THRESHOLD = 0.70;  // start shedding
inline constexpr double BP_LOW_THRESHOLD  = 0.30;  // resume normal

// EMA smoothing coefficient for OccupancyTracker
inline constexpr double EMA_ALPHA_DEFAULT = 0.10;

// Worker scheduler idle-spin budget before yield
inline constexpr int IDLE_SPIN_BUDGET = 128;

// Maximum number of tracked users in KeyedFeatureExtractOp
inline constexpr std::uint32_t MAX_TRACKED_USERS = 1'000'000;

// Maximum snapshots per FeatureBatch (compile-time upper bound for W)
inline constexpr std::uint32_t MAX_FEATURE_BATCH = 256;

// Controller trace sampling interval (every N ticks of the harness loop)
inline constexpr int CONTROLLER_TRACE_SAMPLE_EVERY = 64;

} // namespace klstream
