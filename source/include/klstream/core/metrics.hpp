// include/klstream/core/metrics.hpp
#pragma once
#include "config.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
#include <chrono>
#include <iostream>
#include <iomanip>
#include <fstream>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <algorithm>
#include <condition_variable>
#include <thread>

namespace klstream {

// ── Counter ───────────────────────────────────────────────────────────────
//
// A cache-line-aligned atomic counter for counting events.
// Each operator has one Counter for events_processed and one for
// events_blocked (backpressure occurrences).
//
// memory_order_relaxed is used everywhere because:
//   a) We only care about approximate throughput, not exact synchronisation.
//   b) Relaxed atomics do not generate memory fence instructions on ARM,
//      so they cost essentially nothing in the hot path.
//   c) We snapshot counters from a reporter thread using relaxed loads,
//      which is fine because we only need "recent" values, not "exact" values.
struct Counter {
    alignas(CACHE_LINE_SIZE) std::atomic<std::uint64_t> value{0};

    void increment() noexcept {
        value.fetch_add(1, std::memory_order_relaxed);
    }

    std::uint64_t load() const noexcept {
        return value.load(std::memory_order_relaxed);
    }

    // Atomically reset and return the old value (used by the reporter to
    // compute per-interval throughput without cumulative growth).
    std::uint64_t reset() noexcept {
        return value.exchange(0, std::memory_order_relaxed);
    }
};

// ── LatencyHistogram ──────────────────────────────────────────────────────
//
// A fixed-width histogram for end-to-end latency. Each bucket covers 1 us.
// Bucket index = latency_us = latency_ns / 1000.
// Values beyond MAX_LATENCY_US go into an overflow bucket.
//
// Not lock-free: uses a single compare_exchange_weak per record. Suitable
// for the sink operator (single consumer thread increments buckets).
// If multiple sinks need to share a histogram, protect with a mutex or
// use per-thread histograms merged periodically.
struct LatencyHistogram {
    std::array<std::atomic<std::uint64_t>, HISTOGRAM_BUCKETS + 1> buckets{};

    LatencyHistogram() {
        for (auto& b : buckets) b.store(0, std::memory_order_relaxed);
    }

    void record(std::uint64_t latency_ns) noexcept {
        std::size_t idx = latency_ns / 1000; // convert ns -> us
        if (idx >= HISTOGRAM_BUCKETS) idx = HISTOGRAM_BUCKETS; // overflow
        buckets[idx].fetch_add(1, std::memory_order_relaxed);
    }

    // Returns the latency_us value below which `pct` fraction of events fall.
    // E.g., percentile(0.99) returns p99 latency in microseconds.
    double percentile(double pct) const noexcept {
        std::uint64_t total = 0;
        for (const auto& b : buckets)
            total += b.load(std::memory_order_relaxed);
        if (total == 0) return 0.0;
        const std::uint64_t target = static_cast<std::uint64_t>(pct * total);
        std::uint64_t cumulative = 0;
        for (std::size_t i = 0; i < HISTOGRAM_BUCKETS; ++i) {
            cumulative += buckets[i].load(std::memory_order_relaxed);
            if (cumulative >= target) return static_cast<double>(i);
        }
        return static_cast<double>(MAX_LATENCY_US); // overflow bucket
    }
};

// ── OperatorMetrics ───────────────────────────────────────────────────────
//
// One per operator instance. Attached to the operator at construction and
// read by the MetricsReporter thread.
struct OperatorMetrics {
    Counter events_processed;   // successfully processed events
    Counter events_blocked;     // tick() returned Blocked (backpressure)
    Counter events_idle;        // tick() returned Idle (no input)
    std::string op_name;        // set at construction, never modified after

