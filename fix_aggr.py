import re

def fix_file(path):
    with open(path, "r") as f:
        code = f.read()

    code = code.replace(
        "auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {\n            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i],i); return fb;\n        };",
        "auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {\n            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,i); return fb;\n        };"
    )

    with open(path, "w") as f:
        f.write(code)

fix_file("feature_flow/harness.cpp")
fix_file("feature_flow/main.cpp")
print("Done")
