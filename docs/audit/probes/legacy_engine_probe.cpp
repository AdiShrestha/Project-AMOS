// Diagnostic counterexamples against legacy code. Never research evidence.
#include "klstream/core/mpmc_queue.hpp"
#include "klstream/feature/scoring_flush_op.hpp"
#include "klstream/feature/adaptive_feature_window_op.hpp"
#include "klstream/model/logistic_model.hpp"
#include <fstream>
#include <iostream>

int main(int argc, char** argv) {
    using namespace klstream;
    if (argc != 2) return 2;
    MPMCQueue<int> queue(4);
    for (int i = 0; i < 4; ++i) if (!queue.try_push(i)) return 3;
    std::cout << "full_mpmc_occupancy=" << queue.occupancy() << '\n';
    {
        std::ofstream weights(argv[1]);
        weights << "bias=0.1\nw0=1\n";
    }
    auto partial = LogisticModel::load(argv[1]);
    std::cout << "partial_model_accepted_w6=" << partial.weights[6] << '\n';
    BPFeatController controller(8, 256, 0.3, 0.7, 0.7, 1.01);
    for (int i = 0; i < 50; ++i) controller.update(1.0);
    const auto before = controller.current();
    for (int i = 0; i < 50; ++i) controller.update(0.0);
    std::cout << "growth_integer_trap_before=" << before << " after=" << controller.current() << '\n';
    ScoringFlushOp::InQueue input(4);
    ScoringFlushOp::OutQueue output(2);
    LogisticModel model;
    ScoringFlushOp scorer("probe", &input, &output, &model);
    FeatureBatch batch{};
    FeatureSnapshot a{}, b{};
    a.user_id = b.user_id = 1;
    a.event_ts_ns = 1000000000ULL;
    b.event_ts_ns = 5000000000ULL;
    batch.push_back(a, 10);
    batch.push_back(b, 30);
    Event<FeatureBatch> event{123, 0, 30, batch};
    if (!input.try_push(event)) return 4;
    scorer.tick();
    Event<ScoredResult> first{}, second{};
    if (!output.try_pop(&first)) return 5;
    scorer.tick();
    if (!output.try_pop(&second)) return 6;
    std::cout << "expected_second_seq=30 actual=" << second.seq << '\n';
    std::cout << "expected_retry_gap_seconds=4 actual=" << second.data.staleness_sec << '\n';
    std::cout << "individual_creation_timestamp_replaced=" << second.timestamp_ns << '\n';
}
