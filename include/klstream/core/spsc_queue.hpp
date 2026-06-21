#pragma once
// Lock-free Single-Producer Single-Consumer queue.
// Based on the classic Lamport ring-buffer; correctness requires
// that exactly ONE thread calls try_push() and exactly ONE calls try_pop().
// Capacity must be a power of two — enforced by static_assert.

#include "config.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <type_traits>
#include <new>          // std::hardware_destructive_interference_size

namespace klstream {

template <typename T>
class SPSCQueue {
    static_assert(std::is_trivially_copyable_v<T>,
                  "SPSCQueue<T>: T must be trivially copyable");

public:
    explicit SPSCQueue(std::size_t capacity = DEFAULT_QUEUE_CAPACITY)
        : capacity_(next_pow2(capacity))
        , mask_(capacity_ - 1)
        , buffer_(std::make_unique<T[]>(capacity_))
    {}

    // Producer: returns true if the item was pushed, false if full.
    [[nodiscard]] bool try_push(const T& item) noexcept {
        const auto head = head_.load(std::memory_order_relaxed);
        const auto next = (head + 1) & mask_;
        if (next == tail_.load(std::memory_order_acquire)) return false; // full
        buffer_[head] = item;
        head_.store((head + 1) & mask_, std::memory_order_release);
        return true;
    }

    // Consumer: returns true and fills *out if an item was available.
    [[nodiscard]] bool try_pop(T* out) noexcept {
        const auto tail = tail_.load(std::memory_order_relaxed);
        if (tail == head_.load(std::memory_order_acquire)) return false; // empty
        *out = buffer_[tail];
        tail_.store((tail + 1) & mask_, std::memory_order_release);
        return true;
    }

    // Approximate occupancy in [0,1]; safe to call from either thread.
    [[nodiscard]] double occupancy() const noexcept {
        auto h = head_.load(std::memory_order_relaxed);
        auto t = tail_.load(std::memory_order_relaxed);
        std::size_t used = (h >= t) ? (h - t) : (capacity_ - t + h);
        return static_cast<double>(used) / static_cast<double>(capacity_);
    }

    [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }
    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_acquire)
            == tail_.load(std::memory_order_acquire);
    }

private:
    static constexpr std::size_t kCacheLineSize =
#ifdef __cpp_lib_hardware_interference_size
        std::hardware_destructive_interference_size;
#else
        64;
#endif

    static std::size_t next_pow2(std::size_t n) noexcept {
        if (n < 2) return 2;
        --n;
        for (std::size_t shift = 1; shift < sizeof(n)*8; shift <<= 1) n |= n >> shift;
        return ++n;
    }

    const std::size_t capacity_;
    const std::size_t mask_;
    std::unique_ptr<T[]> buffer_;

    alignas(kCacheLineSize) std::atomic<std::size_t> head_{0};
    alignas(kCacheLineSize) std::atomic<std::size_t> tail_{0};
};

} // namespace klstream
