#pragma once
// BehaviorSource: replays a preloaded vector of BehaviorRows into the pipeline.
// Two replay modes (mirroring Project 2's FinancialTickSource semantics):
//   PreserveTiming — respects original inter-arrival gaps (scaled by speed_factor)
//   MaxRate        — emits as fast as the output queue will accept
//
// Burst rows (is_burst_period=1) always replay at MaxRate regardless of mode,
// simulating flash-sale-like traffic spikes.
//
// Label information is carried in a sequence-keyed side map (labels_) and
// exposed via label_for_seq() to keep RawBehaviorEvent minimal (Section 13.3
// implementation note). Keying by seq, rather than assuming dense indexes,
// preserves source-column sequence identity.

#pragma once
#include "../core/operator.hpp"
#include "../core/event.hpp"
#include "../core/spsc_queue.hpp"
#include "../core/metrics.hpp"
#include "types.hpp"
#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

namespace klstream {

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

// Schema-aware loader — branches explicitly on DatasetMode without heuristic inference.
inline std::vector<BehaviorRow> load_replay_csv(const std::string& path, DatasetMode mode) {
    std::ifstream f(path);
    if (!f) throw std::runtime_error("cannot open replay CSV: " + path);
    std::string line;
    if (!std::getline(f, line)) throw std::runtime_error("empty replay CSV: " + path);

    auto split = [](const std::string& value) {
        std::vector<std::string> cells;
        std::stringstream ss(value);
        std::string cell;
        while (std::getline(ss, cell, ',')) cells.push_back(cell);
        if (!cells.empty() && !cells.back().empty() && cells.back().back() == '\r') {
            cells.back().pop_back();
        }
        return cells;
    };
    const std::vector<std::string> expected_header = (mode == DatasetMode::Taobao)
        ? std::vector<std::string>{"seq", "timestamp_ns", "user_id", "item_id",
                                   "category_id", "behavior_code", "label",
                                   "label_valid", "is_burst_period"}
        : std::vector<std::string>{"seq", "timestamp_ns", "user_id", "item_id",
                                   "category_id", "behavior_code", "amount",
                                   "label", "label_valid", "is_burst_period"};
    const auto header_cells = split(line);
    if (header_cells != expected_header) {
        throw std::runtime_error("Unexpected replay CSV header for explicit dataset mode; "
                                 "schema columns must match exactly");
    }

    std::vector<BehaviorRow> rows;
    auto parse_unsigned = [](const std::string& cell, const char* field) -> std::uint64_t {
        if (cell.empty() || !std::all_of(cell.begin(), cell.end(),
                                         [](unsigned char c) { return std::isdigit(c) != 0; })) {
            throw std::runtime_error(std::string("invalid ") + field);
        }
        std::size_t end = 0;
        const auto value = std::stoull(cell, &end, 10);
        if (end != cell.size()) {
            throw std::runtime_error(std::string("invalid ") + field);
        }
        return value;
    };
    auto parse_signed = [](const std::string& cell, const char* field) -> int {
        const std::size_t first_digit = (!cell.empty() && (cell[0] == '-' || cell[0] == '+')) ? 1 : 0;
        if (first_digit == cell.size() ||
            !std::all_of(cell.begin() + static_cast<std::ptrdiff_t>(first_digit), cell.end(),
                         [](unsigned char c) { return std::isdigit(c) != 0; })) {
            throw std::runtime_error(std::string("invalid ") + field);
        }
        std::size_t end = 0;
        const auto value = std::stoll(cell, &end, 10);
        if (end != cell.size()) {
            throw std::runtime_error(std::string("invalid ") + field);
        }
        if (value < std::numeric_limits<int>::min() || value > std::numeric_limits<int>::max()) {
            throw std::runtime_error(std::string("out-of-range ") + field);
        }
        return static_cast<int>(value);
    };
    auto parse_binary = [&](const std::string& cell, const char* field) -> std::uint8_t {
        const int value = parse_signed(cell, field);
        if (value != 0 && value != 1) {
            throw std::runtime_error(std::string(field) + " must be binary");
        }
        return static_cast<std::uint8_t>(value);
    };
    std::uint64_t row_num = 1;
    std::uint64_t previous_seq = 0;
    bool have_previous_seq = false;
    std::unordered_map<std::uint32_t, std::uint64_t> last_timestamp_by_entity;
    while (std::getline(f, line)) {
        ++row_num;
        if (line.empty()) continue;
        const auto cells = split(line);

        if (mode == DatasetMode::Taobao && cells.size() != 9) {
            throw std::runtime_error("Malformed row " + std::to_string(row_num) +
                                     " in Taobao CSV (expected 9 columns, got " + std::to_string(cells.size()) + ")");
        }
        if (mode == DatasetMode::ULB && cells.size() != 10) {
            throw std::runtime_error("Malformed row " + std::to_string(row_num) +
                                     " in ULB CSV (expected 10 columns, got " + std::to_string(cells.size()) + ")");
        }

        BehaviorRow r{};
        try {
            const auto seq_value = parse_unsigned(cells[0], "seq");
            const auto timestamp_value = parse_unsigned(cells[1], "timestamp_ns");
            const auto user_value = parse_unsigned(cells[2], "user_id");
            const auto item_value = parse_unsigned(cells[3], "item_id");
            const auto category_value = parse_unsigned(cells[4], "category_id");
            if (user_value > std::numeric_limits<std::uint32_t>::max() ||
                item_value > std::numeric_limits<std::uint32_t>::max() ||
                category_value > std::numeric_limits<std::uint16_t>::max()) {
                throw std::runtime_error("identity field outside declared width");
            }
            r.seq = seq_value;
            r.timestamp_ns = timestamp_value;
            r.user_id = static_cast<std::uint32_t>(user_value);
            r.item_id = static_cast<std::uint32_t>(item_value);
            r.category_id = static_cast<std::uint16_t>(category_value);
            int bcode = parse_signed(cells[5], "behavior_code");

            if (have_previous_seq && r.seq <= previous_seq) {
                throw std::runtime_error("duplicate or non-increasing seq at row " +
                                         std::to_string(row_num));
            }
            if (mode == DatasetMode::Taobao) {
                if (bcode < 0 || bcode > 3) {
                    throw std::runtime_error("Unknown behavior code " + std::to_string(bcode) +
                                             " at row " + std::to_string(row_num) + " in Taobao mode");
                }
                r.behavior_code = static_cast<std::uint8_t>(bcode);
                r.amount = 0.0f;
                r.label = parse_binary(cells[6], "label");
                r.label_valid = parse_binary(cells[7], "label_valid");
                r.is_burst_period = parse_binary(cells[8], "is_burst_period");
            } else {
                // ULB mode — transaction only
                if (bcode != 0) {
                    throw std::runtime_error("Unknown behavior code " + std::to_string(bcode) +
                                             " at row " + std::to_string(row_num) + " in ULB mode (expected 0)");
                }
                r.behavior_code = 0;
                std::size_t amount_end = 0;
                r.amount = std::stof(cells[6], &amount_end);
                if (amount_end != cells[6].size()) {
                    throw std::runtime_error("invalid ULB amount");
                }
                if (!std::isfinite(r.amount) || r.amount < 0.0f) {
                    throw std::runtime_error("invalid ULB amount at row " +
                                             std::to_string(row_num));
                }
                r.label = parse_binary(cells[7], "label");
                r.label_valid = parse_binary(cells[8], "label_valid");
                r.is_burst_period = parse_binary(cells[9], "is_burst_period");
                if (r.user_id != 0 || r.item_id != 0 || r.category_id != 0) {
                    throw std::runtime_error("ULB replay cannot carry invented entity/item/category identity");
                }
            }
            if (r.label > 1 || r.label_valid > 1 || r.is_burst_period > 1) {
                throw std::runtime_error("binary metadata field out of domain at row " +
                                         std::to_string(row_num));
            }
            const auto previous_for_entity = last_timestamp_by_entity.find(r.user_id);
            if (previous_for_entity != last_timestamp_by_entity.end() &&
                r.timestamp_ns < previous_for_entity->second) {
                throw std::runtime_error("non-monotonic timestamp for entity at row " +
                                         std::to_string(row_num));
            }
        } catch (const std::exception& e) {
            throw std::runtime_error("Adapter conversion failure at row " + std::to_string(row_num) + ": " + e.what());
        }
        previous_seq = r.seq;
        have_previous_seq = true;
        last_timestamp_by_entity[r.user_id] = r.timestamp_ns;
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
        for (const auto& r : rows_) labels_.emplace(r.seq, std::make_pair(r.label, r.label_valid));
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
        const auto it = labels_.find(seq);
        if (it != labels_.end()) return it->second;
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
    std::unordered_map<std::uint64_t, std::pair<std::uint8_t,std::uint8_t>> labels_;
    ReplayMode  mode_;
    double      speed_factor_;
    std::size_t idx_{0};
};

} // namespace klstream
