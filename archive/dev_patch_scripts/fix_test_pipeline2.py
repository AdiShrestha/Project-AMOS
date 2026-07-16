import re

with open("tests/test_pipeline_integration.cpp", "r") as f:
    code = f.read()

# Remove the incorrectly placed source_done
code = code.replace("Runtime rt;\n    bool source_done = false;", "Runtime rt;")

# Insert bool source_done = false; after BehaviorSource src(...)
code = re.sub(
    r'(BehaviorSource src\([^)]+\);)',
    r'\1\n    bool source_done = false;',
    code
)

# Fix lambda in all 3 runs
code = code.replace(
    "[&src](Event<RawBehaviorEvent>& out, std::uint64_t seq){ return src(out,seq); }",
    "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; }"
)
code = code.replace(
    "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; });",
    "[&src, &source_done](Event<RawBehaviorEvent>& out, std::uint64_t seq){ bool ok = src(out, seq); if(!ok) source_done=true; return ok; }"
)

with open("tests/test_pipeline_integration.cpp", "w") as f:
    f.write(code)

print("Done")
