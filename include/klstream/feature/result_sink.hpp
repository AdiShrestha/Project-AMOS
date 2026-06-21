#pragma once
// ResultSink: CSV writer for ScoredResult events (Section 19).
// log_controller_trace: sampled controller-state logger, called from the
// harness loop — not an IOperator, just a free function writing to a
// separate ofstream.

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <fstream>
#include <iomanip>
#include <ostream>
#include <string>

namespace klstream {

class ResultSink : public IOperator {
public:
    using InQueue = SPSCQueue<Event<ScoredResult>>;

    ResultSink(std::string name, InQueue* input, std::string out_csv_path)
        : IOperator(std::move(name)), input_(input)
        , out_(out_csv_path)
    {
        if (!out_) throw std::runtime_error("ResultSink: cannot open " + out_csv_path);
        out_ << "seq,result_timestamp_ns,latency_ns,user_id,score,"
                "label,label_valid,window_size_used,alpha_used,"
                "staleness_sec,occupancy_at_decision\n";
    }

    void attach_metrics(OperatorMetrics* m) { metrics_ = m; }

    OpStatus tick() override {
        Event<ScoredResult> ev;
        if (!input_->try_pop(&ev)) {
            if (metrics_) metrics_->events_idle.increment();
            return OpStatus::Idle;
        }
        const auto& r = ev.data;
        out_ << ev.seq                              << ','
             << ev.timestamp_ns                     << ','
             << ev.latency_ns()                     << ','
             << r.user_id                           << ','
             << std::setprecision(8) << r.score     << ','
             << static_cast<int>(r.label)           << ','
             << static_cast<int>(r.label_valid)     << ','
             << r.window_size_used                  << ','
             << r.alpha_used                        << ','
             << r.staleness_sec                     << ','
             << r.occupancy_at_decision             << '\n';
        if (metrics_) metrics_->events_processed.increment();
        return OpStatus::Processed;
    }

    void shutdown() override { out_.flush(); }

    [[nodiscard]] std::uint64_t rows_written() const noexcept { return rows_written_; }

private:
    InQueue*      input_;
    std::ofstream out_;
    std::uint64_t rows_written_{0};
    OperatorMetrics* metrics_{nullptr};
};

// ── Controller trace logger ───────────────────────────────────────────────────
// Called from harness.cpp's outer loop every CONTROLLER_TRACE_SAMPLE_EVERY
// ticks. Not an IOperator — reads public state from two already-running
// operators, writes directly to its own ofstream.
inline void log_controller_trace(std::ofstream& out,
                                  std::uint64_t wall_ns,
                                  std::uint32_t w,
                                  float alpha,
                                  double occupancy) {
    out << wall_ns    << ','
        << w          << ','
        << alpha      << ','
        << occupancy  << '\n';
}

// Writes the trace CSV header; call once before the run loop.
inline void init_controller_trace(std::ofstream& out) {
    if (!out) throw std::runtime_error("controller trace: cannot open output file");
    out << "wall_ns,w,alpha,occupancy\n";
}

} // namespace klstream
