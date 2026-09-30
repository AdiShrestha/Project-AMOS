#include <cassert>
#include <fstream>
#include <stdexcept>
#include <string>
#include <iostream>

#include "klstream/core/metrics.hpp"

using namespace klstream;

int main() {
    const std::string path = "/tmp/bpfeat-native-trace-test.jsonl";
    NativeTraceWriter writer(path, "run-test", "cfg-test");
    writer.write({1, 1, 0, "source", "produced", 10, "2026-08-28T00:00:00Z", "cfg-test", "complete"});
    writer.write({2, 2, 0, "sink", "finalized", 20, "2026-08-28T00:00:01Z", "cfg-test", "complete"});
    writer.flush();
    bool threw = false;
    try { writer.write({3, 2, 0, "sink", "duplicate", 30, "", "cfg-test", "complete"}); }
    catch (const std::logic_error&) { threw = true; }
    assert(threw);
    std::ifstream in(path);
    std::string first, second;
    assert(std::getline(in, first) && std::getline(in, second));
    assert(first.find("\"schema_version\":\"1.0\"") != std::string::npos);
    assert(first.find("\"run_id\":\"run-test\"") != std::string::npos);
    assert(first.find("\"origin\":\"source\"") != std::string::npos);
    assert(second.find("\"event_seq\":2") != std::string::npos);
    std::cout << "native_trace=PASS\n";
    return 0;
}
