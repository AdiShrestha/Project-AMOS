#pragma once
// LogisticModel: plain-text weight file loader and inference step.
// Decision 5: no ONNX, no external model-serving runtime. The inference
// step is a dot product + sigmoid — exactly portable from scikit-learn.

#include "../feature/types.hpp"
#include <array>
#include <cmath>
#include <fstream>
#include <stdexcept>
#include <string>

namespace klstream {

struct LogisticModel {
    double bias{0.0};
    double weights[FeatureSnapshot::kDim]{};

    // Score a single feature vector; returns P(positive class).
    [[nodiscard]] double score(const float x[FeatureSnapshot::kDim]) const noexcept {
        double z = bias;
        for (std::size_t i = 0; i < FeatureSnapshot::kDim; ++i)
            z += weights[i] * static_cast<double>(x[i]);
        return 1.0 / (1.0 + std::exp(-z));
    }

    // Loads the plain-text file written by train_classifier.py:
    //   bias=<value>
    //   w0=<value>
    //   w1=<value>
    //   ...
    static LogisticModel load(const std::string& path) {
        std::ifstream f(path);
        if (!f) throw std::runtime_error("cannot open model weights file: " + path);
        LogisticModel m;
        std::string token;
        while (f >> token) {
            auto pos = token.find('=');
            if (pos == std::string::npos) continue;
            std::string name = token.substr(0, pos);
            double val = std::stod(token.substr(pos + 1));
            if (name == "bias") {
                m.bias = val;
            } else if (name.size() > 1 && name[0] == 'w') {
                std::size_t idx = std::stoul(name.substr(1));
                if (idx < FeatureSnapshot::kDim) m.weights[idx] = val;
            }
        }
        return m;
    }

    // Writes a model to a file in the same format load() expects.
    void save(const std::string& path) const {
        std::ofstream f(path);
        if (!f) throw std::runtime_error("cannot write model weights file: " + path);
        f << "bias=" << bias << "\n";
        for (std::size_t i = 0; i < FeatureSnapshot::kDim; ++i)
            f << "w" << i << "=" << weights[i] << "\n";
    }

    // Construct a trivial zero model (all weights = 0, bias = 0).
    // Used in integration tests where model quality is irrelevant.
    static LogisticModel zero() { return LogisticModel{}; }
};

} // namespace klstream
