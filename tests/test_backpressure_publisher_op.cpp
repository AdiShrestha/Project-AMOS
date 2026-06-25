#include <cassert>
#include <cstdio>
#include "../include/klstream/core/spsc_queue.hpp"
#include "../include/klstream/core/event.hpp"
#include "../include/klstream/core/backpressure.hpp"
#include "../include/klstream/feature/types.hpp"
#include "../include/klstream/feature/backpressure_publisher_op.hpp"

using namespace klstream;

int main() {
    using Queue = SPSCQueue<Event<FeatureBatch>>;
    Queue q(100);
    BackpressureSignal signal;
    
    BackpressurePublisherOp<Queue> op("bp_pub", &q, &signal);
    
    assert(op.tick() == OpStatus::Idle);
    assert(signal.load() == 0.0f);
    
    for(int i=0; i<50; ++i) {
        Event<FeatureBatch> ev;
        q.try_push(ev);
    }
    
    assert(op.tick() == OpStatus::Idle);
    assert(signal.load() > 0.0f);
    
    assert(q.occupancy_approx() == 50);
    
    printf("[test_backpressure_publisher_op] ALL TESTS PASSED\n");
    return 0;
}
