import re

with open("tests/test_pipeline_integration.cpp", "r") as f:
    code = f.read()

# Fix lambda
code = code.replace(
    "[&src](Event<RawBehaviorEvent>& out, std::uint64_t seq){ return src(out, seq); }",
    "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; }"
)

# Fix Runtime
code = code.replace("Runtime rt;", "Runtime rt;\n    bool source_done = false;")
code = re.sub(r'rt\.register_op\((&[a-zA-Z0-9_]+)\);', r'rt.register_op(\1, 0);', code)
code = code.replace("rt.run_until_source_exhausted();", "rt.add_worker(); rt.start(); while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); } std::this_thread::sleep_for(std::chrono::milliseconds(20)); rt.stop();")

# Fix aggr
code = code.replace(
    "auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {\n        FeatureBatch fb{}; for(std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i], i); return fb;\n    };",
    "auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {\n        FeatureBatch fb{}; for(std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data, i); return fb;\n    };"
)

with open("tests/test_pipeline_integration.cpp", "w") as f:
    f.write(code)

print("Done")
