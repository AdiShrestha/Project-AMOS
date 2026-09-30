#pragma once
// include/klstream/core/experiment_config.hpp
// Typed experiment configuration, architecture registry mapping, and fail-closed validation.

#include "config.hpp"
#include "../feature/types.hpp"
#include <cstdint>
#include <cstddef>
#include <string>
#include <vector>
#include <stdexcept>
#include <sstream>
#include <algorithm>

namespace klstream {

// ── Typed Error Categories ──────────────────────────────────────────────────
class ConfigValidationError : public std::runtime_error {
public:
    explicit ConfigValidationError(const std::string& msg) : std::runtime_error("ConfigValidationError: " + msg) {}
};

class ArtifactLoadError : public std::runtime_error {
public:
    explicit ArtifactLoadError(const std::string& msg) : std::runtime_error("ArtifactLoadError: " + msg) {}
};

class TopologyConstructionError : public std::runtime_error {
public:
    explicit TopologyConstructionError(const std::string& msg) : std::runtime_error("TopologyConstructionError: " + msg) {}
};

class ExecutionError : public std::runtime_error {
public:
    explicit ExecutionError(const std::string& msg) : std::runtime_error("ExecutionError: " + msg) {}
};

// ── Architecture Enum ───────────────────────────────────────────────────────
enum class ArchitectureType {
    FixedWindow,
    BackpressureOnly,
    RateThrottle,
    BPFeatAdaptive,
    Unknown
};

inline ArchitectureType parse_architecture_id(const std::string& id) {
    if (id == "fixed_window_v1") return ArchitectureType::FixedWindow;
    if (id == "backpressure_only_v1") return ArchitectureType::BackpressureOnly;
    if (id == "rate_throttle_v1") return ArchitectureType::RateThrottle;
    if (id == "bpfeat_adaptive_v1") return ArchitectureType::BPFeatAdaptive;
    return ArchitectureType::Unknown;
}

inline std::string to_string(ArchitectureType arch) {
    switch (arch) {
        case ArchitectureType::FixedWindow: return "fixed_window_v1";
        case ArchitectureType::BackpressureOnly: return "backpressure_only_v1";
        case ArchitectureType::RateThrottle: return "rate_throttle_v1";
        case ArchitectureType::BPFeatAdaptive: return "bpfeat_adaptive_v1";
        default: return "unknown";
    }
}

// ── Resource Budget ────────────────────────────────────────────────────────
struct ResourceBudget {
    int workers{1};
    std::size_t queue_capacity{1024};
    std::string cpu_policy{"declared_at_run"};
    std::string memory_budget{"declared_at_run"};
};

// ── Experiment Configuration ────────────────────────────────────────────────
struct ExperimentConfig {
    std::string architecture_id;
    std::string display_name;
    std::string data_artifact_id{"resolved_after_gate"};
    std::string model_artifact_id{"resolved_after_gate"};
    std::string feature_schema_id{"bpfeat.feature.v1"};
    std::string task_protocol_id{"bpfeat.prediction.v1"};
    
    std::uint32_t seed{42};
    DatasetMode dataset_mode{DatasetMode::Taobao};
    
    // Window and controller parameters
    std::uint32_t w_events{32};
    float backpressure_threshold{0.70f};
    
    // Rate throttle specific
    float initial_rate{1000.0f};
    std::string recovery_rule{"multiplicative_increase"};
    
    // BPFeat adaptive specific
    std::uint32_t w_min{8};
    std::uint32_t w_max{256};
    float alpha_min{0.02f};
    float alpha_max{0.30f};
    float slew_rate{0.01f};
    float occ_low{0.30f};
    float occ_high{0.70f};
    float shrink_factor{0.70f};
    float grow_factor{1.15f};
    std::string update_cadence{"batch-boundary"};
    
    // Resource envelope
    ResourceBudget resource_budget{};
    
    // Event count envelopes
    std::uint64_t warmup_events{1000};
    std::uint64_t measurement_events{10000};
    std::uint64_t scoring_delay_us{0};
    float ulb_max_amount{1.0f};
    
