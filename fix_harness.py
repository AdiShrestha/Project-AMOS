import re

def fix_file(path):
    with open(path, "r") as f:
        code = f.read()

    # Add source_done
    code = code.replace("Runtime rt;", "Runtime rt;\n    bool source_done = false;")

    # Fix lambda
    code = code.replace(
        "[&src](Event<RawBehaviorEvent>& out, std::uint64_t seq){ return src(out, seq); }",
        "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; }"
    )
    code = code.replace(
        "[&src](Event<RawBehaviorEvent>& out, std::uint64_t seq){ return src(out,seq); }",
        "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out,seq); if(!ok) source_done=true; return ok; }"
    )

    # Fix registrations
    code = re.sub(r'rt\.register_op\((&[a-zA-Z0-9_]+)\);', r'rt.register_op(\1, 0);', code)

    # Fix run_until
    code = code.replace("rt.run_until_source_exhausted();",
        "rt.add_worker();\n        rt.start();\n        while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }\n        std::this_thread::sleep_for(std::chrono::milliseconds(20));\n        rt.stop();")

    with open(path, "w") as f:
        f.write(code)

fix_file("feature_flow/harness.cpp")
fix_file("feature_flow/main.cpp")
print("Done")