    OperatorMetrics() = default;
    explicit OperatorMetrics(std::string name) : op_name(std::move(name)) {}
};

// Exact run accounting used by terminal conservation and audit contracts.
struct AccountingSnapshot {
    std::uint64_t offered{0};
    std::uint64_t admitted{0};
    std::uint64_t rejected{0};
    std::uint64_t terminal_scored{0};
    std::uint64_t terminal_dropped{0};
    std::uint64_t terminal_failed{0};
    std::uint64_t terminal_cancelled{0};
    std::int64_t in_flight{0};
    std::uint64_t emitted{0};
    std::uint64_t partial_batches{0};
    std::uint64_t sink_finalized{0};
    std::uint64_t failure_recorded{0};
};

class AccountingLedger {
public:
    void offer(std::uint64_t n = 1) noexcept { offered_.fetch_add(n, std::memory_order_relaxed); }
    void admit(std::uint64_t n = 1) noexcept {
        admitted_.fetch_add(n, std::memory_order_relaxed);
        in_flight_.fetch_add(static_cast<std::int64_t>(n), std::memory_order_relaxed);
    }
    void reject(std::uint64_t n = 1) noexcept { rejected_.fetch_add(n, std::memory_order_relaxed); }
    void emitted(std::uint64_t n = 1) noexcept { emitted_.fetch_add(n, std::memory_order_relaxed); }
    void partial_batch(std::uint64_t n = 1) noexcept { partial_batches_.fetch_add(n, std::memory_order_relaxed); }
    void failure_recorded() noexcept { failure_recorded_.fetch_add(1, std::memory_order_relaxed); }
    void sink_finalized() noexcept { sink_finalized_.fetch_add(1, std::memory_order_relaxed); }
    void scored(std::uint64_t n = 1) noexcept { terminal_scored_.fetch_add(n, std::memory_order_relaxed); release(n); }
    void dropped(std::uint64_t n = 1) noexcept { terminal_dropped_.fetch_add(n, std::memory_order_relaxed); release(n); }
    void failed(std::uint64_t n = 1) noexcept { terminal_failed_.fetch_add(n, std::memory_order_relaxed); release(n); }
    void cancelled(std::uint64_t n = 1) noexcept { terminal_cancelled_.fetch_add(n, std::memory_order_relaxed); release(n); }

    [[nodiscard]] AccountingSnapshot snapshot() const noexcept {
        return {offered_.load(), admitted_.load(), rejected_.load(),
                terminal_scored_.load(), terminal_dropped_.load(),
                terminal_failed_.load(), terminal_cancelled_.load(),
                in_flight_.load(), emitted_.load(), partial_batches_.load(),
                sink_finalized_.load(), failure_recorded_.load()};
    }

    [[nodiscard]] bool conservation_valid() const noexcept {
        const auto s = snapshot();
        const auto terminal = s.terminal_scored + s.terminal_dropped +
                              s.terminal_failed + s.terminal_cancelled;
        return s.offered == s.admitted + s.rejected &&
               s.in_flight >= 0 &&
               static_cast<std::uint64_t>(s.in_flight) + terminal == s.admitted;
    }

    [[nodiscard]] bool terminal_predicate(bool sources_closed,
                                          bool operators_completed,
                                          bool queues_drained,
                                          bool sink_is_finalized) const noexcept {
        const auto s = snapshot();
        return sources_closed && operators_completed && queues_drained &&
               sink_is_finalized && s.in_flight == 0 && s.failure_recorded == 0;
    }

private:
    void release(std::uint64_t n) noexcept {
        auto current = in_flight_.load(std::memory_order_relaxed);
        for (;;) {
            const auto next = std::max<std::int64_t>(0, current - static_cast<std::int64_t>(n));
            if (in_flight_.compare_exchange_weak(current, next,
                    std::memory_order_relaxed, std::memory_order_relaxed)) return;
        }
    }

    std::atomic<std::uint64_t> offered_{0}, admitted_{0}, rejected_{0};
    std::atomic<std::uint64_t> terminal_scored_{0}, terminal_dropped_{0};
    std::atomic<std::uint64_t> terminal_failed_{0}, terminal_cancelled_{0};
    std::atomic<std::int64_t> in_flight_{0};
    std::atomic<std::uint64_t> emitted_{0}, partial_batches_{0};
    std::atomic<std::uint64_t> sink_finalized_{0}, failure_recorded_{0};
};

struct TraceRecord {
    std::uint64_t event_seq{0};
    std::uint64_t trace_seq{0};
    std::uint64_t generation{0};
    std::string origin;
    std::string kind;
    std::uint64_t monotonic_ns{0};
    std::string wall_time_utc;
    std::string configuration_id;
    std::string completeness_status;
};

inline std::string trace_escape(const std::string& value) {
    std::string out;
    out.reserve(value.size() + 8);
    for (const char c : value) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default: out += c; break;
        }
    }
    return out;
}

