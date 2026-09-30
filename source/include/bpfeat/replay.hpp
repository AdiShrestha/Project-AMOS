#pragma once
#include "features.hpp"
#include <algorithm>
#include <cctype>
#include <istream>
#include <limits>
#include <string>
#include <vector>

namespace bpfeat {
inline std::vector<std::string> csv_cells(const std::string& line) {
    // This version deliberately accepts an unquoted integer-only schema.
    std::vector<std::string> result;
    std::size_t start = 0;
    for (;;) {
        auto comma = line.find(',', start);
        result.push_back(line.substr(start, comma == std::string::npos ? comma : comma - start));
        if (comma == std::string::npos) return result;
        start = comma + 1;
    }
}
inline std::uint64_t unsigned_integer(const std::string& value) {
    if (value.empty() || !std::all_of(value.begin(), value.end(), [](unsigned char c) { return std::isdigit(c); }))
        throw std::invalid_argument("unsigned integer required");
    std::size_t end = 0;
    auto parsed = std::stoull(value, &end);
    if (end != value.size()) throw std::invalid_argument("trailing integer content");
    return parsed;
}
class ReplayReader {
public:
    explicit ReplayReader(std::istream& stream) : stream_(stream) {
        std::string header;
        if (!std::getline(stream_, header)) throw std::invalid_argument("missing replay header");
        strip_cr(header);
        if (header != "seq,event_ts_ns,key,item_id,category_id,behavior_code")
            throw std::invalid_argument("replay schema mismatch; labels/legacy CSVs are not accepted");
    }
    bool next(RawEvent& event) {
        std::string line;
        if (!std::getline(stream_, line)) {
            if (!stream_.eof() || stream_.bad()) throw std::runtime_error("replay read failed");
            return false;
        }
        ++row_;
        strip_cr(line);
        auto cells = csv_cells(line);
        if (cells.size() != 6) throw std::invalid_argument("replay row width at line " + std::to_string(row_));
        auto behavior = unsigned_integer(cells[5]);
        if (behavior > 3) throw std::invalid_argument("unknown behavior at line " + std::to_string(row_));
        event = {unsigned_integer(cells[0]), unsigned_integer(cells[1]), unsigned_integer(cells[2]),
                 unsigned_integer(cells[3]), unsigned_integer(cells[4]), static_cast<std::uint8_t>(behavior)};
        if (seen_ && (event.seq <= previous_seq_ || event.event_ts_ns < previous_ts_))
            throw std::invalid_argument("replay IDs must increase and global event times must not decrease");
        previous_seq_ = event.seq;
        previous_ts_ = event.event_ts_ns;
        seen_ = true;
        return true;
    }
private:
    static void strip_cr(std::string& line) { if (!line.empty() && line.back() == '\r') line.pop_back(); }
    std::istream& stream_;
    std::uint64_t previous_seq_{0}, previous_ts_{0}, row_{1};
    bool seen_{false};
};
}
