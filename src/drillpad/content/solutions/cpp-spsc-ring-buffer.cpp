template <class T, std::size_t N>
class SpscQueue {
    static_assert(N > 0 && (N & (N - 1)) == 0, "N must be a power of two");
    static constexpr std::size_t kMask = N - 1;

    // Each index lives on its own cache line: producer writes tail_, consumer writes head_.
    alignas(64) std::atomic<std::size_t> head_{0};   // next slot to pop (written by consumer)
    alignas(64) std::atomic<std::size_t> tail_{0};   // next slot to push (written by producer)
    alignas(64) std::array<T, N> buf_{};

public:
    bool try_push(const T& v) { return emplace_impl(v); }
    bool try_push(T&& v) { return emplace_impl(std::move(v)); }

    bool try_pop(T& out) {
        const std::size_t h = head_.load(std::memory_order_relaxed);   // only we write head_
        if (h == tail_.load(std::memory_order_acquire)) return false;   // pairs with producer's release
        out = std::move(buf_[h & kMask]);
        head_.store(h + 1, std::memory_order_release);                  // hand the slot back to the producer
        return true;
    }

    std::size_t size_approx() const {
        return tail_.load(std::memory_order_relaxed) - head_.load(std::memory_order_relaxed);
    }
    static constexpr std::size_t capacity() { return N; }

private:
    template <class U>
    bool emplace_impl(U&& v) {
        const std::size_t t = tail_.load(std::memory_order_relaxed);    // only we write tail_
        if (t - head_.load(std::memory_order_acquire) == N) return false;   // full; pairs with consumer's release
        buf_[t & kMask] = std::forward<U>(v);
        tail_.store(t + 1, std::memory_order_release);                  // publish the slot contents
        return true;
    }
};
