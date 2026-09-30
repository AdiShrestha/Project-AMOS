#pragma once
#include "spsc_queue.hpp"
#include "features.hpp"
#include "model.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <exception>
#include <functional>
#include <iomanip>
#include <limits>
#include <mutex>
#include <ostream>
#include <thread>
#include <vector>

namespace bpfeat {
inline std::uint64_t monotonic_ns() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
enum class Mode { Fixed, BatchOnly, AlphaOnly, Joint };
struct PipelineConfig {
    Mode mode{Mode::Fixed};
    std::uint32_t batch_initial{32}, batch_min{8}, batch_max{256};
    double alpha_initial{0.1}, alpha_min{0.02}, alpha_max{0.3}, alpha_delta{0.01};
    double occupancy_gain{0.1}, low{0.3}, high{0.7}, shrink{0.7}, grow{1.15};
    std::size_t feature_slots{1024}, batch_slots{8}, max_keys{1000000};
    std::uint64_t timeout_seconds{60};
};
inline constexpr std::size_t MAX_BATCH = 256;
struct Batch {
    std::array<FeatureSnapshot, MAX_BATCH> items{};
    std::uint32_t count{0};
    PressureObservation pressure_at_start;
};
struct PipelineStats {
    std::uint64_t read{0}, extracted{0}, batched{0}, scored{0}, written{0}, batches{0}, tails{0};
    std::uint64_t source_block_retries{0}, batch_block_retries{0}, batch_actions{0}, direction_changes{0};
    std::uint64_t started_ns{0}, finished_ns{0};
};
inline void validate(const PipelineConfig& config) {
    if (config.batch_max > MAX_BATCH || config.batch_min == 0 || config.batch_min > config.batch_initial ||
        config.batch_initial > config.batch_max || !config.max_keys || !config.timeout_seconds ||
        config.timeout_seconds > 86400 || config.feature_slots > 1048576 || config.batch_slots > 4096)
        throw std::invalid_argument("invalid pipeline resource or batch bounds");
    if (config.mode != Mode::Fixed && config.mode != Mode::BatchOnly && config.mode != Mode::AlphaOnly && config.mode != Mode::Joint)
        throw std::invalid_argument("unknown pipeline mode");
    AlphaController alpha(config.alpha_min, config.alpha_max, config.alpha_delta, config.alpha_initial);
    MultiplicativeBatchController batch(config.batch_min, config.batch_max, config.low, config.high,
                                         config.shrink, config.grow, config.batch_initial);
    OccupancyEMA tracker(config.occupancy_gain);
    (void)alpha; (void)batch; (void)tracker;
}

// Three actual workers: streaming source/features, batching/feedback, scoring/
// file sink. Every accepted input is scored exactly once, including EOF tails.
// Completion requires joined workers, closed queues and counter conservation.
// No dataset labels, predictor training, publication cache or benchmark claim.
inline PipelineStats run_pipeline(std::function<bool(RawEvent&)> next, const LogisticModel& model,
                                 std::ostream& predictions, std::ostream& controller_trace,
                                 const PipelineConfig& config) {
    validate(config);
    if (!next) throw std::invalid_argument("missing source callback");
    SPSCQueue<FeatureSnapshot> features(config.feature_slots);
    SPSCQueue<Batch> batches(config.batch_slots);
    PressureSignal signal;
    PipelineStats stats;
    stats.started_ns = monotonic_ns();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(config.timeout_seconds);
    std::atomic<bool> cancelled{false};
    std::mutex error_mutex;
    std::exception_ptr first_error;
    auto fail = [&](std::exception_ptr error) {
        { std::lock_guard<std::mutex> lock(error_mutex); if (!first_error) first_error = error; }
        cancelled.store(true, std::memory_order_release);
    };
    auto check = [&]() {
        if (cancelled.load(std::memory_order_acquire)) return false;
        if (std::chrono::steady_clock::now() >= deadline) throw std::runtime_error("engine deadline exceeded");
        return true;
    };
    auto pause = [] { std::this_thread::yield(); };
    predictions << "seq,event_ts_ns,key,score,alpha_used,pressure_used,pressure_generation_used,pressure_available,"
                   "source_created_ns,scored_ns,latency_ns,batch_size,batch_pressure,batch_pressure_generation";
    for (std::size_t i = 0; i < FEATURE_DIMENSION; ++i) predictions << ",x" << i;
    predictions << '\n' << std::setprecision(std::numeric_limits<double>::max_digits10);
    controller_trace << "generation,sampled_ns,occupancy_slots,occupancy_ema,batch_target\n"
                     << std::setprecision(std::numeric_limits<double>::max_digits10);
    if (!predictions || !controller_trace) throw std::runtime_error("cannot write engine headers");
    std::vector<std::thread> workers;
    workers.reserve(3);
    auto launch = [&](auto function) {
        workers.emplace_back([&, function] { try { function(); } catch (...) { fail(std::current_exception()); } });
    };
    try {
        launch([&] {
            Batch batch;
            while (check()) {
                if (!batches.try_pop(batch)) {
                    if (batches.closed_and_empty()) break;
                    pause(); continue;
                }
                if (!batch.count || batch.count > MAX_BATCH) throw std::runtime_error("invalid accepted batch");
                for (std::uint32_t i = 0; i < batch.count; ++i) {
                    if (!check()) return;
                    const auto& snapshot = batch.items[i];
                    const auto score = model.score(snapshot.x);
                    ++stats.scored;
                    const auto scored_ns = monotonic_ns();
                    predictions << snapshot.event.seq << ',' << snapshot.event.event_ts_ns << ',' << snapshot.event.key
                                << ',' << score << ',' << snapshot.alpha << ',' << snapshot.pressure_used.value
                                << ',' << snapshot.pressure_used.generation << ',' << snapshot.pressure_used.available
                                << ',' << snapshot.created_ns << ',' << scored_ns << ',' << scored_ns - snapshot.created_ns
                                << ',' << batch.count << ',' << batch.pressure_at_start.value
                                << ',' << batch.pressure_at_start.generation;
                    for (auto value : snapshot.x) predictions << ',' << value;
                    predictions << '\n';
                    if (!predictions) throw std::runtime_error("prediction write failed");
                    ++stats.written;
                }
            }
            predictions.flush();
            if (!predictions) throw std::runtime_error("prediction final flush failed");
        });
        launch([&] {
            OccupancyEMA tracker(config.occupancy_gain);
            MultiplicativeBatchController controller(config.batch_min, config.batch_max, config.low, config.high,
                                                      config.shrink, config.grow, config.batch_initial);
            Batch batch;
            std::uint32_t target = config.batch_initial;
            auto flush = [&]() {
                if (!batch.count) return true;
                while (!batches.try_push(batch)) {
                    if (!check()) return false;
                    ++stats.batch_block_retries;
                    pause();
                }
                ++stats.batches;
                batch = Batch{};
                return true;
            };
            FeatureSnapshot snapshot;
            while (check()) {
                if (!features.try_pop(snapshot)) {
                    if (features.closed_and_empty()) break;
                    pause(); continue;
                }
                // Exactly one control update for each nonempty batch start.
                // Idle polling and blocked retries never advance the controller.
                if (!batch.count) {
                    auto raw_pressure = batches.occupancy();
                    auto pressure = tracker.update(raw_pressure);
                    signal.store(pressure, monotonic_ns());
                    batch.pressure_at_start = signal.load();
                    target = (config.mode == Mode::BatchOnly || config.mode == Mode::Joint)
                        ? controller.update(pressure) : config.batch_initial;
                    controller_trace << batch.pressure_at_start.generation << ',' << batch.pressure_at_start.sampled_ns
                                     << ',' << raw_pressure << ',' << pressure << ',' << target << '\n';
                    if (!controller_trace) throw std::runtime_error("controller trace write failed");
                }
                batch.items[batch.count++] = snapshot;
                ++stats.batched;
                if (batch.count == target && !flush()) return;
            }
            if (cancelled.load(std::memory_order_acquire)) return;
            if (batch.count) { ++stats.tails; if (!flush()) return; }
            controller_trace.flush();
            if (!controller_trace) throw std::runtime_error("controller trace final flush failed");
            stats.batch_actions = controller.actions();
            stats.direction_changes = controller.direction_changes();
            batches.close();
        });
        launch([&] {
            KeyedFeatures extractor(config.max_keys);
            AlphaController alpha(config.alpha_min, config.alpha_max, config.alpha_delta, config.alpha_initial);
            RawEvent event;
            bool seen = false;
            std::uint64_t previous_seq = 0, previous_event_ns = 0;
            while (check() && next(event)) {
                ++stats.read;
                if (seen && (event.seq <= previous_seq || event.event_ts_ns < previous_event_ns))
                    throw std::invalid_argument("source sequence/time order violated");
                seen = true;
                previous_seq = event.seq;
                previous_event_ns = event.event_ts_ns;
                auto created_ns = monotonic_ns();
                auto observation = signal.load();
                // No observation is recorded as available until the first real
                // batch-start sample. Hold the declared initial alpha before it.
                auto value = config.alpha_initial;
                if (config.mode == Mode::AlphaOnly || config.mode == Mode::Joint)
                    value = observation.available ? alpha.update(observation.value) : alpha.current();
                auto snapshot = extractor.update(event, value, created_ns, observation);
                ++stats.extracted;
                while (!features.try_push(snapshot)) {
                    if (!check()) return;
                    ++stats.source_block_retries;
                    pause();
                }
            }
            if (!cancelled.load(std::memory_order_acquire)) features.close();
        });
    } catch (...) { fail(std::current_exception()); }
    for (auto& worker : workers) if (worker.joinable()) worker.join();
    stats.finished_ns = monotonic_ns();
    if (first_error) std::rethrow_exception(first_error);
    if (!features.closed_and_empty() || !batches.closed_and_empty() || stats.read != stats.extracted ||
        stats.read != stats.batched || stats.read != stats.scored || stats.read != stats.written)
        throw std::runtime_error("terminal engine conservation failure");
    return stats;
}
}
