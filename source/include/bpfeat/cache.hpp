#pragma once
#include "features.hpp"
#include <array>
#include <atomic>
#include <cmath>
#include <cstdint>
#include <memory>
#include <mutex>
#include <shared_mutex>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace bpfeat {

struct PublishedVersion {
    std::uint64_t key{0};
    std::uint64_t version_id{0};
    std::uint64_t latest_included_seq{0};
    std::uint64_t latest_event_ts_ns{0};
    std::array<double, FEATURE_DIMENSION> features{};
    std::uint64_t published_ts_ns{0};
};

struct CacheLookupResult {
    bool cold_start{true};
    PublishedVersion version{};
};

enum class PublicationPolicyType {
    ExactFresh,
    FixedCadence,
    ElapsedThreshold,
    AdaptivePressure
};

struct PublicationPolicyConfig {
    PublicationPolicyType type{PublicationPolicyType::ExactFresh};
    std::uint64_t cadence{1};              // For FixedCadence (U=k)
    std::uint64_t elapsed_threshold_ns{0}; // For ElapsedThreshold (U=delta_t)
    std::uint64_t cadence_max{16};         // For AdaptivePressure
};

struct QueryResult {
    std::uint64_t query_id{0};
    std::uint64_t key{0};
    std::uint64_t query_ts_ns{0};
    bool cold_start{true};
    std::uint64_t version_id{0};
    std::uint64_t latest_included_seq{0};
    std::uint64_t latest_event_ts_ns{0};
    std::array<double, FEATURE_DIMENSION> cached_features{};
    std::array<double, FEATURE_DIMENSION> fresh_features{};
    std::uint64_t event_time_age_ns{0};
    std::uint64_t update_staleness{0};
    double feature_error{0.0};
};

struct PublicationAccounting {
    std::uint64_t processed_updates{0};
    std::uint64_t published_updates{0};
    std::uint64_t coalesced_updates{0};
    std::uint64_t queries_served{0};
    std::uint64_t cold_queries{0};
    std::uint64_t warm_queries{0};

    bool is_conserved() const {
        return processed_updates == (published_updates + coalesced_updates);
    }
};

class VersionedCache {
public:
    explicit VersionedCache(std::size_t max_keys = 1000000) : max_keys_(max_keys) {
        if (!max_keys) throw std::invalid_argument("max_keys must be positive");
    }

    CacheLookupResult get(std::uint64_t key) const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        auto it = versions_.find(key);
        if (it == versions_.end()) {
            return {true, PublishedVersion{key, 0, 0, 0, {}, 0}};
        }
        return {false, it->second};
    }

    PublishedVersion publish(std::uint64_t key, std::uint64_t seq, std::uint64_t event_ts_ns,
                             const std::array<double, FEATURE_DIMENSION>& features,
                             std::uint64_t published_ts_ns) {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        auto it = versions_.find(key);
        std::uint64_t next_version_id = 1;
        if (it != versions_.end()) {
            next_version_id = it->second.version_id + 1;
        } else {
            if (versions_.size() >= max_keys_) {
                throw std::runtime_error("cache key budget exhausted; no silent drops");
            }
        }
        PublishedVersion version{key, next_version_id, seq, event_ts_ns, features, published_ts_ns};
        versions_[key] = version;
        total_publications_.fetch_add(1, std::memory_order_relaxed);
        return version;
    }

    std::size_t size() const {
        std::shared_lock<std::shared_mutex> lock(mutex_);
        return versions_.size();
    }

    std::uint64_t total_publications() const {
        return total_publications_.load(std::memory_order_relaxed);
    }

    void clear() {
        std::unique_lock<std::shared_mutex> lock(mutex_);
        versions_.clear();
        total_publications_.store(0, std::memory_order_relaxed);
    }

private:
    std::size_t max_keys_;
    mutable std::shared_mutex mutex_;
    std::unordered_map<std::uint64_t, PublishedVersion> versions_;
    std::atomic<std::uint64_t> total_publications_{0};
};

class PublicationCoordinator {
public:
    explicit PublicationCoordinator(PublicationPolicyConfig policy = {},
                                    double alpha = 0.1,
                                    std::size_t max_keys = 1000000)
        : policy_(policy), alpha_(alpha), features_(max_keys), cache_(max_keys) {
        if (!std::isfinite(alpha) || alpha <= 0.0 || alpha > 1.0) {
            throw std::invalid_argument("alpha must be in (0, 1]");
        }
    }

