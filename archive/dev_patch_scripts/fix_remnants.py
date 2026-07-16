import re

# Fix main.cpp aggr lambdas
with open("feature_flow/main.cpp", "r") as f:
    code = f.read()
code = code.replace(
    "auto aggr = [](const std::vector<FeatureSnapshot>& buf) -> FeatureBatch {\n            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i],i); return fb;\n        };",
    "auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {\n            FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,i); return fb;\n        };"
)
code = code.replace("const std::vector<FeatureSnapshot>& buf", "const std::vector<Event<FeatureSnapshot>>& buf")
code = code.replace("fb.push_back(buf[i],i)", "fb.push_back(buf[i].data,i)")
with open("feature_flow/main.cpp", "w") as f:
    f.write(code)

# Fix test_keyed_feature_extract_op.cpp
with open("tests/test_keyed_feature_extract_op.cpp", "r") as f:
    code = f.read()
code = code.replace(
    "RawBehaviorEvent{1, 100, 10, 3, 0.0f}",
    "RawBehaviorEvent{1, 1000, 100, 10, 3, 0.0f}"
)
code = code.replace(
    "RawBehaviorEvent{2, 101, 10, 0, 0.0f}",
    "RawBehaviorEvent{2, 2000, 101, 10, 0, 0.0f}"
)
code = code.replace(
    "RawBehaviorEvent{0, 0, 0, 0, /*amount*/100.0f + i}",
    "RawBehaviorEvent{0, 1000, 0, 0, 0, /*amount*/100.0f + i}"
)
with open("tests/test_keyed_feature_extract_op.cpp", "w") as f:
    f.write(code)

print("Done")
