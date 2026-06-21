// test_bpfeat_controller.cpp — Section 29
// Tests BPFeatController with synthetic occupancy traces.
// Confirms: shrink-on-high, grow-on-low, deadband-holds-steady,
// clamping at w_min/w_max, direction_changes() correctness.

#include "klstream/feature/adaptive_feature_window_op.hpp"
#include <cassert>
#include <cstdio>
#include <cmath>

using namespace klstream;

int main() {
    {
        // ── Test 1: shrink on high occupancy ──────────────────────────────
        BPFeatController ctrl(/*w_min=*/8, /*w_max=*/256, 0.30, 0.70, 0.70, 1.15);
        assert(ctrl.current() == 256u);  // starts at w_max

        std::uint32_t w = ctrl.update(0.80);  // above occ_high
        assert(w < 256u);
        assert(w >= 8u);
        // Expected: floor(256 * 0.70) = 179
        assert(w == 179u);
        printf("[test_bpfeat_controller] test1 PASS (shrink on high occupancy)\n");
    }

    {
        // ── Test 2: grow on low occupancy ────────────────────────────────
        BPFeatController ctrl(8, 256, 0.30, 0.70, 0.70, 1.15);
        // Force to a mid value by shrinking first
        ctrl.update(0.80);  // 179
        ctrl.update(0.80);  // 125
        ctrl.update(0.80);  // 87
        std::uint32_t w_before = ctrl.current();
        std::uint32_t w_after  = ctrl.update(0.10);  // below occ_low
        assert(w_after > w_before);
        printf("[test_bpfeat_controller] test2 PASS (grow on low occupancy)\n");
    }

    {
        // ── Test 3: deadband — neither shrink nor grow ───────────────────
        BPFeatController ctrl(8, 256, 0.30, 0.70, 0.70, 1.15);
        ctrl.update(0.80); // shrink to 179
        std::uint32_t w1 = ctrl.current();
        std::uint32_t w2 = ctrl.update(0.50); // in deadband [0.30, 0.70]
        assert(w1 == w2);
        printf("[test_bpfeat_controller] test3 PASS (deadband holds steady)\n");
    }

    {
        // ── Test 4: clamp at w_min ───────────────────────────────────────
        BPFeatController ctrl(8, 256, 0.30, 0.70, 0.70, 1.15);
        for (int i = 0; i < 30; ++i) ctrl.update(0.90);  // keep shrinking
        assert(ctrl.current() == 8u);  // must clamp at w_min
        printf("[test_bpfeat_controller] test4 PASS (clamped at w_min=%u)\n", ctrl.current());
    }

    {
        // ── Test 5: clamp at w_max ───────────────────────────────────────
        BPFeatController ctrl(8, 256, 0.30, 0.70, 0.70, 1.15);
        ctrl.update(0.90); // shrink
        for (int i = 0; i < 30; ++i) ctrl.update(0.10); // grow back
        assert(ctrl.current() == 256u);
        printf("[test_bpfeat_controller] test5 PASS (clamped at w_max=%u)\n", ctrl.current());
    }

    {
        // ── Test 6: direction_changes on oscillating trace ───────────────
        BPFeatController ctrl(8, 256, 0.30, 0.70, 0.70, 1.15);
        // High → low → high → low: should see at least 3 direction changes
        ctrl.update(0.90); // dir=-1
        ctrl.update(0.10); // dir=+1, change #1
        ctrl.update(0.90); // dir=-1, change #2
        ctrl.update(0.10); // dir=+1, change #3
        assert(ctrl.direction_changes() >= 3u);
        printf("[test_bpfeat_controller] test6 PASS (direction_changes=%llu)\n",
               (unsigned long long)ctrl.direction_changes());
    }

    printf("[test_bpfeat_controller] ALL TESTS PASSED\n");
    return 0;
}
