// FABRICATION-DISCLOSURE: All records and weights below are declared test
// fixtures. They are never research data, predictions or certification input.
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
        std::cout << "Engine fixture counterexamples passed; no research claims.\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
