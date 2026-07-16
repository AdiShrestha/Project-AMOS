#include <cassert>
#include <cstdio>
#include "../include/klstream/core/spsc_queue.hpp"
#include "../include/klstream/core/event.hpp"
#include "../include/klstream/core/backpressure.hpp"
#include "../include/klstream/feature/types.hpp"
#include "../include/klstream/feature/backpressure_signal.hpp"
#include "../include/klstream/feature/adaptive_feature_window_op.hpp"
#include "../include/klstream/operators/window.hpp"
#include "../include/klstream/feature/backpressure_publisher_op.hpp"
#include "../include/klstream/feature/keyed_feature_extract_op.hpp"

using namespace klstream;

void test_a_only() {
    using QRaw = SPSCQueue<Event<RawBehaviorEvent>>;
    using QFeat = SPSCQueue<Event<FeatureSnapshot>>;
    using QBatch = SPSCQueue<Event<FeatureBatch>>;

    QRaw q_raw(1024);
    QFeat q_feat(1024);
    QBatch q_batch(1024);
    BackpressureSignal signal;
    
    KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, nullptr, nullptr, 0.02f);
    AdaptiveFeatureWindowOp window("adaptive", &q_feat, &q_batch, &signal, 8, 256);
    
    int events_to_push = 300;
    for(int i=0; i<events_to_push; ++i) {
        Event<RawBehaviorEvent> ev;
        ev.key = i % 10;
        ev.seq = i;
        ev.timestamp_ns = i * 1000;
        ev.data.user_id = ev.key;
        q_raw.try_push(ev);
    }
    
    bool making_progress = true;
    while(making_progress) {
        making_progress = false;
        if(extract.tick() == OpStatus::Processed) making_progress = true;
        if(window.tick() == OpStatus::Processed) making_progress = true;
    }
    
    assert(q_batch.occupancy() > 0.0);
}

void test_b_only() {
    using QRaw = SPSCQueue<Event<RawBehaviorEvent>>;
    using QFeat = SPSCQueue<Event<FeatureSnapshot>>;
    using QBatch = SPSCQueue<Event<FeatureBatch>>;

    QRaw q_raw(1024);
    QFeat q_feat(1024);
    QBatch q_batch(1024);
    BackpressureSignal signal;
    
    BackpressurePublisherOp<QBatch> bp_pub("bp", &q_batch, &signal);
    KeyedFeatureExtractOp extract("extract", &q_raw, &q_feat, nullptr, &signal, 0.02f);
    
    auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
        FeatureBatch fb{}; 
        for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,buf[i].seq); 
        return fb;
    };
    TumblingCountWindow<FeatureSnapshot,FeatureBatch> window("fixed", &q_feat, &q_batch, 32, aggr);
    
    int events_to_push = 200;
    for(int i=0; i<events_to_push; ++i) {
        Event<RawBehaviorEvent> ev;
        ev.key = i % 10;
        ev.seq = i;
        ev.timestamp_ns = i * 1000;
        ev.data.user_id = ev.key;
        q_raw.try_push(ev);
    }
    
    bool making_progress = true;
    while(making_progress) {
        making_progress = false;
        bp_pub.tick();
        if(extract.tick() == OpStatus::Processed) making_progress = true;
        if(window.tick() == OpStatus::Processed) making_progress = true;
    }
    
    assert(q_batch.occupancy() > 0.0);
}

int main() {
    test_a_only();
    test_b_only();
    printf("[test_ablation_architectures] ALL TESTS PASSED\n");
    return 0;
}
