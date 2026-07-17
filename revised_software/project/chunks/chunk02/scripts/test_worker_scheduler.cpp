#include "klstream/core/worker.hpp"
#include <iostream>
#include <cassert>
#include <chrono>
#include <thread>

using namespace klstream;

class MockOperator : public IOperator {
public:
    explicit MockOperator(std::string name) : IOperator(std::move(name)) {}

    void init() override {
        initialized = true;
    }

    OpStatus tick() override {
        ticks++;
        return OpStatus::Processed;
    }

    void shutdown() override {
        shutdown_called = true;
    }

    bool initialized = false;
    bool shutdown_called = false;
    std::atomic<int> ticks{0};
};

int main() {
    MockOperator op("test_op");
    WorkerThread worker;
    worker.assign(&op);
    worker.set_affinity(CoreAffinity::Any);

    assert(!op.initialized);
    assert(!op.shutdown_called);

    worker.start();

    // Give it a little time to spin and process
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    assert(op.initialized);
    assert(op.ticks > 0);

    worker.stop();

    assert(op.shutdown_called);

    std::cout << "Worker scheduler tests passed!" << std::endl;
    return 0;
}
