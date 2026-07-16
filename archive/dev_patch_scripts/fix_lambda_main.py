import re

files = [
    "feature_flow/main.cpp",
    "feature_flow/harness.cpp"
]

for path in files:
    with open(path, "r") as f:
        code = f.read()

    # Fixed, Drift, Adaptive
    old_lambda = """[&behavior_src](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                return behavior_src(out, seq); }"""
    new_lambda = """[&behavior_src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){
                bool ok = behavior_src(out, seq); if(!ok) source_done=true; return ok; }"""
    code = code.replace(old_lambda, new_lambda)

    # Throttled
    old_throttled = """return [&src, &q_raw](Event<RawBehaviorEvent>& out, std::uint64_t seq) -> bool {
        tracker.update();
        if (tracker.soft_pressure()) {
            limiter.set_rate(std::max(1000.0, limiter.rate() * 0.85));
        } else if (tracker.ema() < 0.30) {
            limiter.set_rate(std::min(100000.0, limiter.rate() * 1.05));
        }
        if (!limiter.try_consume()) return true; // skip this tick (not done, just throttled)
        return src(out, seq);
    };"""
    new_throttled = """return [&src, &q_raw, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq) -> bool {
        tracker.update();
        if (tracker.soft_pressure()) {
            limiter.set_rate(std::max(1000.0, limiter.rate() * 0.85));
        } else if (tracker.ema() < 0.30) {
            limiter.set_rate(std::min(100000.0, limiter.rate() * 1.05));
        }
        if (!limiter.try_consume()) return true; // skip this tick (not done, just throttled)
        bool ok = src(out, seq); if(!ok) source_done=true; return ok;
    };"""
    code = code.replace(old_throttled, new_throttled)
    
    # We also need to fix `make_throttled_generator` arguments to accept `source_done`
    code = code.replace("make_throttled_generator(BehaviorSource& src,", "make_throttled_generator(BehaviorSource& src, bool& source_done,")
    code = code.replace("make_throttled_generator(behavior_src, q_raw)", "make_throttled_generator(behavior_src, source_done, q_raw)")

    with open(path, "w") as f:
        f.write(code)

print("Done")
