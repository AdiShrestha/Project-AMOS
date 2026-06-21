// test_scoring_flush_op.cpp — Section 29
// HIGH RISK: tests the multi-item Blocked-recovery pattern (has_pending_idx_)
// which differs from the standard single-pending-event idiom.
// Confirms: no event skipped or duplicated after an artificially full output queue.

#include "klstream/core/spsc_queue.hpp"
#include "klstream/core/event.hpp"
#include "klstream/feature/scoring_flush_op.hpp"
#include "klstream/model/logistic_model.hpp"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <vector>

using namespace klstream;

static FeatureBatch make_batch(std::uint32_t n) {
    FeatureBatch fb{};
    for (std::uint32_t i = 0; i < n; ++i) {
        FeatureSnapshot s{};
        s.user_id = i + 1;
        s.event_ts_ns = 1000 + i;
        s.x[0] = static_cast<float>(i) * 0.1f;
        s.label = 0; s.label_valid = 1;
        fb.push_back(s, static_cast<std::uint64_t>(i));
    }
    return fb;
}

int main() {
    {
        // ── Test 1: full batch, output queue large enough ─────────────────
        SPSCQueue<Event<FeatureBatch>>   q_in(16);
        SPSCQueue<Event<ScoredResult>>   q_out(512);
        LogisticModel model = LogisticModel::zero();
        ScoringFlushOp op("scorer", &q_in, &q_out, &model);

        const std::uint32_t W = 10;
        Event<FeatureBatch> batch_ev{1000, 0, 99, make_batch(W)};
        q_in.try_push(batch_ev);

        // Drain until idle
        for (int i = 0; i < 30; ++i) op.tick();

        // Count outputs
        int count = 0;
        Event<ScoredResult> out;
        std::vector<std::uint32_t> seen_uids;
        while (q_out.try_pop(&out)) {
            seen_uids.push_back(out.data.user_id);
            ++count;
        }
        assert(count == static_cast<int>(W));
        // All user_ids 1..W must appear exactly once
        for (std::uint32_t uid = 1; uid <= W; ++uid) {
            int found = std::count(seen_uids.begin(), seen_uids.end(), uid);
            assert(found == 1);
        }
        printf("[test_scoring_flush] test1 PASS (batch W=%u, all %u results produced)\n", W, W);
    }

    {
        // ── Test 2: Blocked-recovery — output queue fills mid-batch ───────
        // Queue capacity = 4 (smaller than batch W=10), so flush will block
        // partway through and must resume correctly on the next tick.
        SPSCQueue<Event<FeatureBatch>>   q_in(16);
        SPSCQueue<Event<ScoredResult>>   q_out(4);  // intentionally small
        LogisticModel model = LogisticModel::zero();
        ScoringFlushOp op("scorer", &q_in, &q_out, &model);

        const std::uint32_t W = 10;
        Event<FeatureBatch> batch_ev{2000, 0, 0, make_batch(W)};
        q_in.try_push(batch_ev);

        // Simulate draining the output queue as we tick, allowing progress
        std::vector<std::uint32_t> collected;
        for (int iter = 0; iter < 200 && collected.size() < W; ++iter) {
            op.tick();
            Event<ScoredResult> out;
            while (q_out.try_pop(&out)) {
                collected.push_back(out.data.user_id);
            }
        }

        assert(collected.size() == W);
        // No duplicates
        std::vector<std::uint32_t> sorted = collected;
        std::sort(sorted.begin(), sorted.end());
        for (std::uint32_t uid = 1; uid <= W; ++uid) {
            int cnt = std::count(collected.begin(), collected.end(), uid);
            assert(cnt == 1);
        }
        printf("[test_scoring_flush] test2 PASS (Blocked-recovery: no skip/dup in W=%u)\n", W);
    }

    printf("[test_scoring_flush_op] ALL TESTS PASSED\n");
    return 0;
}
