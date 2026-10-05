// FABRICATION-DISCLOSURE: All records and weights below are declared test
// fixtures. They are never research data, predictions or certification input.
#include "bpfeat/cache.hpp"
#include "bpfeat/pipeline.hpp"
#include "bpfeat/replay.hpp"
#include <cmath>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

using namespace bpfeat;
// Assertions must execute in Release as well as Debug; no assert side effects.
void require(bool condition, const char* why) { if (!condition) throw std::runtime_error(why); }
template<class Function> void rejects(Function f, const char* why) {
    bool threw = false;
    try { f(); } catch (const std::exception&) { threw = true; }
    require(threw, why);
}
int main() {
    try {
        for (auto capacity : {std::size_t{0}, std::size_t{1}, std::size_t{3}})
            rejects([&] { SPSCQueue<int> q(capacity); }, "invalid queue accepted");
        SPSCQueue<int> queue(4);
        for (int i = 0; i < 3; ++i) require(queue.try_push(i), "valid queue push failed");
        require(queue.occupancy() == 1, "full queue must report one");
        require(!queue.try_push(4), "full queue accepted input");
        queue.close();
        require(!queue.try_push(5), "closed queue accepted input");
        for (int i = 0, actual; i < 3; ++i) { require(queue.try_pop(actual), "closed drain failed"); require(actual == i, "queue reordered"); }
        require(queue.closed_and_empty(), "close drain predicate wrong");
        SPSCQueue<std::uint64_t> concurrent(8);
        std::atomic<bool> bad{false};
        std::thread producer([&] {
            for (std::uint64_t i = 0; i < 100000; ++i)
                while (!concurrent.try_push(i)) std::this_thread::yield();
            concurrent.close();
        });
        std::thread consumer([&] {
            std::uint64_t expected = 0, value;
            for (;;) {
                if (concurrent.try_pop(value)) { if (value != expected++) bad = true; }
                else if (concurrent.closed_and_empty()) break;
                else std::this_thread::yield();
            }
            if (expected != 100000) bad = true;
        });
        producer.join(); consumer.join();
        require(!bad, "concurrent sequence conservation failed");
        AlphaController alpha(0.02, 0.3, 0.01, 0.1);
        require(std::abs(alpha.update(1) - 0.11) < 1e-12, "alpha slew incorrect");
        rejects([&] { alpha.update(std::nan("")); }, "NaN pressure accepted");
        MultiplicativeBatchController batch(8, 256, 0.3, 0.7, 0.7, 1.01, 8);
        require(batch.update(0) == 9, "integer growth trap remains");
        KeyedFeatures features(1);
        auto first = features.update({10, 0, 1, 1, 2520377, 0}, 1, 10);
        auto second = features.update({30, 1000000000, 1, 2, 2520377, 3}, 1, 20);
        require(first.event.category_id == 2520377, "category truncated");
        require(std::abs(second.x[6] - 1) < 1e-12, "time-zero sentinel error");
        require(second.event.seq == 30, "sequence gap lost");
        rejects([&] { features.update({40, 1, 2, 1, 1, 0}, 0.1, 0); }, "key cap silently dropped event");
        rejects([&] { features.update({40, 1, 1, 1, 1, 0}, 0.1, 0); }, "time regression accepted");
        LogisticModel model(0.2, {0.4, -0.1, 0.3, 0.2, -0.4, 0.1, 0.01});
        auto score = model.score(second.x);
        require(std::isfinite(score) && score > 0 && score < 1, "score invalid");
        for (auto mode : {Mode::Fixed, Mode::BatchOnly, Mode::AlphaOnly, Mode::Joint}) {
            for (std::uint64_t n : {0, 1, 7, 8, 9, 17, 257}) {
                PipelineConfig config;
                config.mode = mode;
                config.batch_initial = 8;
                config.feature_slots = 2;
                config.batch_slots = 2;
                std::uint64_t index = 0;
                std::ostringstream output, trace;
                auto stats = run_pipeline([&](RawEvent& event) {
                    if (index == n) return false;
                    event = {10 + index * 3, index * 1000000000, index % 3, 100, 2520377, static_cast<std::uint8_t>(index % 4)};
                    ++index; return true;
                }, model, output, trace, config);
                require(stats.read == n && stats.written == n && stats.scored == n, "pipeline counter mismatch");
                std::istringstream csv(output.str());
                std::string line;
                std::getline(csv, line);
                std::uint64_t rows = 0;
                while (std::getline(csv, line)) {
                    auto cells = csv_cells(line);
                    require(unsigned_integer(cells[0]) == 10 + rows * 3, "batch invented IDs");
                    require(unsigned_integer(cells[1]) == rows * 1000000000, "batch replaced event timestamp");
                    require(unsigned_integer(cells[10]) == unsigned_integer(cells[9]) - unsigned_integer(cells[8]), "latency arithmetic wrong");
                    ++rows;
                }
                require(rows == n, "tail or blocked event lost/duplicated");
            }
        }
        std::uint64_t index = 0;
        std::ostringstream output, trace;
        rejects([&] { run_pipeline([&](RawEvent& event) {
            if (index++ == 4) throw std::runtime_error("injected input failure");
            event = {index, index, 1, 1, 1, 0}; return true;
        }, model, output, trace, PipelineConfig{}); }, "input failure marked successful");
        struct FailedBuffer : std::streambuf { int overflow(int) override { return traits_type::eof(); } } buffer;
        std::ostream failing(&buffer);
        rejects([&] { run_pipeline([](RawEvent&) { return false; }, model, failing, trace, PipelineConfig{}); }, "sink failure accepted");
        struct FlushFailure : std::stringbuf { int sync() override { return -1; } } flush_buffer;
        std::ostream flush_failure(&flush_buffer);
        rejects([&] { run_pipeline([](RawEvent&) { return false; }, model, flush_failure, trace, PipelineConfig{}); }, "final flush failure accepted");
        struct CommaLocale : std::numpunct<char> { char do_decimal_point() const override { return ','; } };
        std::ostringstream polluted, clean_trace;
        polluted.imbue(std::locale(std::locale::classic(), new CommaLocale));
        polluted << std::hex << std::showpos << std::boolalpha << std::scientific;
        bool produced = false;
        auto formatting_stats = run_pipeline([&](RawEvent& event) {
            if (produced) return false;
            produced = true; event = {30, 10, 1, 1, 1, 0}; return true;
        }, model, polluted, clean_trace, PipelineConfig{});
        require(formatting_stats.written == 1, "formatting fixture lost");
        std::istringstream formatted(polluted.str());
        std::string header, row;
        std::getline(formatted, header); std::getline(formatted, row);
        auto cells = csv_cells(row);
        require(cells.size() == csv_cells(header).size() && cells[0] == "30" && cells[7] == "0", "caller formatting corrupted diagnostics");

        // Versioned Cache and Publication Coordinator Tests (AMOS-06)
        {
            VersionedCache cache(100);
            auto cold = cache.get(999);
            require(cold.cold_start, "cold lookup must report cold_start=true");
            require(cold.version.version_id == 0, "cold lookup version_id must be 0");
            require(cold.version.features[0] == 0.0, "cold lookup features must be 0");

            std::array<double, FEATURE_DIMENSION> f1 = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0};
            auto v1 = cache.publish(42, 10, 1000000, f1, 1000100);
            require(v1.version_id == 1, "first publication must have version_id=1");
            require(v1.key == 42 && v1.latest_included_seq == 10, "version metadata corrupted");

            auto lookup1 = cache.get(42);
            require(!lookup1.cold_start, "published key must not be cold");
            require(lookup1.version.version_id == 1, "published key version mismatch");
            require(std::abs(lookup1.version.features[0] - 1.0) < 1e-12, "feature mismatch");

            std::array<double, FEATURE_DIMENSION> f2 = {1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5};
            auto v2 = cache.publish(42, 20, 2000000, f2, 2000100);
            require(v2.version_id == 2, "second publication must have version_id=2");

            auto lookup2 = cache.get(42);
            require(lookup2.version.version_id == 2, "lookup2 version mismatch");
            require(std::abs(lookup2.version.features[0] - 1.5) < 1e-12, "feature mismatch v2");
        }

        // Concurrent Readers/Writers Stress Test on VersionedCache
        {
            VersionedCache conc_cache(1000);
            std::atomic<bool> conc_stop{false};
            std::atomic<bool> conc_error{false};
            constexpr int NUM_KEYS = 50;
            constexpr int NUM_ITERATIONS = 5000;

            std::vector<std::thread> writers;
            for (int w = 0; w < 4; ++w) {
                writers.emplace_back([&, w] {
                    for (int i = 0; i < NUM_ITERATIONS && !conc_error.load(); ++i) {
                        std::uint64_t key = (w * 10 + (i % 10)) % NUM_KEYS;
                        std::array<double, FEATURE_DIMENSION> feat{};
                        feat[0] = static_cast<double>(i);
                        conc_cache.publish(key, i, i * 1000, feat, i * 1000 + 50);
                    }
                });
            }

            std::vector<std::thread> readers;
            for (int r = 0; r < 4; ++r) {
                readers.emplace_back([&] {
                    while (!conc_stop.load() && !conc_error.load()) {
                        for (int k = 0; k < NUM_KEYS; ++k) {
                            auto res = conc_cache.get(k);
                            if (!res.cold_start) {
                                if (res.version.version_id == 0) conc_error = true;
                            }
                        }
                    }
                });
            }

            for (auto& w : writers) w.join();
            conc_stop = true;
            for (auto& r : readers) r.join();
            require(!conc_error.load(), "concurrent cache access caused corruption");
        }

        // PublicationCoordinator Conservation & Policies Tests
        {
            // ExactFresh (U=1)
            PublicationPolicyConfig p_fresh;
            p_fresh.type = PublicationPolicyType::ExactFresh;
            PublicationCoordinator coord_fresh(p_fresh, 0.1, 100);

            for (std::uint64_t i = 0; i < 20; ++i) {
                RawEvent ev = {i, i * 1000000000ULL, i % 4, 100, 200, static_cast<std::uint8_t>(i % 4)};
                coord_fresh.process_event(ev);
            }
            const auto& acc_fresh = coord_fresh.accounting();
            require(acc_fresh.processed_updates == 20, "processed_updates mismatch");
            require(acc_fresh.published_updates == 20, "ExactFresh must publish all updates");
            require(acc_fresh.coalesced_updates == 0, "ExactFresh must have 0 coalesced updates");
            require(acc_fresh.is_conserved(), "ExactFresh conservation failed");

            // Query warm key: feature error must be exactly 0
            auto q_warm = coord_fresh.query(1, 0, 20ULL * 1000000000ULL);
            require(!q_warm.cold_start, "key 0 must be warm");
            require(q_warm.feature_error < 1e-12, "ExactFresh feature error must be ~0");
            require(q_warm.update_staleness == 0, "ExactFresh staleness must be 0");

            // Query cold key: cold_start must be true
            auto q_cold = coord_fresh.query(2, 999, 20ULL * 1000000000ULL);
            require(q_cold.cold_start, "unseen key must report cold_start=1");
            require(q_cold.version_id == 0, "cold key version_id must be 0");

            // FixedCadence (U=k=4)
            PublicationPolicyConfig p_cadence;
            p_cadence.type = PublicationPolicyType::FixedCadence;
            p_cadence.cadence = 4;
            PublicationCoordinator coord_cadence(p_cadence, 0.1, 100);

            for (std::uint64_t i = 0; i < 10; ++i) {
                RawEvent ev = {i, i * 1000000000ULL, 1, 100, 200, static_cast<std::uint8_t>(i % 4)};
                coord_cadence.process_event(ev);
            }
            const auto& acc_cadence = coord_cadence.accounting();
            require(acc_cadence.processed_updates == 10, "cadence processed mismatch");
            require(acc_cadence.published_updates == 2, "cadence published count mismatch");
            require(acc_cadence.coalesced_updates == 8, "cadence coalesced count mismatch");
            require(acc_cadence.is_conserved(), "cadence conservation failed");

            auto q_cadence = coord_cadence.query(3, 1, 10ULL * 1000000000ULL);
            require(q_cadence.update_staleness == 2, "cadence update staleness mismatch");
            require(q_cadence.feature_error > 0.0, "coalesced updates must yield positive feature error");
        }

        std::cout << "Engine fixture counterexamples passed; no research claims.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
