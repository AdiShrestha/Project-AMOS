import re

with open("tests/test_pipeline_integration.cpp", "r") as f:
    code = f.read()

# Fix the duplicate lambda body
bad_lambda = """    auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
        FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,i); return fb;
    };
        FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i],i); return fb;
    };"""

good_lambda = """    auto aggr = [](const std::vector<Event<FeatureSnapshot>>& buf) -> FeatureBatch {
        FeatureBatch fb{}; for (std::size_t i=0;i<buf.size();i++) fb.push_back(buf[i].data,i); return fb;
    };"""

code = code.replace(bad_lambda, good_lambda)

with open("tests/test_pipeline_integration.cpp", "w") as f:
    f.write(code)

print("Done")
