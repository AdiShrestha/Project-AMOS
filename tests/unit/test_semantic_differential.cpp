#include <cassert>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iomanip>
#include "klstream/feature/keyed_feature_extract_op.hpp"

using namespace klstream;

int main() {
    using InQ = SPSCQueue<Event<RawBehaviorEvent>>;
    using OutQ = SPSCQueue<Event<FeatureSnapshot>>;
    InQ input(16384); OutQ output(16384);
    KeyedFeatureExtractOp op("semantic", &input, &output, nullptr, nullptr, 0.10f);
    constexpr std::uint64_t n = 10000;
    for (std::uint64_t i = 0; i < n; ++i) {
        RawBehaviorEvent raw{static_cast<std::uint32_t>((i % 17) + 1),
            1'700'000'000'000'000'000ULL + i * 1'000'000ULL + (i % 3),
            static_cast<std::uint32_t>(i % 1000), static_cast<std::uint16_t>(i % 10),
            static_cast<std::uint8_t>(i % 4), 0.0f, 0};
        Event<RawBehaviorEvent> ev{raw.event_ts_ns, raw.user_id, i, raw};
        assert(input.try_push(ev));
    }
    input.close();
    std::ofstream out("/tmp/bpfeat-semantic-cpp.csv");
    assert(out);
    std::uint64_t count = 0;
    while (count < n) {
        const auto status = op.tick();
        Event<FeatureSnapshot> ev;
        if (output.try_pop(&ev)) {
            out << ev.seq << ',' << ev.data.user_id << ',' << ev.data.event_ts_ns;
            for (float x : ev.data.x) out << ',' << std::setprecision(9) << x;
            out << '\n';
            ++count;
        } else if (status == OpStatus::Closed) break;
    }
    assert(count == n);
    std::cout << "semantic_cpp_events=" << count << "\n";
    return 0;
}
