// tests/unit/test_harness_registry.cpp
// Unit tests for RegistryHarness topology building, execution, counter conservation, and atomic finalization.

#include "klstream/core/registry_harness.hpp"
#include <cassert>
#include <cstdio>
#include <filesystem>

using namespace klstream;
namespace fs = std::filesystem;

int main() {
    printf("[test_harness_registry] Running registry harness tests...\n");

    // Synthetic behavior rows
    std::vector<BehaviorRow> rows;
    for (std::uint64_t i = 1; i <= 200; ++i) {
        BehaviorRow r{};
        r.seq = i;
        r.user_id = static_cast<std::uint32_t>(i % 10 + 1);
        r.timestamp_ns = 1700000000000000000ULL + i * 1000000ULL;
        r.item_id = static_cast<std::uint32_t>(100 + (i % 20));
        r.category_id = static_cast<std::uint16_t>(5);
        r.behavior_code = static_cast<std::uint8_t>(i % 4);
        r.amount = 0.0f;
        r.label = static_cast<std::uint8_t>(i % 2);
        r.label_valid = 1;
        r.is_burst_period = 0;
        rows.push_back(r);
    }

    LogisticModel model; // default weights

    // ── Test 1: Empty dataset error ────────────────────────────────────────
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "fixed_window_v1";
        RegistryHarness harness(cfg);
        bool caught = false;
        try {
            std::vector<BehaviorRow> empty_rows;
            harness.load_artifacts(empty_rows, model);
        } catch (const ArtifactLoadError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_harness_registry] test1: empty dataset error PASS\n");
    }

    // ── Test 2: Execution without load error ────────────────────────────────
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "fixed_window_v1";
        RegistryHarness harness(cfg);
        bool caught = false;
        try {
            harness.execute();
        } catch (const ExecutionError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_harness_registry] test2: uninitialized execution error PASS\n");
    }

    // ── Test 3: Fixed window execution and exact counter accounting ────────
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "fixed_window_v1";
        cfg.w_events = 16;
        cfg.out_dir = "/tmp/bpfeat_harness_test_out";
        fs::create_directories(cfg.out_dir);

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.status == "COMPLETED");
        assert(ident.counters.events_read == rows.size());
        assert(ident.counters.events_extracted == rows.size());
        assert(ident.counters.events_sunk == rows.size());
        assert(ident.counters.windows_emitted > 0);
        assert(ident.counters.final_w == 16);
        assert(fs::exists(ident.result_file));

        // Ensure no leftover tmp files
        for (const auto& entry : fs::directory_iterator(cfg.out_dir)) {
            std::string name = entry.path().filename().string();
            assert(name.find("tmp_") != 0);
        }

        fs::remove_all(cfg.out_dir);
        printf("[test_harness_registry] test3: fixed_window execution & counter accounting PASS\n");
    }

    // ── Test 4: BPFeat adaptive execution ──────────────────────────────────
    {
        ExperimentConfig cfg;
        cfg.architecture_id = "bpfeat_adaptive_v1";
        cfg.w_min = 8;
        cfg.w_max = 64;
        cfg.out_dir = "/tmp/bpfeat_harness_test_adaptive";
        fs::create_directories(cfg.out_dir);

        RegistryHarness harness(cfg);
        harness.load_artifacts(rows, model);
        RunIdentity ident = harness.execute();

        assert(ident.status == "COMPLETED");
        assert(ident.counters.events_read == rows.size());
        assert(ident.counters.events_sunk == rows.size());
        assert(ident.counters.final_w >= 8 && ident.counters.final_w <= 64);
        assert(fs::exists(ident.result_file));

        fs::remove_all(cfg.out_dir);
        printf("[test_harness_registry] test4: bpfeat_adaptive execution PASS\n");
    }

    printf("[test_harness_registry] ALL TESTS PASSED\n");
    return 0;
}
