import re

def fix_file(path):
    with open(path, "r") as f:
        code = f.read()

    # Move add_worker before register_op
    code = code.replace("bool source_done = false;\n    rt.register_op", "bool source_done = false;\n    rt.add_worker();\n    rt.register_op")
    code = code.replace("rt.add_worker(); rt.start();", "rt.start();")

    with open(path, "w") as f:
        f.write(code)

for p in ["tests/test_pipeline_integration.cpp", "feature_flow/harness.cpp", "feature_flow/main.cpp"]:
    fix_file(p)

print("Done")
