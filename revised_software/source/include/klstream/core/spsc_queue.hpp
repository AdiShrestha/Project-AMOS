// include/klstream/core/spsc_queue.hpp
#pragma once
#include "config.hpp"
#include <atomic>
#include <cassert>
#include <cstddef>
#include <memory>
#include <new>
#include <optional>
#include <type_traits>
#include <thread>
#include <chrono>

namespace klstream {

// ── SPSCQueue<T> ─────────────────────────────────────────────────────────
//
// A bounded, lock-free, single-producer / single-consumer ring buffer.
//
// CORRECTNESS CONTRACT:
//   * Exactly one thread calls push() or try_push() at a time (the producer).
//   * Exactly one thread calls pop() or try_pop() at a time (the consumer).
//   * These two threads may be different OS threads.
//   * T must be trivially copyable (POD-like).
//
// MEMORY LAYOUT (cache-line padded to prevent false sharing):
//
//   [padding 0]          <- start on cache line boundary
//   write_idx_           <- producer writes, consumer reads (release/acquire)
//   [padding 1]          <- isolate write_idx_ from read_idx_
//   write_idx_cached_    <- producer's local shadow of read_idx_ (relaxed)
//   [padding 2]
//   read_idx_            <- consumer writes, producer reads (release/acquire)
//   [padding 3]          <- isolate read_idx_ from write_idx_
//   read_idx_cached_     <- consumer's local shadow of write_idx_ (relaxed)
//   [padding 4]
//   capacity_            <- const after construction
//   buffer_              <- actual ring, heap-allocated, cache-line aligned
template <typename T>
class SPSCQueue {
    static_assert(std::is_trivially_copyable_v<T>,
        "SPSCQueue<T>: T must be trivially copyable. "
        "Wrap complex types in std::shared_ptr.");

public:
    // capacity must be a power of 2 and >= 2.
    explicit SPSCQueue(std::size_t capacity = DEFAULT_QUEUE_CAPACITY)
        : capacity_(capacity)
        , buffer_(static_cast<T*>(
            ::operator new(capacity * sizeof(T),
                           std::align_val_t{CACHE_LINE_SIZE})))
    {
        assert(capacity >= 2 && "SPSCQueue capacity must be >= 2");
        assert((capacity & (capacity - 1)) == 0 &&
               "SPSCQueue capacity must be a power of 2");
    }

    ~SPSCQueue() {
        ::operator delete(buffer_,
            std::align_val_t{CACHE_LINE_SIZE});
    }

    // Non-copyable, non-movable
    SPSCQueue(const SPSCQueue&)            = delete;
    SPSCQueue& operator=(const SPSCQueue&) = delete;
    SPSCQueue(SPSCQueue&&)                 = delete;
    SPSCQueue& operator=(SPSCQueue&&)      = delete;

    // ── Producer side ─────────────────────────────────────────────────────

    [[nodiscard]] bool try_push(const T& val) noexcept {
        const std::size_t wi = write_idx_.load(std::memory_order_relaxed);
        const std::size_t next_wi = (wi + 1) & (capacity_ - 1);

        if (next_wi == write_idx_cached_) {
            write_idx_cached_ = read_idx_.load(std::memory_order_acquire);
            if (next_wi == write_idx_cached_) {
                return false; // Queue is full
            }
        }
        buffer_[wi] = val;
        write_idx_.store(next_wi, std::memory_order_release);
        return true;
    }

    void push(const T& val) noexcept {
        int spin = 0, yields = 0;
        while (!try_push(val)) {
            if (spin < SPIN_BEFORE_YIELD) {
                ++spin;
#if defined(__aarch64__)
                __asm__ volatile("yield" ::: "memory");
#elif defined(__x86_64__)
                __asm__ volatile("pause" ::: "memory");
#endif
            } else if (yields < YIELD_BEFORE_SLEEP) {
                ++yields;
                std::this_thread::yield();
            } else {
                std::this_thread::sleep_for(
                    std::chrono::nanoseconds(SLEEP_NS));
            }
        }
    }

    // ── Consumer side ─────────────────────────────────────────────────────

    [[nodiscard]] bool try_pop(T* out) noexcept {
        const std::size_t ri = read_idx_.load(std::memory_order_relaxed);

        if (ri == read_idx_cached_) {
            read_idx_cached_ = write_idx_.load(std::memory_order_acquire);
            if (ri == read_idx_cached_) {
                return false; // Queue is empty
            }
        }
        *out = buffer_[ri];
        read_idx_.store((ri + 1) & (capacity_ - 1),
                        std::memory_order_release);
        return true;
    }

    std::optional<T> pop() noexcept {
        T val;
        if (try_pop(&val)) return val;
        return std::nullopt;
    }

    // ── Inspection ────────────────────────────────────────────────────────

    [[nodiscard]] double occupancy() const noexcept {
        const std::size_t wi = write_idx_.load(std::memory_order_relaxed);
        const std::size_t ri = read_idx_.load(std::memory_order_relaxed);
        const std::size_t used = (wi - ri + capacity_) & (capacity_ - 1);
        return static_cast<double>(used) / static_cast<double>(capacity_);
    }

    [[nodiscard]] std::size_t capacity() const noexcept { return capacity_; }

    [[nodiscard]] bool empty() const noexcept {
        return write_idx_.load(std::memory_order_acquire)
            == read_idx_.load(std::memory_order_acquire);
    }

private:
    alignas(CACHE_LINE_SIZE) std::atomic<std::size_t> write_idx_{0};
    alignas(CACHE_LINE_SIZE) std::size_t              write_idx_cached_{0};
    alignas(CACHE_LINE_SIZE) std::atomic<std::size_t> read_idx_{0};
    alignas(CACHE_LINE_SIZE) std::size_t              read_idx_cached_{0};

    const std::size_t capacity_;
    T*                buffer_;
};

} // namespace klstream
