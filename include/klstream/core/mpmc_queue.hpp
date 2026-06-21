#pragma once
// Multi-Producer Multi-Consumer queue using a mutex + condition_variable.
// Used for the results/control plane where strict lock-freedom is not required
// and multiple threads may read or write. Hot-path queues (SPSC) are in
// spsc_queue.hpp; this is for secondary bookkeeping paths only.

#include "config.hpp"
#include <atomic>
#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>

namespace klstream {

template <typename T>
class MPMCQueue {
public:
    explicit MPMCQueue(std::size_t capacity = DEFAULT_QUEUE_CAPACITY)
        : capacity_(capacity)
    {
        buffer_.reserve(capacity_);
    }

    bool try_push(const T& item) {
        std::unique_lock<std::mutex> lk(mu_);
        if (buffer_.size() >= capacity_) return false;
        buffer_.push_back(item);
        lk.unlock();
        cv_.notify_one();
        return true;
    }

    std::optional<T> try_pop() {
        std::unique_lock<std::mutex> lk(mu_);
        if (buffer_.empty()) return std::nullopt;
        T item = buffer_.front();
        buffer_.erase(buffer_.begin());
        return item;
    }

    // Blocking pop; returns std::nullopt only when shutdown() has been called.
    std::optional<T> pop() {
        std::unique_lock<std::mutex> lk(mu_);
        cv_.wait(lk, [this]{ return !buffer_.empty() || shutdown_; });
        if (buffer_.empty()) return std::nullopt;
        T item = buffer_.front();
        buffer_.erase(buffer_.begin());
        return item;
    }

    void shutdown() {
        { std::lock_guard<std::mutex> lk(mu_); shutdown_ = true; }
        cv_.notify_all();
    }

    [[nodiscard]] std::size_t size() const {
        std::lock_guard<std::mutex> lk(mu_);
        return buffer_.size();
    }
    [[nodiscard]] double occupancy() const {
        std::lock_guard<std::mutex> lk(mu_);
        return static_cast<double>(buffer_.size()) / static_cast<double>(capacity_);
    }

private:
    const std::size_t capacity_;
    mutable std::mutex mu_;
    std::condition_variable cv_;
    std::vector<T> buffer_;
    bool shutdown_{false};
};

} // namespace klstream
