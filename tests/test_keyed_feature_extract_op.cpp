// test_keyed_feature_extract_op.cpp — Section 29
// Tests:
//   - Per-user state isolation: two interleaved users' EMAs don't leak
//   - ULB degenerate single-key path (user_id=0) behaves like general path
//   - Basic output shape (each input event produces exactly one FeatureSnapshot)

#include "klstream/core/spsc_queue.hpp"
#include "klstream/core/event.hpp"
#include "klstream/feature/keyed_feature_extract_op.hpp"
#include <cassert>
#include <cstdio>

using namespace klstream;

// Helper: push a RawBehaviorEvent into q_raw
static void push_raw(SPSCQueue<Event<RawBehaviorEvent>>& q,
                     std::uint32_t uid, std::uint8_t bc, std::uint64_t ts, std::uint64_t seq) {
    Event<RawBehaviorEvent> ev;
    ev.timestamp_ns = ts;
    ev.key  = uid;
    ev.seq  = seq;
    ev.data = RawBehaviorEvent{uid, 1000, /*item*/1, /*cat*/0, bc, /*amount*/0.0f};
    bool ok = q.try_push(ev);
    assert(ok && "push_raw: queue full");
}

int main() {
    {
        // ── Test 1: per-user EMA isolation ────────────────────────────────
        // Two users interleaved: each user's ema_engagement should differ
        // because they have different behavior_codes.
        SPSCQueue<Event<RawBehaviorEvent>>  q_in(256);
        SPSCQueue<Event<FeatureSnapshot>>   q_out(256);
        KeyedFeatureExtractOp op("ext", &q_in, &q_out, nullptr, nullptr, 0.30f);

        // User 1: only 'buy' (bc=3, weight=5), 5 events
        for (int i = 0; i < 5; ++i)
            push_raw(q_in, 1, 3, 1000000000ULL * (i+1), i);
        // User 2: only 'pv'  (bc=0, weight=1), 5 events
        for (int i = 0; i < 5; ++i)
            push_raw(q_in, 2, 0, 1000000000ULL * (i+1), i+5);

        // Drain 10 ticks
        for (int i = 0; i < 10; ++i) op.tick();

        // Read snapshots and separate by user
        float ema_u1 = -1.0f, ema_u2 = -1.0f;
        Event<FeatureSnapshot> snap;
        int count = 0;
        while (q_out.try_pop(&snap)) {
            if (snap.data.user_id == 1) ema_u1 = snap.data.x[0];
            if (snap.data.user_id == 2) ema_u2 = snap.data.x[0];
            ++count;
        }
        assert(count == 10);  // one snapshot per event
        assert(ema_u1 > ema_u2 + 0.01f);  // buy-heavy user should have higher EMA
        printf("[test_keyed] test1 PASS (user isolation: ema_u1=%.4f > ema_u2=%.4f)\n",
               ema_u1, ema_u2);
    }

    {
        // ── Test 2: ULB degenerate single-key (user_id=0) ─────────────────
        SPSCQueue<Event<RawBehaviorEvent>> q_in(256);
        SPSCQueue<Event<FeatureSnapshot>>  q_out(256);
        KeyedFeatureExtractOp op("ext", &q_in, &q_out, nullptr, nullptr, 0.10f);

        for (int i = 0; i < 5; ++i) {
            Event<RawBehaviorEvent> ev;
            ev.timestamp_ns = 1000000000ULL * (i+1);
            ev.key  = 0;
            ev.seq  = static_cast<std::uint64_t>(i);
            ev.data = RawBehaviorEvent{0, 1000, 0, 0, 0, /*amount*/100.0f + i};
            q_in.try_push(ev);
        }
        for (int i = 0; i < 5; ++i) op.tick();
        assert(op.user_count() == 1u);  // exactly one entry in the hash map

        Event<FeatureSnapshot> snap;
        int count = 0;
        while (q_out.try_pop(&snap)) {
            assert(snap.data.user_id == 0);
            ++count;
        }
        assert(count == 5);
        printf("[test_keyed] test2 PASS (ULB degenerate single key, user_count=%zu)\n",
               op.user_count());
    }

    {
        // ── Test 3: one FeatureSnapshot per input event ───────────────────
        SPSCQueue<Event<RawBehaviorEvent>> q_in(256);
        SPSCQueue<Event<FeatureSnapshot>>  q_out(256);
        KeyedFeatureExtractOp op("ext", &q_in, &q_out, nullptr, nullptr, 0.10f);

        const int N = 20;
        for (int i = 0; i < N; ++i)
            push_raw(q_in, static_cast<std::uint32_t>(i % 3 + 1),
                     static_cast<std::uint8_t>(i % 4),
                     1000000000ULL * (i+1), static_cast<std::uint64_t>(i));
        for (int i = 0; i < N; ++i) op.tick();

        int count = 0;
        Event<FeatureSnapshot> snap;
        while (q_out.try_pop(&snap)) ++count;
        assert(count == N);
        printf("[test_keyed] test3 PASS (%d input events → %d snapshots)\n", N, count);
    }

    printf("[test_keyed_feature_extract_op] ALL TESTS PASSED\n");
    return 0;
}