    // Output configuration
    std::string out_dir{"results/runs/chunk05"};
};

// ── Fail-Closed Config Validator ────────────────────────────────────────────
inline void validate_experiment_config(const ExperimentConfig& cfg) {
    ArchitectureType arch = parse_architecture_id(cfg.architecture_id);
    if (arch == ArchitectureType::Unknown) {
        throw ConfigValidationError("Unknown or forbidden architecture_id: '" + cfg.architecture_id + "'");
    }

    if (cfg.feature_schema_id != "bpfeat.feature.v1") {
        throw ConfigValidationError("Invalid feature_schema_id: expected 'bpfeat.feature.v1', got '" + cfg.feature_schema_id + "'");
    }
    if (cfg.task_protocol_id != "bpfeat.prediction.v1") {
        throw ConfigValidationError("Invalid task_protocol_id: expected 'bpfeat.prediction.v1', got '" + cfg.task_protocol_id + "'");
    }
    if (cfg.data_artifact_id.empty()) {
        throw ConfigValidationError("data_artifact_id cannot be empty");
    }
    if (cfg.model_artifact_id.empty()) {
        throw ConfigValidationError("model_artifact_id cannot be empty");
    }

    // Common resource envelope symmetry check
    if (cfg.resource_budget.workers <= 0) {
        throw ConfigValidationError("Worker count must be positive");
    }
    if (cfg.resource_budget.queue_capacity < 16 || (cfg.resource_budget.queue_capacity & (cfg.resource_budget.queue_capacity - 1)) != 0) {
        throw ConfigValidationError("Queue capacity must be a power of 2 and >= 16");
    }

    // Architecture-specific parameter validation
    switch (arch) {
        case ArchitectureType::FixedWindow:
            if (cfg.w_events == 0) {
                throw ConfigValidationError("fixed_window_v1 requires positive w_events");
            }
            break;

        case ArchitectureType::BackpressureOnly:
            if (cfg.backpressure_threshold <= 0.0f || cfg.backpressure_threshold >= 1.0f) {
                throw ConfigValidationError("backpressure_only_v1 requires backpressure_threshold in (0, 1)");
            }
            if (cfg.w_events == 0) {
                throw ConfigValidationError("backpressure_only_v1 requires positive w_events");
            }
            break;

        case ArchitectureType::RateThrottle:
            if (cfg.initial_rate <= 0.0f) {
                throw ConfigValidationError("rate_throttle_v1 requires positive initial_rate");
            }
            if (cfg.recovery_rule.empty()) {
                throw ConfigValidationError("rate_throttle_v1 requires explicit recovery_rule");
            }
            if (cfg.w_events == 0) {
                throw ConfigValidationError("rate_throttle_v1 requires positive w_events");
            }
            break;

        case ArchitectureType::BPFeatAdaptive:
            if (cfg.w_min == 0 || cfg.w_max <= cfg.w_min) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires 0 < w_min < w_max");
            }
            if (cfg.alpha_min <= 0.0f || cfg.alpha_max <= cfg.alpha_min) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires 0 < alpha_min < alpha_max");
            }
            if (cfg.slew_rate <= 0.0f) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires positive slew_rate");
            }
            if (cfg.occ_low <= 0.0f || cfg.occ_high <= cfg.occ_low || cfg.occ_high >= 1.0f) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires 0 < occ_low < occ_high < 1");
            }
            if (cfg.shrink_factor <= 0.0f || cfg.shrink_factor >= 1.0f) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires shrink_factor in (0, 1)");
            }
            if (cfg.grow_factor <= 1.0f) {
                throw ConfigValidationError("bpfeat_adaptive_v1 requires grow_factor > 1.0");
            }
            if (cfg.update_cadence != "batch-boundary") {
                throw ConfigValidationError("bpfeat_adaptive_v1 update_cadence must be 'batch-boundary'");
            }
            break;

        default:
            throw ConfigValidationError("Unhandled architecture validation");
    }
}

// ── Lightweight Key-Value / JSON Config Parser ─────────────────────────────
inline std::string trim_str(const std::string& s) {
    auto start = s.find_first_not_of(" \t\r\n\"'");
    if (start == std::string::npos) return "";
    auto end = s.find_last_not_of(" \t\r\n\"'");
    return s.substr(start, end - start + 1);
}

inline ExperimentConfig parse_config_from_json_string(const std::string& json_str) {
    ExperimentConfig cfg;
    std::istringstream stream(json_str);
    std::string line;

    while (std::getline(stream, line)) {
        auto colon = line.find(':');
        if (colon == std::string::npos) continue;

        std::string key = trim_str(line.substr(0, colon));
        std::string val = trim_str(line.substr(colon + 1));
        if (val.empty()) continue;
        if (val.back() == ',') val.pop_back();
        val = trim_str(val);

        if (key == "architecture_id") cfg.architecture_id = val;
        else if (key == "display_name") cfg.display_name = val;
        else if (key == "data_artifact_id") cfg.data_artifact_id = val;
        else if (key == "model_artifact_id") cfg.model_artifact_id = val;
        else if (key == "feature_schema_id") cfg.feature_schema_id = val;
        else if (key == "task_protocol_id") cfg.task_protocol_id = val;
        else if (key == "seed") cfg.seed = static_cast<std::uint32_t>(std::stoul(val));
        else if (key == "w_events") cfg.w_events = static_cast<std::uint32_t>(std::stoul(val));
        else if (key == "backpressure_threshold") cfg.backpressure_threshold = std::stof(val);
        else if (key == "initial_rate") cfg.initial_rate = std::stof(val);
        else if (key == "recovery_rule") cfg.recovery_rule = val;
        else if (key == "w_min") cfg.w_min = static_cast<std::uint32_t>(std::stoul(val));
        else if (key == "w_max") cfg.w_max = static_cast<std::uint32_t>(std::stoul(val));
        else if (key == "alpha_min") cfg.alpha_min = std::stof(val);
        else if (key == "alpha_max") cfg.alpha_max = std::stof(val);
        else if (key == "slew_rate") cfg.slew_rate = std::stof(val);
        else if (key == "occ_low") cfg.occ_low = std::stof(val);
        else if (key == "occ_high") cfg.occ_high = std::stof(val);
        else if (key == "shrink_factor") cfg.shrink_factor = std::stof(val);
        else if (key == "grow_factor") cfg.grow_factor = std::stof(val);
        else if (key == "update_cadence") cfg.update_cadence = val;
        else if (key == "workers") cfg.resource_budget.workers = std::stoi(val);
        else if (key == "queue_capacity") cfg.resource_budget.queue_capacity = static_cast<std::size_t>(std::stoull(val));
        else if (key == "warmup_events") cfg.warmup_events = std::stoull(val);
        else if (key == "measurement_events") cfg.measurement_events = std::stoull(val);
        else if (key == "out_dir") cfg.out_dir = val;
    }

    validate_experiment_config(cfg);
    return cfg;
}

} // namespace klstream
