#include "bpfeat/pipeline.hpp"
#include "bpfeat/replay.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>

namespace fs = std::filesystem;
int main(int argc, char** argv) {
    try {
        const std::set<std::string> allowed = {"--events", "--model", "--out-dir", "--mode", "--batch-size",
            "--batch-min", "--batch-max", "--alpha", "--alpha-min", "--alpha-max", "--alpha-delta",
            "--occupancy-gain", "--low", "--high", "--shrink", "--grow", "--feature-slots", "--batch-slots",
            "--max-keys", "--timeout-seconds"};
        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "bpfeat_engine --events CSV --model WEIGHTS --out-dir NEW_DIRECTORY --mode fixed|batch|alpha|joint\n"
                         "Engine diagnostics only; see source/README.md for the exact schema and defaults.\n";
            return 0;
        }
        std::map<std::string, std::string> options;
        for (int i = 1; i < argc; i += 2) {
            std::string key = argv[i];
            if (!allowed.count(key) || i + 1 >= argc || !options.emplace(key, argv[i + 1]).second)
                throw std::invalid_argument("unknown, missing or duplicate option: " + key);
        }
        for (auto key : {"--events", "--model", "--out-dir", "--mode"})
            if (!options.count(key) || options.at(key).empty()) throw std::invalid_argument(std::string("required: ") + key);
        auto integer = [&](const char* key, std::uint64_t fallback) {
            return options.count(key) ? bpfeat::unsigned_integer(options.at(key)) : fallback;
        };
        auto real = [&](const char* key, double fallback) {
            if (!options.count(key)) return fallback;
            std::size_t end = 0;
            double value = std::stod(options.at(key), &end);
            if (end != options.at(key).size() || !std::isfinite(value)) throw std::invalid_argument("invalid numeric option");
            return value;
        };
        auto u32 = [&](const char* key, std::uint32_t fallback) {
            auto value = integer(key, fallback);
            if (value > std::numeric_limits<std::uint32_t>::max()) throw std::out_of_range("option exceeds uint32");
            return static_cast<std::uint32_t>(value);
        };
        bpfeat::PipelineConfig config;
        auto mode = options.at("--mode");
        if (mode == "fixed") config.mode = bpfeat::Mode::Fixed;
        else if (mode == "batch") config.mode = bpfeat::Mode::BatchOnly;
        else if (mode == "alpha") config.mode = bpfeat::Mode::AlphaOnly;
        else if (mode == "joint") config.mode = bpfeat::Mode::Joint;
        else throw std::invalid_argument("unknown mode");
        config.batch_initial = u32("--batch-size", config.batch_initial);
        config.batch_min = u32("--batch-min", config.batch_min);
        config.batch_max = u32("--batch-max", config.batch_max);
        config.alpha_initial = real("--alpha", config.alpha_initial);
        config.alpha_min = real("--alpha-min", config.alpha_min);
        config.alpha_max = real("--alpha-max", config.alpha_max);
        config.alpha_delta = real("--alpha-delta", config.alpha_delta);
        config.occupancy_gain = real("--occupancy-gain", config.occupancy_gain);
        config.low = real("--low", config.low);
        config.high = real("--high", config.high);
        config.shrink = real("--shrink", config.shrink);
        config.grow = real("--grow", config.grow);
        config.feature_slots = integer("--feature-slots", config.feature_slots);
        config.batch_slots = integer("--batch-slots", config.batch_slots);
        config.max_keys = integer("--max-keys", config.max_keys);
        config.timeout_seconds = integer("--timeout-seconds", config.timeout_seconds);
        bpfeat::validate(config);
        if (!fs::is_regular_file(fs::symlink_status(options.at("--events"))) ||
            !fs::is_regular_file(fs::symlink_status(options.at("--model"))))
            throw std::runtime_error("events/model must be supplied regular files");
        auto model = bpfeat::LogisticModel::load(options.at("--model"));
        std::ifstream input(options.at("--events"));
        if (!input) throw std::runtime_error("cannot open events");
        bpfeat::ReplayReader reader(input);
        const fs::path directory = options.at("--out-dir");
        if (!fs::create_directory(directory)) throw std::runtime_error("output directory already exists or cannot be created");
        std::ofstream predictions(directory / "predictions_unlabeled.csv");
        std::ofstream trace(directory / "batch_controller.csv");
        auto stats = bpfeat::run_pipeline([&](bpfeat::RawEvent& event) { return reader.next(event); }, model, predictions, trace, config);
        std::ofstream receipt(directory / "engine_receipt.json");
        receipt << "{\n  \"schema\": \"bpfeat.engine.receipt.v2\",\n  \"status\": \"ENGINE_COMPLETED\",\n"
                   "  \"research_evidence\": false,\n  \"feature_schema\": \"bpfeat.taobao.features.v2\",\n"
                << "  \"mode\": \"" << mode << "\",\n  \"read\": " << stats.read << ",\n  \"extracted\": " << stats.extracted
                << ",\n  \"batched\": " << stats.batched << ",\n  \"scored\": " << stats.scored << ",\n  \"written\": " << stats.written
                << ",\n  \"batches\": " << stats.batches << ",\n  \"tail_batches\": " << stats.tails
                << ",\n  \"source_block_retries\": " << stats.source_block_retries << ",\n  \"batch_block_retries\": " << stats.batch_block_retries
                << ",\n  \"batch_actions\": " << stats.batch_actions << ",\n  \"direction_changes\": " << stats.direction_changes
                << ",\n  \"started_monotonic_ns\": " << stats.started_ns << ",\n  \"finished_monotonic_ns\": " << stats.finished_ns << "\n}\n";
        receipt.flush();
        if (!receipt) throw std::runtime_error("engine receipt write failed");
        std::cout << "ENGINE_COMPLETED rows=" << stats.written << " research_evidence=false\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "ENGINE_FAILED: " << error.what() << '\n';
        return 2;
    }
}
