import re

files = [
    "feature_flow/main.cpp",
    "feature_flow/harness.cpp",
    "tests/test_pipeline_integration.cpp"
]

for path in files:
    with open(path, "r") as f:
        code = f.read()

    # Find the malformed printf which spans across multiple lines
    bad_printf = r'printf\("\[drain\] Final occupancy: raw=%\.3f, feat=%\.3f, batch=%\.3f, scored=%\.3f\n",\s*q_raw\.occupancy\(\), q_feat\.occupancy\(\), q_batch\.occupancy\(\), q_scored\.occupancy\(\)\);'
    good_printf = r'printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\\n", q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());'
    
    code = re.sub(bad_printf, good_printf, code, flags=re.MULTILINE)

    with open(path, "w") as f:
        f.write(code)

print("Done")