// Native JSONL trace writer. Records are append-only and never reconstructed
// from aggregate metrics; sequence monotonicity is enforced at write time.
class NativeTraceWriter {
public:
    NativeTraceWriter(std::string path, std::string run_id,
                      std::string configuration_id)
        : out_(std::move(path)), run_id_(std::move(run_id)),
          configuration_id_(std::move(configuration_id)) {
        if (!out_) throw std::runtime_error("NativeTraceWriter: cannot open output");
    }

    void write(const TraceRecord& record) {
        std::lock_guard<std::mutex> lock(mu_);
        if (has_written_ && record.trace_seq <= last_trace_seq_)
            throw std::logic_error("NativeTraceWriter: non-monotonic trace_seq");
        if (has_written_ && record.event_seq < last_event_seq_)
            throw std::logic_error("NativeTraceWriter: non-monotonic event_seq");
        out_ << "{\"schema_version\":\"1.0\",\"run_id\":\""
             << trace_escape(run_id_) << "\",\"event_seq\":" << record.event_seq
             << ",\"trace_seq\":" << record.trace_seq
             << ",\"generation\":" << record.generation
             << ",\"origin\":\"" << trace_escape(record.origin)
             << "\",\"kind\":\"" << trace_escape(record.kind)
             << "\",\"monotonic_ns\":" << record.monotonic_ns
             << ",\"wall_time_utc\":\"" << trace_escape(record.wall_time_utc)
             << "\",\"configuration_id\":\"" << trace_escape(configuration_id_)
             << "\",\"completeness_status\":\""
             << trace_escape(record.completeness_status) << "\"}\n";
        if (!out_) throw std::runtime_error("NativeTraceWriter: write failure");
        last_trace_seq_ = record.trace_seq;
        last_event_seq_ = record.event_seq;
        has_written_ = true;
    }

    void flush() { std::lock_guard<std::mutex> lock(mu_); out_.flush(); }
    [[nodiscard]] const std::string& run_id() const noexcept { return run_id_; }

private:
    std::ofstream out_;
    std::string run_id_, configuration_id_;
    std::uint64_t last_trace_seq_{0};
    std::uint64_t last_event_seq_{0};
    bool has_written_{false};
    std::mutex mu_;
};

// ── MetricsReporter ───────────────────────────────────────────────────────
//
// Runs on its own background std::thread. Every METRICS_INTERVAL_SEC seconds
// it samples all registered OperatorMetrics instances and prints a summary
// table to stdout.
//
// To use: create one MetricsReporter, call add(metrics_ptr) for each operator,
// then call start(). Call stop() on shutdown.
class MetricsReporter {
public:
    void add(OperatorMetrics* m) {
        if (!m) throw std::invalid_argument("MetricsReporter::add: null metrics");
        std::lock_guard<std::mutex> lock(mu_);
        entries_.push_back(m);
    }

    void start() {
        std::lock_guard<std::mutex> lock(mu_);
        if (running_.load()) return;
        running_.store(true);
        thread_ = std::thread([this]{ run(); });
    }

    void stop() {
        running_.store(false);
        cv_.notify_all();
        if (thread_.joinable()) thread_.join();
    }

    ~MetricsReporter() { stop(); }

private:
    void run() {
        while (running_.load(std::memory_order_relaxed)) {
            std::unique_lock<std::mutex> lock(cv_mu_);
            cv_.wait_for(lock, std::chrono::seconds(METRICS_INTERVAL_SEC),
                         [this] { return !running_.load(std::memory_order_relaxed); });
            if (!running_.load(std::memory_order_relaxed)) break;
            print();
        }
    }

    void print() {
        using namespace std;
        cout << "\n── KLStream Metrics ─────────────────────────────────\n";
        cout << left
             << setw(22) << "Operator"
             << setw(16) << "Events/sec"
             << setw(14) << "Blocked/sec"
             << setw(12) << "Idle/sec" << "\n";
        cout << string(64, '-') << "\n";
        std::lock_guard<std::mutex> lock(mu_);
        for (auto* m : entries_) {
            cout << setw(22) << m->op_name
                 << setw(16) << m->events_processed.reset()
                 << setw(14) << m->events_blocked.reset()
                 << setw(12) << m->events_idle.reset()
                 << "\n";
        }
        cout << flush;
    }

    std::vector<OperatorMetrics*> entries_;
    mutable std::mutex            mu_;
    std::atomic<bool>             running_{false};
    std::thread                   thread_;
    std::mutex                    cv_mu_;
    std::condition_variable       cv_;
};

} // namespace klstream
