// tests/unit/test_config_parser.cpp
// Unit tests for experiment configuration parsing and fail-closed validation.

#include "klstream/core/experiment_config.hpp"
#include <cassert>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <sstream>

using namespace klstream;
namespace fs = std::filesystem;

std::string read_file(const std::string& path) {
    std::vector<std::string> candidates = {
        path,
        "../../" + path,
        "../" + path,
        "../../../" + path
    };
    for (const auto& p : candidates) {
        if (fs::exists(p)) {
            std::ifstream f(p);
            if (f.is_open()) {
                std::stringstream ss;
                ss << f.rdbuf();
                return ss.str();
            }
        }
    }
    return "";
}

int main() {
    printf("[test_config_parser] Running configuration parser tests...\n");

    // ── Test 1: Load and validate standard configs ─────────────────────────
    {
        std::string json_fixed = read_file("configs/fixed_window_v1.json");
        if (json_fixed.empty()) {
            json_fixed = R"({
  "architecture_id": "fixed_window_v1",
  "display_name": "Fixed window",
  "data_artifact_id": "resolved_after_gate",
  "model_artifact_id": "resolved_after_gate",
  "feature_schema_id": "bpfeat.feature.v1",
  "task_protocol_id": "bpfeat.prediction.v1",
  "seed": 42,
  "w_events": 32,
  "workers": 1,
  "queue_capacity": 1024,
  "warmup_events": 1000,
  "measurement_events": 10000,
  "out_dir": "results/runs/chunk05"
})";
        }
        ExperimentConfig cfg1 = parse_config_from_json_string(json_fixed);
        assert(cfg1.architecture_id == "fixed_window_v1");
        assert(cfg1.w_events == 32);
        assert(cfg1.resource_budget.workers == 1);
        assert(cfg1.resource_budget.queue_capacity == 1024);
        printf("[test_config_parser] test1: fixed_window_v1 PASS\n");
    }

    {
        std::string json_bp = read_file("configs/backpressure_only_v1.json");
        if (json_bp.empty()) {
            json_bp = R"({
  "architecture_id": "backpressure_only_v1",
  "display_name": "Backpressure only",
  "data_artifact_id": "resolved_after_gate",
  "model_artifact_id": "resolved_after_gate",
  "feature_schema_id": "bpfeat.feature.v1",
  "task_protocol_id": "bpfeat.prediction.v1",
  "seed": 42,
  "w_events": 32,
  "backpressure_threshold": 0.70,
  "workers": 1,
  "queue_capacity": 1024,
  "warmup_events": 1000,
  "measurement_events": 10000,
  "out_dir": "results/runs/chunk05"
})";
        }
        ExperimentConfig cfg2 = parse_config_from_json_string(json_bp);
        assert(cfg2.architecture_id == "backpressure_only_v1");
        assert(cfg2.backpressure_threshold > 0.0f);
        printf("[test_config_parser] test1: backpressure_only_v1 PASS\n");
    }

    {
        std::string json_th = read_file("configs/rate_throttle_v1.json");
        if (json_th.empty()) {
            json_th = R"({
  "architecture_id": "rate_throttle_v1",
  "display_name": "Rate throttle",
  "data_artifact_id": "resolved_after_gate",
  "model_artifact_id": "resolved_after_gate",
  "feature_schema_id": "bpfeat.feature.v1",
  "task_protocol_id": "bpfeat.prediction.v1",
  "seed": 42,
  "w_events": 32,
  "initial_rate": 1000.0,
  "recovery_rule": "multiplicative_increase",
  "workers": 1,
  "queue_capacity": 1024,
  "warmup_events": 1000,
  "measurement_events": 10000,
  "out_dir": "results/runs/chunk05"
})";
        }
        ExperimentConfig cfg3 = parse_config_from_json_string(json_th);
        assert(cfg3.architecture_id == "rate_throttle_v1");
        assert(cfg3.initial_rate > 0.0f);
        assert(!cfg3.recovery_rule.empty());
        printf("[test_config_parser] test1: rate_throttle_v1 PASS\n");
    }

    {
        std::string json_ad = read_file("configs/bpfeat_adaptive_v1.json");
        if (json_ad.empty()) {
            json_ad = R"({
  "architecture_id": "bpfeat_adaptive_v1",
  "display_name": "BPFeat adaptive",
  "data_artifact_id": "resolved_after_gate",
  "model_artifact_id": "resolved_after_gate",
  "feature_schema_id": "bpfeat.feature.v1",
  "task_protocol_id": "bpfeat.prediction.v1",
  "seed": 42,
  "w_min": 8,
  "w_max": 256,
  "alpha_min": 0.02,
  "alpha_max": 0.30,
  "slew_rate": 0.01,
  "occ_low": 0.30,
  "occ_high": 0.70,
  "shrink_factor": 0.70,
  "grow_factor": 1.15,
  "update_cadence": "batch-boundary",
  "workers": 1,
  "queue_capacity": 1024,
  "warmup_events": 1000,
  "measurement_events": 10000,
  "out_dir": "results/runs/chunk05"
})";
        }
        ExperimentConfig cfg4 = parse_config_from_json_string(json_ad);
        assert(cfg4.architecture_id == "bpfeat_adaptive_v1");
        assert(cfg4.w_min < cfg4.w_max);
        assert(cfg4.alpha_min < cfg4.alpha_max);
        assert(cfg4.update_cadence == "batch-boundary");
        printf("[test_config_parser] test1: bpfeat_adaptive_v1 PASS\n");
    }

    // ── Test 2: Poison case — Unknown architecture ID ─────────────────────
    {
        bool caught = false;
        try {
            ExperimentConfig bad_cfg;
            bad_cfg.architecture_id = "unregistered_magical_arch_v99";
            validate_experiment_config(bad_cfg);
        } catch (const ConfigValidationError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_config_parser] test2: unknown architecture fail-closed PASS\n");
    }

    // ── Test 3: Poison case — Missing required throttle parameter ─────────
    {
        bool caught = false;
        try {
            ExperimentConfig bad_cfg;
            bad_cfg.architecture_id = "rate_throttle_v1";
            bad_cfg.initial_rate = 0.0f; // invalid!
            validate_experiment_config(bad_cfg);
        } catch (const ConfigValidationError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_config_parser] test3: missing throttle rate fail-closed PASS\n");
    }

    // ── Test 4: Poison case — Asymmetric or invalid queue capacity ────────
    {
        bool caught = false;
        try {
            ExperimentConfig bad_cfg;
            bad_cfg.architecture_id = "fixed_window_v1";
            bad_cfg.resource_budget.queue_capacity = 1000; // not a power of 2!
            validate_experiment_config(bad_cfg);
        } catch (const ConfigValidationError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_config_parser] test4: invalid queue capacity fail-closed PASS\n");
    }

    // ── Test 5: Poison case — Invalid schema ID ───────────────────────────
    {
        bool caught = false;
        try {
            ExperimentConfig bad_cfg;
            bad_cfg.architecture_id = "fixed_window_v1";
            bad_cfg.feature_schema_id = "unsupported.schema.v2";
            validate_experiment_config(bad_cfg);
        } catch (const ConfigValidationError& e) {
            caught = true;
        }
        assert(caught);
        printf("[test_config_parser] test5: invalid feature schema fail-closed PASS\n");
    }

    printf("[test_config_parser] ALL TESTS PASSED\n");
    return 0;
}
