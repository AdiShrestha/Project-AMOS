import re

files = [
    "feature_flow/main.cpp",
    "feature_flow/harness.cpp",
    "tests/test_pipeline_integration.cpp"
]

for path in files:
    with open(path, "r") as f:
        code = f.read()

    new_drain = """while(!source_done) { std::this_thread::sleep_for(std::chrono::milliseconds(5)); }
        int drain_checks = 0;
        while (drain_checks < 10) {
            if (q_raw.empty() && q_feat.empty() && q_batch.empty() && q_scored.empty()) {
                drain_checks++;
            } else {
                drain_checks = 0;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
        }
        printf("[drain] Final occupancy: raw=%.3f, feat=%.3f, batch=%.3f, scored=%.3f\\n", 
               q_raw.occupancy(), q_feat.occupancy(), q_batch.occupancy(), q_scored.occupancy());"""
               
    # Replace the while(!source_done)... and the sleep_for(20ms)
    code = re.sub(
        r'while\(!source_done\) \{ std::this_thread::sleep_for\(std::chrono::milliseconds\(5\)\); \}\s*std::this_thread::sleep_for\(std::chrono::milliseconds\(20\)\);',
        new_drain,
        code
    )

    with open(path, "w") as f:
        f.write(code)

print("Done")
