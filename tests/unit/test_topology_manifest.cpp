#include <cassert>
#include <stdexcept>
#include <string>
#include <iostream>
#include "klstream/core/runtime.hpp"
#include "klstream/operators/source.hpp"

using namespace klstream;

int main() {
    SPSCQueue<Event<int>> q(8);
    SourceOperator<int> source("source", &q, [](Event<int>&, std::uint64_t) { return false; });
    Runtime runtime;
    const int worker = runtime.add_worker(CoreAffinity::Any);
    runtime.register_op(&source, worker);
    const auto observed = runtime.observed_topology();
    std::string reason;
    assert(observed.validate(&reason));
    runtime.set_expected_topology(observed);
    assert(runtime.validate_topology(&reason));
    assert(observed.nodes.size() == 1 && observed.nodes[0].name == "source");

    TopologyManifest duplicate;
    duplicate.nodes = {{1, "a", 0, CoreAffinity::Any}, {1, "b", 0, CoreAffinity::Any}};
    assert(!duplicate.validate(&reason));
    bool threw = false;
    try { runtime.set_expected_topology(duplicate); } catch (const std::invalid_argument&) { threw = true; }
    assert(threw);

    SourceOperator<int> duplicate_name("source", &q, [](Event<int>&, std::uint64_t) { return false; });
    threw = false;
    try { runtime.register_op(&duplicate_name, worker); } catch (const std::logic_error&) { threw = true; }
    assert(threw);
    std::cout << "topology_manifest=PASS\n";
    return 0;
}
