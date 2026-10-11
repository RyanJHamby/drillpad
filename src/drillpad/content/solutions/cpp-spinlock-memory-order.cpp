class SpinLock {
    // Own cache line: spinning threads hammer this word, keep it away from neighbouring data.
    alignas(64) std::atomic<bool> locked_{false};

    static void cpu_relax() noexcept {
#if defined(__aarch64__) || defined(__arm__)
        asm volatile("yield" ::: "memory");
#elif defined(__x86_64__) || defined(__i386__)
        asm volatile("pause" ::: "memory");
#else
        std::atomic_signal_fence(std::memory_order_seq_cst);
#endif
    }

public:
    SpinLock() = default;
    SpinLock(const SpinLock&) = delete;
    SpinLock& operator=(const SpinLock&) = delete;

    void lock() noexcept {
        unsigned spins = 1;
        for (;;) {
            // Test-and-set: acquire so everything in the critical section happens after the previous unlock.
            if (!locked_.exchange(true, std::memory_order_acquire)) return;
            // Test-and-test-and-set: wait on a plain read (shared cache line, no write traffic) with backoff.
            while (locked_.load(std::memory_order_relaxed)) {
                for (unsigned i = 0; i < spins; i++) cpu_relax();
                if (spins < 1024) spins <<= 1;
                else std::this_thread::yield();          // long wait: let the holder run if it was descheduled
            }
        }
    }
    bool try_lock() noexcept {
        // Cheap relaxed check first so a failed attempt does not steal the line in exclusive state.
        return !locked_.load(std::memory_order_relaxed) && !locked_.exchange(true, std::memory_order_acquire);
    }
    void unlock() noexcept {
        locked_.store(false, std::memory_order_release); // publish the critical section's writes
    }
};
