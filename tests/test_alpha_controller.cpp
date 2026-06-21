// test_alpha_controller.cpp — Section 29
// Tests AlphaController (Mechanism B):
//   - slew-rate bound is never violated for an adversarial step-function input
//   - sign: rising occupancy → rising α (OPPOSITE of Project 1's load_adaptive_ema)
//   - alpha stays in [alpha_min, alpha_max] at all times

#include "klstream/feature/keyed_feature_extract_op.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>

using namespace klstream;

int main() {
    {
        // ── Test 1: rising occupancy → rising α (sign check, Decision 3) ─
        AlphaController ctrl(0.02f, 0.30f, 0.01f);
        float a0 = ctrl.current();  // 0.02 (calm)
        // Apply high occupancy for many steps
        for (int i = 0; i < 50; ++i) ctrl.update(1.0f);
        float a_final = ctrl.current();
        assert(a_final > a0);  // α must rise (sign-flipped vs Project 1)
        printf("[test_alpha_controller] test1 PASS (rising occ → rising alpha: %.4f → %.4f)\n",
               a0, a_final);
    }

    {
        // ── Test 2: slew-rate bound — step from occ=0 to occ=1 ──────────
        AlphaController ctrl(0.02f, 0.30f, /*d_alpha_max=*/0.01f);
        float prev = ctrl.current();
        for (int i = 0; i < 100; ++i) {
            float a = ctrl.update(1.0f);  // full-load step function
            float delta = std::fabs(a - prev);
            assert(delta <= 0.01f + 1e-6f);  // slew rate must not exceed d_alpha_max
            prev = a;
        }
        printf("[test_alpha_controller] test2 PASS (slew-rate bound respected)\n");
    }

    {
        // ── Test 3: alpha stays in [alpha_min, alpha_max] ─────────────────
        AlphaController ctrl(0.02f, 0.30f, 0.01f);
        for (int i = 0; i < 200; ++i) {
            float occ = (i % 2 == 0) ? 1.0f : 0.0f;
            float a = ctrl.update(occ);
            assert(a >= 0.02f - 1e-6f);
            assert(a <= 0.30f + 1e-6f);
        }
        printf("[test_alpha_controller] test3 PASS (alpha bounded [0.02, 0.30])\n");
    }

    {
        // ── Test 4: contrast with Project 1 sign (documentation test) ────
        // Project 1: α[n] = α_max - (α_max - α_min)*L → high load LOWERS α
        // Project 3: α[n] = α_min + (α_max - α_min)*L → high load RAISES α
        AlphaController ctrl(0.02f, 0.30f, 1.0f);  // large slew for instant response
        float a_calm   = ctrl.update(0.0f);  // load=0 → should be near alpha_min
        ctrl = AlphaController(0.02f, 0.30f, 1.0f);
        float a_stress = ctrl.update(1.0f);  // load=1 → should be near alpha_max
        assert(a_stress > a_calm);
        printf("[test_alpha_controller] test4 PASS (Project 3 sign: calm=%.3f, stress=%.3f)\n",
               a_calm, a_stress);
    }

    printf("[test_alpha_controller] ALL TESTS PASSED\n");
    return 0;
}
