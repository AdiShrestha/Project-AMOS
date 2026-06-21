import re
for path in ["tests/test_pipeline_integration.cpp", "feature_flow/harness.cpp", "feature_flow/main.cpp"]:
    with open(path, "r") as f:
        code = f.read()
    code = code.replace("Runtime rt;", "Runtime rt;\n    rt.add_worker();")
    with open(path, "w") as f:
        f.write(code)
print("Done")
