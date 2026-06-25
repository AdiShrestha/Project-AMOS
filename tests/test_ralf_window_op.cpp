#include <cassert>
#include <cstdio>
#include "../include/klstream/core/spsc_queue.hpp"
#include "../include/klstream/core/event.hpp"
#include "../include/klstream/core/backpressure.hpp"
#include "../include/klstream/feature/types.hpp"
#include "../include/klstream/feature/ralf_window_op.hpp"

using namespace klstream;

int main() {
    using InQueue = SPSCQueue<Event<FeatureSnapshot>>;
    using OutQueue = SPSCQueue<Event<FeatureBatch>>;

    InQueue q_in(1024);
    OutQueue q_out(1024);
    
    // window=4, fraction=0.5 -> budget_k=2
    RALFWindowOp op("ralf_test", &q_in, &q_out, 4, 0.5);

    auto push_snapshot = [&](uint32_t uid, float ema, uint64_t ts) {
        Event<FeatureSnapshot> ev;
        ev.key = uid;
        ev.seq = uid * 100;
        ev.timestamp_ns = ts;
        ev.data.user_id = uid;
        ev.data.x[0] = ema;
        q_in.try_push(ev);
    };

    push_snapshot(1, 0.8f, 1000);
    push_snapshot(2, 0.2f, 2000);
    push_snapshot(3, 0.9f, 3000);
    push_snapshot(4, 0.1f, 4000);

    for (int i = 0; i < 4; i++) {
        assert(op.tick() == OpStatus::Processed);
    }
    
    int popped = 0;
    Event<FeatureBatch> out_ev;
    bool has_user_1 = false;
    bool has_user_3 = false;
    
    while (q_out.try_pop(&out_ev)) {
        popped++;
        assert(out_ev.data.count == 1);
        uint32_t published_uid = out_ev.data.items[0].user_id;
        if (published_uid == 1) has_user_1 = true;
        if (published_uid == 3) has_user_3 = true;
    }
    
    assert(popped == 2);
    assert(has_user_1);
    assert(has_user_3);
    
    push_snapshot(1, 0.81f, 5000);
    push_snapshot(2, 0.4f, 6000);
    push_snapshot(3, 0.91f, 7000);
    push_snapshot(4, 0.3f, 8000);
    
    for (int i = 0; i < 4; i++) {
        assert(op.tick() == OpStatus::Processed);
    }
    
    popped = 0;
    bool has_user_2 = false;
    bool has_user_4 = false;
    while (q_out.try_pop(&out_ev)) {
        popped++;
        assert(out_ev.data.count == 1);
        uint32_t published_uid = out_ev.data.items[0].user_id;
        if (published_uid == 2) has_user_2 = true;
        if (published_uid == 4) has_user_4 = true;
    }
    
    assert(popped == 2);
    assert(has_user_2);
    assert(has_user_4);
    
    printf("[test_ralf_window_op] ALL TESTS PASSED\n");
    return 0;
}