    std::pair<bool, PublishedVersion> process_event(const RawEvent& event, double pressure = 0.0,
                                                   std::uint64_t wall_clock_ns = 0) {
        auto snapshot = features_.update(event, alpha_, wall_clock_ns);
        latest_fresh_features_[event.key] = snapshot.x;
        ++accounting_.processed_updates;

        auto& tracking = key_tracking_[event.key];
        ++tracking.pending_updates;

        bool should_publish = false;
        switch (policy_.type) {
            case PublicationPolicyType::ExactFresh:
                should_publish = true;
                break;
            case PublicationPolicyType::FixedCadence:
                should_publish = (tracking.pending_updates >= policy_.cadence);
                break;
            case PublicationPolicyType::ElapsedThreshold:
                if (!tracking.has_published) {
                    should_publish = true;
                } else {
                    should_publish = (event.event_ts_ns >= tracking.last_published_event_ts_ns + policy_.elapsed_threshold_ns);
                }
                break;
            case PublicationPolicyType::AdaptivePressure: {
                double p = std::max(0.0, std::min(1.0, pressure));
                std::uint64_t k = 1 + static_cast<std::uint64_t>(p * (policy_.cadence_max - 1));
                k = std::max<std::uint64_t>(1, std::min(policy_.cadence_max, k));
                should_publish = (tracking.pending_updates >= k);
                break;
            }
        }

        if (should_publish) {
            std::uint64_t pub_ts = (wall_clock_ns > 0) ? wall_clock_ns : event.event_ts_ns;
            auto version = cache_.publish(event.key, event.seq, event.event_ts_ns, snapshot.x, pub_ts);
            tracking.has_published = true;
            tracking.last_published_event_ts_ns = event.event_ts_ns;
            tracking.last_published_seq = event.seq;
            tracking.pending_updates = 0;
            ++accounting_.published_updates;
            return {true, version};
        } else {
            ++accounting_.coalesced_updates;
            return {false, PublishedVersion{event.key, 0, 0, 0, {}, 0}};
        }
    }

    QueryResult query(std::uint64_t query_id, std::uint64_t key, std::uint64_t query_ts_ns) {
        auto lookup = cache_.get(key);
        ++accounting_.queries_served;
        if (lookup.cold_start) {
            ++accounting_.cold_queries;
        } else {
            ++accounting_.warm_queries;
        }

        std::array<double, FEATURE_DIMENSION> fresh_x{};
        auto it = latest_fresh_features_.find(key);
        if (it != latest_fresh_features_.end()) {
            fresh_x = it->second;
        }

        double error_sq = 0.0;
        for (std::size_t i = 0; i < FEATURE_DIMENSION; ++i) {
            double diff = lookup.version.features[i] - fresh_x[i];
            error_sq += diff * diff;
        }

        std::uint64_t age = 0;
        if (!lookup.cold_start) {
            age = (query_ts_ns >= lookup.version.latest_event_ts_ns)
                      ? (query_ts_ns - lookup.version.latest_event_ts_ns)
                      : 0;
        } else {
            age = query_ts_ns;
        }

        std::uint64_t staleness = 0;
        auto track_it = key_tracking_.find(key);
        if (track_it != key_tracking_.end()) {
            staleness = track_it->second.pending_updates;
        }

        return QueryResult{
            query_id,
            key,
            query_ts_ns,
            lookup.cold_start,
            lookup.version.version_id,
            lookup.version.latest_included_seq,
            lookup.version.latest_event_ts_ns,
            lookup.version.features,
            fresh_x,
            age,
            staleness,
            std::sqrt(error_sq)
        };
    }

    const VersionedCache& cache() const { return cache_; }
    const PublicationAccounting& accounting() const { return accounting_; }

private:
    struct PerKeyTracking {
        std::uint64_t pending_updates{0};
        std::uint64_t last_published_event_ts_ns{0};
        std::uint64_t last_published_seq{0};
        bool has_published{false};
    };

    PublicationPolicyConfig policy_;
    double alpha_{0.1};
    KeyedFeatures features_;
    VersionedCache cache_;
    std::unordered_map<std::uint64_t, std::array<double, FEATURE_DIMENSION>> latest_fresh_features_;
    std::unordered_map<std::uint64_t, PerKeyTracking> key_tracking_;
    PublicationAccounting accounting_;
};

} // namespace bpfeat
