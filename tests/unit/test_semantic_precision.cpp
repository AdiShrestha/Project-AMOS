#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include "klstream/feature/user_state.hpp"

using namespace klstream;

int main() {
    EMAUserState state;
    const std::uint64_t t0 = 1'700'000'000'000'000'000ULL;
    const std::uint64_t t1 = t0 + 1'000'000'000ULL;
    state.update(1.0f, 1.0f, t0, 0, 0);
    state.update(1.0f, 1.0f, t1, 0, t0);
    float x[7]{};
    state.export_features(x, t0);
    assert(std::fabs(x[3] - (1.0f / 3600.0f)) < 1e-7f);
    assert(std::fabs(x[6] - 1.0f) < 1e-6f);
    std::cout << "epoch_precision=PASS\n";
    return 0;
}
