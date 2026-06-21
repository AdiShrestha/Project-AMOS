#pragma once
// IOperator: the abstract base class every KLStream operator implements.
// The cooperative scheduler (Runtime) calls tick() in a round-robin loop
// across all registered operators. Operators MUST NOT block inside tick();
// if an output queue is full, they return OpStatus::Blocked and the
// scheduler moves on to the next operator.

#include <string>

namespace klstream {

enum class OpStatus {
    Processed,  // did useful work (pushed or popped at least one event)
    Idle,       // input queue empty, nothing to do
    Blocked,    // output queue full, could not push — try again next tick
    Done        // source exhausted; runtime may stop scheduling this operator
};

class IOperator {
public:
    explicit IOperator(std::string name) : name_(std::move(name)) {}
    virtual ~IOperator() = default;

    // Non-blocking: do exactly ONE unit of work (push or pop ONE event).
    // Return the appropriate OpStatus so the scheduler can act.
    virtual OpStatus tick() = 0;

    // Called once after the runtime loop exits, before thread join.
    virtual void shutdown() {}

    [[nodiscard]] const std::string& name() const noexcept { return name_; }

protected:
    std::string name_;
};

} // namespace klstream
