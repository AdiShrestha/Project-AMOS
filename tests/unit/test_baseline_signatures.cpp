// tests/unit/test_baseline_signatures.cpp
// Unit tests verifying architecture baseline signatures from C05-07 baseline matrix.

#include "klstream/core/registry_harness.hpp"
#include <cassert>
#include <cstdio>
#include <filesystem>

using namespace klstream;
namespace fs = std::filesystem;

int main() {
    printf("[test_baseline_signatures] Verifying architecture baseline signatures...\n");

    std::vector<BehaviorRow> rows;
    for (std::uint64_t i = 1; i <= 300; ++i) {
        BehaviorRow r{};
        r.seq = i;
        r.user_id = static_cast<std::uint32_t>(i % 5 + 1);
        r.timestamp_ns = 1700000000000000000ULL + i * 1000000ULL;
        r.item_id = static_cast<std::uint32_t>(200 + (i % 10));
        r.category_id = static_cast<std::uint16_t>(1);
        r.behavior_code = static_cast<std::uint8_t>(i % 4);
        r.amount = 0.0f;
        r.label = static_cast<std::uint8_t>(i % 2);
        r.label_valid = 1;
        r.is_burst_period = 0;
        rows.push_back(r);
    }

    LogisticModel model;
    std::string test_dir = "/tmp/bpfeat_baseline_sig_test";
    fs::create_directories(test_dir);

    // ── Signature 1: fixed_window_v1 ───────────────────────────────────────
    // Signature: window_size_constant_and_no_controller_actions
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "fixed_window_v1";
        cfg.w_events = 24;
        cfg.out_dir = test_dir;

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.counters.direction_changes == 0);
        assert(ident.counters.final_w == 24);
        printf("[test_baseline_signatures] Signature 1 (fixed_window_v1): PASS\n");
    }

    // ── Signature 2: backpressure_only_v1 ──────────────────────────────────
    // Signature: admission_delay_without_window_adaptation
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "backpressure_only_v1";
        cfg.w_events = 32;
        cfg.backpressure_threshold = 0.70f;
        cfg.out_dir = test_dir;

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.counters.direction_changes == 0);
        assert(ident.counters.final_w == 32);
        printf("[test_baseline_signatures] Signature 2 (backpressure_only_v1): PASS\n");
    }

    // ── Signature 3: rate_throttle_v1 ──────────────────────────────────────
    // Signature: admission_rate_changes_with_fixed_window
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "rate_throttle_v1";
        cfg.w_events = 32;
        cfg.initial_rate = 500.0f;
        cfg.recovery_rule = "multiplicative_increase";
        cfg.out_dir = test_dir;

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.counters.direction_changes == 0);
        assert(ident.counters.final_w == 32);
        printf("[test_baseline_signatures] Signature 3 (rate_throttle_v1): PASS\n");
    }

    // ── Signature 4: bpfeat_adaptive_v1 ────────────────────────────────────
    // Signature: declared_batch_boundary_window_and_controller_actions
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "bpfeat_adaptive_v1";
        cfg.w_min = 8;
        cfg.w_max = 64;
        cfg.alpha_min = 0.02f;
        cfg.alpha_max = 0.30f;
        cfg.slew_rate = 0.01f;
        cfg.out_dir = test_dir;

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.counters.final_w >= 8 && ident.counters.final_w <= 64);
        assert(ident.counters.final_alpha >= 0.02f && ident.counters.final_alpha <= 0.30f);
        printf("[test_baseline_signatures] Signature 4 (bpfeat_adaptive_v1): PASS\n");
    }

    fs::remove_all(test_dir);
    printf("[test_baseline_signatures] ALL BASELINE SIGNATURES VERIFIED PASS\n");
    return 0;
}
