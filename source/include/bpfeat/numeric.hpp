#pragma once
#include <cmath>
#include <iomanip>
#include <limits>
#include <locale>
#include <sstream>
#include <stdexcept>
#include <string>

namespace bpfeat {
inline double finite_decimal(const std::string& text) {
    std::istringstream stream(text);
    stream.imbue(std::locale::classic());
    double value = 0;
    stream >> std::noskipws >> value;
    if (!stream || !stream.eof() || !std::isfinite(value))
        throw std::invalid_argument("expected a finite decimal number");
    return value;
}
inline void diagnostic_format(std::ostream& stream) {
    stream.imbue(std::locale::classic());
    stream.flags(std::ios::dec);
    stream.width(0);
    stream.precision(std::numeric_limits<double>::max_digits10);
}
}
