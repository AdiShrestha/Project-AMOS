#pragma once
#include "features.hpp"
#include "numeric.hpp"
#include <array>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>

namespace bpfeat {
class LogisticModel {
public:
    LogisticModel(double bias, std::array<double, FEATURE_DIMENSION> weights) : bias_(bias), weights_(weights) {
        if (!std::isfinite(bias)) throw std::invalid_argument("nonfinite model bias");
        for (auto weight : weights) if (!std::isfinite(weight)) throw std::invalid_argument("nonfinite model weight");
    }
    double score(const std::array<double, FEATURE_DIMENSION>& x) const {
        double z = bias_;
        for (std::size_t i = 0; i < x.size(); ++i) {
            if (!std::isfinite(x[i])) throw std::invalid_argument("nonfinite feature");
            z += weights_[i] * x[i];
        }
        if (!std::isfinite(z)) throw std::overflow_error("nonfinite logit");
        if (z >= 0) return 1 / (1 + std::exp(-z));
        auto e = std::exp(z);
        return e / (1 + e);
    }
    static LogisticModel load(const std::string& path) {
        std::ifstream stream(path);
        if (!stream) throw std::runtime_error("cannot open model: " + path);
        std::string line;
        if (!std::getline(stream, line) || line != "schema=bpfeat.taobao.features.v2")
            throw std::runtime_error("model feature schema mismatch");
        std::set<std::string> seen;
        double bias = 0;
        std::array<double, FEATURE_DIMENSION> weights{};
        while (std::getline(stream, line)) {
            auto equals = line.find('=');
            if (equals == std::string::npos || line.find('=', equals + 1) != std::string::npos)
                throw std::runtime_error("malformed model field");
            auto key = line.substr(0, equals), text = line.substr(equals + 1);
            if (!seen.insert(key).second || text.empty()) throw std::runtime_error("duplicate/empty model field");
            double value = finite_decimal(text);
            if (key == "bias") bias = value;
            else if (key.size() == 2 && key[0] == 'w' && key[1] >= '0' && key[1] <= '6')
                weights[static_cast<std::size_t>(key[1] - '0')] = value;
            else throw std::runtime_error("unknown model field");
        }
        if (stream.bad() || seen.size() != FEATURE_DIMENSION + 1) throw std::runtime_error("incomplete model");
        return LogisticModel(bias, weights);
    }
    void save(const std::string& path) const {
        std::ofstream stream(path);
        diagnostic_format(stream);
        stream << "schema=" << FEATURE_SCHEMA << '\n' << std::setprecision(std::numeric_limits<double>::max_digits10);
        stream << "bias=" << bias_ << '\n';
        for (std::size_t i = 0; i < weights_.size(); ++i) stream << 'w' << i << '=' << weights_[i] << '\n';
        stream.flush();
        if (!stream) throw std::runtime_error("model write failed");
        stream.close();
        if (!stream) throw std::runtime_error("model close failed");
    }
    double bias() const noexcept { return bias_; }
    const std::array<double, FEATURE_DIMENSION>& weights() const noexcept { return weights_; }
private:
    double bias_;
    std::array<double, FEATURE_DIMENSION> weights_;
};
}
