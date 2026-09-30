#include <cassert>
#include <cstdint>
#include <iostream>

#include "klstream/core/metrics.hpp"

using namespace klstream;

static void boundary_case(std::uint64_t n, std::uint64_t window) {
    AccountingLedger ledger;
    ledger.offer(n);
    ledger.admit(n);
    const std::uint64_t full = n / window;
    const std::uint64_t tail = n % window;
    if (full) ledger.scored(full * window);
    if (tail) {
        ledger.partial_batch();
        ledger.scored(tail);
    }
    ledger.emitted(n);
    ledger.sink_finalized();
    const auto snap = ledger.snapshot();
    assert(snap.offered == n);
    assert(snap.admitted == n);
    assert(snap.in_flight == 0);
    assert(snap.terminal_scored == n);
    assert(snap.partial_batches == (tail ? 1u : 0u));
    assert(ledger.conservation_valid());
    assert(ledger.terminal_predicate(true, true, true, true));
    std::cout << "{\"offered\":" << snap.offered
              << ",\"admitted\":" << snap.admitted
              << ",\"terminal_scored\":" << snap.terminal_scored
              << ",\"partial_batches\":" << snap.partial_batches
              << ",\"in_flight\":" << snap.in_flight << "}\n";
}

int main() {
    for (const std::uint64_t n : {0u, 1u, 7u, 8u, 9u, 17u}) boundary_case(n, 8);

    AccountingLedger rejected;
    rejected.offer(3);
    rejected.reject(3);
    assert(rejected.conservation_valid());
    assert(rejected.snapshot().in_flight == 0);

    AccountingLedger cancelled;
    cancelled.offer(2);
    cancelled.admit(2);
    cancelled.cancelled(2);
    assert(cancelled.conservation_valid());
    assert(cancelled.snapshot().terminal_cancelled == 2);
    return 0;
}
