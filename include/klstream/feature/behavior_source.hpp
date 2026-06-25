#pragma once
// BehaviorSource: replays a preloaded vector of BehaviorRows into the pipeline.
// Two replay modes (mirroring Project 2's FinancialTickSource semantics):
//   PreserveTiming — respects original inter-arrival gaps (scaled by speed_factor)
//   MaxRate        — emits as fast as the output queue will accept
//
// Burst rows (is_burst_period=1) always replay at MaxRate regardless of mode,
// simulating flash-sale-like traffic spikes.
//
// Label information is carried in a parallel vector (labels_) and exposed via
// label_for_seq() to keep RawBehaviorEvent minimal (Section 13.3 implementation note).

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace klstream {

enum class DatasetMode { Taobao, ULB };
enum class ReplayMode  { PreserveTiming, MaxRate };

struct BehaviorRow {
    std::uint64_t seq;
    std::uint64_t timestamp_ns;
    std::uint32_t user_id, item_id;
    std::uint16_t category_id;
    std::uint8_t  behavior_code;
    float         amount;
    std::uint8_t  label, label_valid;
    std::uint8_t  is_burst_period;
};

// Schema-aware loader — branches on DatasetMode.
inline std::vector<BehaviorRow> load_replay_csv(const std::string& path, DatasetMode mode) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open replay CSV: " + path);
    std::string line;
    std::getline(f, line); // skip header
    std::vector<BehaviorRow> rows;
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        std::stringstream ss(line);
        std::string cell;
        BehaviorRow r{};
        auto gn = [&](){ std::getline(ss, cell, ','); };
        gn(); r.seq           = std::stoull(cell);
        gn(); r.timestamp_ns  = std::stoull(cell);
        gn(); r.user_id       = static_cast<std::uint32_t>(std::stoul(cell));
        gn(); r.item_id       = static_cast<std::uint32_t>(std::stoul(cell));
        gn(); r.category_id   = static_cast<std::uint16_t>(std::stoul(cell));
        gn(); r.behavior_code = static_cast<std::uint8_t>(std::stoi(cell));
        if (mode == DatasetMode::ULB) { gn(); r.amount = std::stof(cell); }
        else                          { r.amount = 0.0f; }
        gn(); r.label         = static_cast<std::uint8_t>(std::stoi(cell));
        gn(); r.label_valid   = static_cast<std::uint8_t>(std::stoi(cell));
        gn(); r.is_burst_period = static_cast<std::uint8_t>(std::stoi(cell));
        rows.push_back(r);
    }
    return rows;
}

class BehaviorSource {
public:
    BehaviorSource(std::vector<BehaviorRow> rows, ReplayMode mode, double speed_factor = 1.0)
        : rows_(std::move(rows)), mode_(mode), speed_factor_(speed_factor)
    {
        labels_.reserve(rows_.size());
        for (const auto& r : rows_) labels_.push_back({r.label, r.label_valid});
    }

    // Generator callback — invoked by SourceOperator<RawBehaviorEvent>::tick().
    bool operator()(Event<RawBehaviorEvent>& out, std::uint64_t /*seq*/) {
        if (idx_ >= rows_.size()) return false;
        const BehaviorRow& r = rows_[idx_];
        bool burst = (r.is_burst_period != 0);

        if (mode_ == ReplayMode::PreserveTiming && !burst && idx_ > 0) {
            std::uint64_t gap_ns = r.timestamp_ns - rows_[idx_-1].timestamp_ns;
            auto scaled = std::chrono::nanoseconds(
                static_cast<std::int64_t>(static_cast<double>(gap_ns) / speed_factor_));
            if (scaled.count() > 0 && scaled < std::chrono::milliseconds(100)) {
                std::this_thread::sleep_for(scaled);
            }
        }

        RawBehaviorEvent raw{r.user_id, r.timestamp_ns, r.item_id, r.category_id,
                             r.behavior_code, r.amount, r.is_burst_period};
        out = Event<RawBehaviorEvent>::make(raw, r.user_id, r.seq);
        ++idx_;
        return true;
    }

