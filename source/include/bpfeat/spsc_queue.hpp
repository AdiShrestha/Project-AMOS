#pragma once
#include <atomic>
#include <cstddef>
#include <limits>
#include <memory>
#include <stdexcept>
#include <type_traits>

namespace bpfeat {
// Exactly one producer and one consumer. The producer closes after its final
// successful push; concurrent external close is not an admission barrier.
// One slot is reserved. Occupancy is a bounded, approximate slot fraction.
template<class T> class SPSCQueue {
    static_assert(std::is_trivially_copyable_v<T> && std::is_default_constructible_v<T>);
public:
    explicit SPSCQueue(std::size_t slots) : slots_(validate(slots)), buffer_(new T[slots_]{}) {}
    SPSCQueue(const SPSCQueue&) = delete;
    SPSCQueue& operator=(const SPSCQueue&) = delete;
    bool try_push(const T& value) noexcept {
        if (closed_.load(std::memory_order_acquire)) return false;
        auto write = write_.load(std::memory_order_relaxed);
        auto next = (write + 1) & (slots_ - 1);
        if (next == read_.load(std::memory_order_acquire)) return false;
        buffer_[write] = value;
        write_.store(next, std::memory_order_release);
        return true;
    }
    bool try_pop(T& value) noexcept {
        auto read = read_.load(std::memory_order_relaxed);
        if (read == write_.load(std::memory_order_acquire)) return false;
        value = buffer_[read];
        read_.store((read + 1) & (slots_ - 1), std::memory_order_release);
        return true;
    }
    void close() noexcept { closed_.store(true, std::memory_order_release); }
    bool closed_and_empty() const noexcept {
        // Loading close before the indices acquires the producer's final push.
        return closed_.load(std::memory_order_acquire) && empty();
    }
    bool empty() const noexcept {
        return read_.load(std::memory_order_acquire) == write_.load(std::memory_order_acquire);
    }
    double occupancy() const noexcept {
        auto write = write_.load(std::memory_order_acquire);
        auto read = read_.load(std::memory_order_acquire);
        return static_cast<double>((write - read) & (slots_ - 1)) / usable_capacity();
    }
    std::size_t usable_capacity() const noexcept { return slots_ - 1; }
private:
    static std::size_t validate(std::size_t n) {
        if (n < 2 || (n & (n - 1)) || n > std::numeric_limits<std::size_t>::max() / sizeof(T))
            throw std::invalid_argument("queue slots must be a representable power of two >= 2");
        return n;
    }
    const std::size_t slots_;
    std::unique_ptr<T[]> buffer_;
    // Padding is a layout choice, not a measured assertion about host caches.
    alignas(128) std::atomic<std::size_t> write_{0};
    alignas(128) std::atomic<std::size_t> read_{0};
    std::atomic<bool> closed_{false};
};
}
