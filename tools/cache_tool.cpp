#include "bpfeat/cache.hpp"
#include "bpfeat/replay.hpp"
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <set>
#include <string>

int main(int argc, char** argv) {
    try {
        const std::set<std::string> allowed = {
            "--events", "--queries", "--out-queries", "--out-accounting",
            "--policy", "--cadence", "--delta-t-ns", "--alpha", "--max-keys"
        };

        if (argc == 2 && std::string(argv[1]) == "--help") {
            std::cout << "bpfeat_cache_tool --events CSV [--queries CSV] [--out-queries CSV] [--out-accounting JSON] [--policy exact_fresh|fixed_cadence|elapsed_threshold|adaptive] [--cadence K] [--delta-t-ns DELTA_T] [--alpha ALPHA]\n";
            return 0;
        }

        std::map<std::string, std::string> options;
        for (int i = 1; i < argc; i += 2) {
            std::string key = argv[i];
            if (!allowed.count(key) || i + 1 >= argc || !options.emplace(key, argv[i + 1]).second) {
                throw std::invalid_argument("unknown, missing or duplicate option: " + key);
            }
        }

        if (!options.count("--events") || options.at("--events").empty()) {
            throw std::invalid_argument("required option: --events");
        }

        bpfeat::PublicationPolicyConfig policy_config;
        std::string policy_str = options.count("--policy") ? options.at("--policy") : "ExactFresh";
        for (auto& c : policy_str) c = static_cast<char>(std::tolower(c));

        if (policy_str == "exactfresh" || policy_str == "exact_fresh" || policy_str == "fresh") {
            policy_config.type = bpfeat::PublicationPolicyType::ExactFresh;
        } else if (policy_str == "fixedcadence" || policy_str == "fixed_cadence" || policy_str == "cadence") {
            policy_config.type = bpfeat::PublicationPolicyType::FixedCadence;
        } else if (policy_str == "elapsedthreshold" || policy_str == "elapsed_threshold" || policy_str == "elapsed") {
            policy_config.type = bpfeat::PublicationPolicyType::ElapsedThreshold;
        } else if (policy_str == "adaptivepressure" || policy_str == "adaptive_pressure" || policy_str == "adaptive") {
            policy_config.type = bpfeat::PublicationPolicyType::AdaptivePressure;
        } else {
            throw std::invalid_argument("unknown policy: " + policy_str);
        }

        if (options.count("--cadence")) {
            policy_config.cadence = bpfeat::unsigned_integer(options.at("--cadence"));
            if (policy_config.cadence == 0) throw std::invalid_argument("cadence must be positive");
            policy_config.cadence_max = std::max<std::uint64_t>(16, policy_config.cadence);
        }

        if (options.count("--delta-t-ns")) {
            policy_config.elapsed_threshold_ns = bpfeat::unsigned_integer(options.at("--delta-t-ns"));
        }

        double alpha = 0.1;
        if (options.count("--alpha")) {
            alpha = std::stod(options.at("--alpha"));
        }

        std::size_t max_keys = 1000000;
        if (options.count("--max-keys")) {
            max_keys = static_cast<std::size_t>(bpfeat::unsigned_integer(options.at("--max-keys")));
        }

        bpfeat::PublicationCoordinator coordinator(policy_config, alpha, max_keys);

        // Process events
        std::ifstream events_file(options.at("--events"));
        if (!events_file) throw std::runtime_error("cannot open events file");
        bpfeat::ReplayReader reader(events_file);
        bpfeat::RawEvent event;
        while (reader.next(event)) {
            coordinator.process_event(event);
        }

        // Process queries if supplied
        std::vector<bpfeat::QueryResult> query_results;
        if (options.count("--queries")) {
            std::ifstream queries_file(options.at("--queries"));
            if (!queries_file) throw std::runtime_error("cannot open queries file");
            std::string header;
            if (std::getline(queries_file, header)) {
                std::string line;
                while (std::getline(queries_file, line)) {
                    if (line.empty()) continue;
                    if (line.back() == '\r') line.pop_back();
                    auto cells = bpfeat::csv_cells(line);
                    if (cells.size() < 3) continue;
                    std::uint64_t qid = bpfeat::unsigned_integer(cells[0]);
                    std::uint64_t key = bpfeat::unsigned_integer(cells[1]);
                    std::uint64_t qts = bpfeat::unsigned_integer(cells[2]);
                    query_results.push_back(coordinator.query(qid, key, qts));
                }
            }
        }

        // Output queries CSV
        if (options.count("--out-queries") && !query_results.empty()) {
            std::ofstream out_q(options.at("--out-queries"));
            if (!out_q) throw std::runtime_error("cannot open output queries file");
            out_q << std::setprecision(17);
            out_q << "query_id,key,query_ts_ns,cold_start,version_id,latest_included_seq,latest_event_ts_ns,event_time_age_ns,update_staleness,feature_error";
            for (std::size_t i = 0; i < bpfeat::FEATURE_DIMENSION; ++i) out_q << ",cached_x" << i;
            for (std::size_t i = 0; i < bpfeat::FEATURE_DIMENSION; ++i) out_q << ",fresh_x" << i;
            out_q << "\n";

            for (const auto& r : query_results) {
                out_q << r.query_id << "," << r.key << "," << r.query_ts_ns << ","
                      << (r.cold_start ? 1 : 0) << "," << r.version_id << ","
                      << r.latest_included_seq << "," << r.latest_event_ts_ns << ","
                      << r.event_time_age_ns << "," << r.update_staleness << ","
                      << std::scientific << r.feature_error;
                for (std::size_t i = 0; i < bpfeat::FEATURE_DIMENSION; ++i) {
                    out_q << "," << std::scientific << r.cached_features[i];
                }
                for (std::size_t i = 0; i < bpfeat::FEATURE_DIMENSION; ++i) {
                    out_q << "," << std::scientific << r.fresh_features[i];
                }
                out_q << "\n";
            }
        }

        // Output accounting JSON
        const auto& acc = coordinator.accounting();
        if (options.count("--out-accounting")) {
            std::ofstream out_acc(options.at("--out-accounting"));
            if (!out_acc) throw std::runtime_error("cannot open output accounting file");
            out_acc << "{\n"
                    << "  \"processed_updates\": " << acc.processed_updates << ",\n"
                    << "  \"published_updates\": " << acc.published_updates << ",\n"
                    << "  \"coalesced_updates\": " << acc.coalesced_updates << ",\n"
                    << "  \"queries_served\": " << acc.queries_served << ",\n"
                    << "  \"cold_queries\": " << acc.cold_queries << ",\n"
                    << "  \"warm_queries\": " << acc.warm_queries << ",\n"
                    << "  \"conservation_valid\": " << (acc.is_conserved() ? "true" : "false") << "\n"
                    << "}\n";
        }

        std::cout << "{\n"
                  << "  \"processed_updates\": " << acc.processed_updates << ",\n"
                  << "  \"published_updates\": " << acc.published_updates << ",\n"
                  << "  \"coalesced_updates\": " << acc.coalesced_updates << ",\n"
                  << "  \"queries_served\": " << acc.queries_served << ",\n"
                  << "  \"cold_queries\": " << acc.cold_queries << ",\n"
                  << "  \"warm_queries\": " << acc.warm_queries << ",\n"
                  << "  \"conservation_valid\": " << (acc.is_conserved() ? "true" : "false") << "\n"
                  << "}\n";

        return acc.is_conserved() ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << "\n";
        return 2;
    }
}