    // Ground-truth lookup by event seq for KeyedFeatureExtractOp (Section 13.3).
    [[nodiscard]] std::pair<std::uint8_t,std::uint8_t> label_for_seq(std::uint64_t seq) const {
        if (seq < labels_.size()) return labels_[seq];
        return {0, 0};
    }

    [[nodiscard]] std::size_t remaining() const noexcept { return rows_.size() - idx_; }
    [[nodiscard]] std::size_t total()     const noexcept { return rows_.size(); }

    // Synthetic dataset generation — used when real Taobao data is unavailable.
    // Creates N_users users with pseudo-random events over a simulated 9-day window,
    // including injected burst periods (matching Section 9.3's fallback plan).
    static std::vector<BehaviorRow> generate_synthetic(
        std::uint32_t n_users = 1000,
        std::uint64_t events_per_user = 200,
        double burst_fraction = 0.10,
        std::uint32_t seed = 42)
    {
        std::vector<BehaviorRow> rows;
        rows.reserve(n_users * events_per_user);
        // Linear-congruential RNG (no stdlib dependency for determinism)
        std::uint64_t rng = seed;
        auto rand_u64 = [&]() -> std::uint64_t {
            rng = rng * 6364136223846793005ULL + 1442695040888963407ULL;
            return rng;
        };

        std::uint64_t base_ts = 1511568000ULL * 1'000'000'000ULL; // 2017-11-25 00:00 UTC in ns
        std::uint64_t day_ns  = 86400ULL * 1'000'000'000ULL;
        std::uint64_t total_span_ns = 9 * day_ns;

        std::uint64_t seq = 0;
        for (std::uint32_t uid = 1; uid <= n_users; ++uid) {
            std::uint64_t t = base_ts + (rand_u64() % total_span_ns);
            for (std::uint64_t e = 0; e < events_per_user; ++e) {
                t += 10'000'000ULL + (rand_u64() % 300'000'000ULL); // 10ms–310ms gaps
                bool burst = (rand_u64() % 1000) < static_cast<std::uint64_t>(burst_fraction * 1000);
                std::uint8_t bcode = static_cast<std::uint8_t>(rand_u64() % 4);
                // Bias toward buy near the end of the sequence (label plausibility)
                std::uint8_t label = (e > events_per_user * 3/4 && bcode == 3) ? 1 : 0;
                std::uint8_t lv = (e > events_per_user * 3/4) ? 1 : 0;
                BehaviorRow r{};
                r.seq = seq++;
                r.timestamp_ns = t;
                r.user_id = uid;
                r.item_id = static_cast<std::uint32_t>(rand_u64() % 1000000);
                r.category_id = static_cast<std::uint16_t>(rand_u64() % 1000);
                r.behavior_code = bcode;
                r.amount = 0.0f;
                r.label = label;
                r.label_valid = lv;
                r.is_burst_period = burst ? 1 : 0;
                rows.push_back(r);
            }
        }
        // Sort by timestamp so the replayer sees monotone time.
        std::sort(rows.begin(), rows.end(),
                  [](const BehaviorRow& a, const BehaviorRow& b){
                      return a.timestamp_ns < b.timestamp_ns;
                  });
        // Re-assign seq after sort and assign contiguous burst period (middle third).
        for (std::size_t i = 0; i < rows.size(); ++i) {
            rows[i].seq = i;
            if (i >= rows.size() / 3 && i < 2 * rows.size() / 3) {
                rows[i].is_burst_period = 1;
            } else {
                rows[i].is_burst_period = 0;
            }
        }
        return rows;
    }

private:
    std::vector<BehaviorRow> rows_;
    std::vector<std::pair<std::uint8_t,std::uint8_t>> labels_;
    ReplayMode  mode_;
    double      speed_factor_;
    std::size_t idx_{0};
};

} // namespace klstream
