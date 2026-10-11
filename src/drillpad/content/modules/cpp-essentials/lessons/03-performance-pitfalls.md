# Undefined Behavior, Data Races, and Interview Traps

## Overview

C++ is a high-performance language, but it punishes carelessness. Common pitfalls:
1. **Undefined behavior (UB):** The compiler can do anything (including crashing, silently producing wrong results).
2. **Data races:** Multiple threads reading/writing without synchronization.
3. **Performance traps:** Micro-optimizations that backfire.

This lesson teaches you to *recognize* these pitfalls in code review and avoid them in interviews.

---

## Undefined Behavior: Common Cases

**UB is scary because the compiler can optimize based on the assumption that UB won't happen.**

```cpp
// Example 1: Out-of-bounds access
int arr[10];
arr[100] = 5;  // UB: no bounds checking
// Compiler: "If this were executed, the program is UB. So this line will never be reached.
//           I'll delete it." (Result: arr[100] never written, but no error at runtime)

// Example 2: Integer overflow
int x = INT_MAX;
x++;  // UB: signed integer overflow
// Compiler: "x can never be INT_MAX+1, so if (x == INT_MIN) is always false.
//           I'll delete this if-block."

// Example 3: Use after free
int* p = new int(42);
delete p;
int val = *p;  // UB: reading freed memory
// Compiler: "This pointer was deleted, so this read never happens.
//           I'll delete this line." (Or: memory is reused, val gets garbage)

// Example 4: Null pointer dereference
int* p = nullptr;
int val = *p;  // UB
// Compiler: "p is null, so this is UB. I'll assume it never happens."

// Example 5: Data race (touched in next section)
std::atomic<int> x;
int val = x;  // OK: atomic read
x = val + 1;  // Wrong: non-atomic read-modify-write, race condition
```

**Key insight:** UB doesn't crash reliably. It might work on your machine, fail in production, or work on debug but fail on release (compiler optimizations).

**How to detect UB:**
- **AddressSanitizer (ASAN):** Detects out-of-bounds, use-after-free, memory leaks.
  ```bash
  clang++ -fsanitize=address -g prog.cpp -o prog
  ./prog  # If UB happens, ASAN reports it
  ```
- **UBSan (UndefinedBehaviorSanitizer):** Detects integer overflow, shift errors, etc.
  ```bash
  clang++ -fsanitize=undefined -g prog.cpp -o prog
  ```

---

## Data Races and Synchronization

**Problem:** Two threads access the same memory without synchronization.

```cpp
int counter = 0;

void increment_1000_times() {
  for (int i = 0; i < 1000; ++i) {
    counter++;  // Read counter, increment, write counter
    // RACE: Between read and write, another thread might modify counter
  }
}

// Thread 1: counter++ → read 0, write 1
// Thread 2: counter++ → read 0, write 1  (both read 0, both write 1!)
// Expected: counter = 2000 (threads interleaved 2000 times)
// Actual: counter = 2 (because both threads read before either writes)

// Result: UNDEFINED. Could be 2, could be 1000, could be 2000, could crash.
```

**Solutions:**

```cpp
// Solution 1: Mutex (mutual exclusion)
std::mutex m;
int counter = 0;

void increment_1000_times() {
  for (int i = 0; i < 1000; ++i) {
    std::lock_guard<std::mutex> lock(m);  // RAII: acquire on ctor, release on dtor
    counter++;
  }
}

// Solution 2: Atomic (fine-grained synchronization)
std::atomic<int> counter{0};

void increment_1000_times() {
  for (int i = 0; i < 1000; ++i) {
    counter++;  // Atomic increment: hardware-level synchronization
  }
}

// Solution 3: Lock-free data structure
std::vector<Order> orders;
std::mutex orders_lock;

void add_order(const Order& o) {
  std::lock_guard<std::mutex> lock(orders_lock);  // Protect the vector
  orders.push_back(o);
}

Order get_best_order() {
  std::lock_guard<std::mutex> lock(orders_lock);
  // ...
}
```

**Memory ordering (advanced):**

```cpp
std::atomic<int> x{0}, y{0};

// Thread 1
x.store(1, std::memory_order_relaxed);  // No synchronization barrier
y.store(1, std::memory_order_release);  // Synchronization point

// Thread 2
int val_y = y.load(std::memory_order_acquire);  // Synchronization point
int val_x = x.load(std::memory_order_relaxed);

// If val_y == 1, you're guaranteed val_x == 1 (acquire/release synchronizes).
// If using memory_order_relaxed everywhere, no guarantee (may see val_y=1, val_x=0).
```

**Interview angle:** What's the difference between `std::mutex` and `std::atomic`?

- **Mutex:** Heavy-weight, ensures mutual exclusion (only one thread in the critical section). Used for protecting complex data structures.
- **Atomic:** Light-weight, ensures individual operations are indivisible. Used for counters, flags, or simple shared data.

**Rule of thumb:** Use atomics for simple operations (increment, flag flip). Use mutexes for complex data structures (vectors, maps).

---

## Performance Pitfalls and Traps

### Pitfall 1: False Sharing

```cpp
struct Counter {
  std::atomic<int> c0;
  std::atomic<int> c1;  // Likely on same cache line (~64 bytes)
  // ...
};

Counter counters[8];  // Array of counters

// Thread 0: increment counters[0].c0
// Thread 7: increment counters[7].c1

// Both counters[0] and counters[7] may be on the same cache line.
// When thread 0 modifies c0, the CPU invalidates the cache line for thread 7.
// Thread 7's next access to c1 is a cache miss → latency spike.

// Result: Poor scalability (threads interfering with each other).
```

**Fix: Padding**

```cpp
struct Counter {
  std::atomic<int> value;
  char padding[64 - sizeof(std::atomic<int>)];  // Ensure each Counter is on its own cache line
};
```

### Pitfall 2: Lock Contention

```cpp
std::mutex global_lock;

for (int i = 0; i < 1000000; ++i) {
  std::lock_guard<std::mutex> lock(global_lock);
  counter++;
}

// If N threads compete for the same lock:
// - Thread 1 acquires lock, does work (1 us), releases.
// - Threads 2–N wait for the lock (queue up).
// - Throughput: ~1 us per operation, not N us.
// - Latency: 1 us + (N-1) * context switch overhead.

// Result: Single-threaded performance is better than multi-threaded!
```

**Fix: Lock-free or fine-grained locking**

```cpp
// Fine-grained: one lock per bucket
std::unordered_map<int, std::atomic<int>> per_key_counters;
std::vector<std::mutex> locks(num_buckets);

for (int i = 0; i < 1000000; ++i) {
  int bucket = hash(i) % num_buckets;
  std::lock_guard<std::mutex> lock(locks[bucket]);
  per_key_counters[i]++;  // Different threads likely hit different buckets
}

// Lock-free: use atomic or lock-free queue
std::atomic<int> counter{0};
counter++;  // No lock, true parallelism
```

### Pitfall 3: Cache Misses in Tight Loops

```cpp
struct Node {
  int value;
  Node* next;  // Pointer to next node in linked list
};

Node* head = /* large linked list */;

// Bad: traversal
int sum = 0;
for (Node* p = head; p != nullptr; p = p->next) {
  sum += p->value;  // p->next may not be in cache
}
// Each node access: 100+ ns (main memory miss), traversal is O(n) * 100 ns.

// Good: convert to array
std::vector<int> values;
for (Node* p = head; p != nullptr; p = p->next) {
  values.push_back(p->value);
}
for (int v : values) {
  sum += v;  // All in cache, 4 ns per access
}
// Same work, but cache-friendly.
```

### Pitfall 4: Unnecessary Allocations in Hot Path

```cpp
std::vector<Order> match_orders(const Order& buy) {
  std::vector<Order> matches;  // Allocation on every call
  for (const auto& sell : sell_orders) {
    if (can_match(buy, sell)) {
      matches.push_back(sell);  // Possible reallocation
    }
  }
  return matches;  // Return by value, copy
}

// Call 1000 times per second → 1000 allocations/sec → malloc contention.

// Fix: Reserve or use a reusable buffer
std::vector<Order> global_buffer;

void match_orders(const Order& buy, std::vector<Order>& out) {
  out.clear();  // Reuse, no allocation
  for (const auto& sell : sell_orders) {
    if (can_match(buy, sell)) {
      out.push_back(sell);
    }
  }
}
// Caller reuses the buffer across calls.
```

### Pitfall 5: Busy-Waiting (Spinning)

```cpp
// Bad: spin until flag is set
bool flag = false;
std::thread t([&]() {
  std::this_thread::sleep_for(std::chrono::ms(10));
  flag = true;
});

while (!flag) {
  // Busy wait: consuming 100% CPU, no progress for other threads
}

// Main thread: ~99% CPU, 10 ms latency
// OS scheduler: other threads starve

// Good: use condition variable
std::mutex m;
std::condition_variable cv;
bool flag = false;

std::thread t([&]() {
  std::this_thread::sleep_for(std::chrono::ms(10));
  {
    std::lock_guard<std::mutex> lock(m);
    flag = true;
  }
  cv.notify_one();
});

{
  std::unique_lock<std::mutex> lock(m);
  cv.wait(lock, [&]() { return flag; });
  // Main thread: sleeps, no CPU, woken when flag is set
}
```

---

## Debugging Performance Issues

**Interview question:** "Your order matching latency is 5 us P50, 50 us P99. How do you find the culprit?"

**Answer strategy:**

1. **Measure with profiler:**
   ```bash
   perf record -F 99 -g ./order_book
   perf report  # Which function is slow?
   ```

2. **Identify hotspot:**
   - Top 3 functions likely consume 70%+ of time.
   - Focus optimization there.

3. **Measure instrumentation impact:**
   - Add timing probes (gettimeofday, rdtsc) to sub-functions.
   - Measure before/after to isolate the culprit.

4. **Check for contention:**
   ```bash
   # Use ThreadSanitizer to detect data races
   clang++ -fsanitize=thread -g prog.cpp
   ./prog  # Reports races
   ```

5. **Profile memory:**
   - Cache misses: `perf stat -e cache-misses,cache-references ./prog`
   - Allocation overhead: `valgrind --tool=massif ./prog`

**Real example (OrderBookEngine):**

```
P99 latency spike from 1 us to 10 us after 100K orders.

Investigation:
  1. perf report → top function: std::map::insert (red-black tree rebalancing)
  2. Realized: After ~100K orders, tree height increases, rebalancing becomes common.
  3. Fix: Use flat_map (faster for reads, slower for inserts, but still better on average).
  4. Result: P99 stable at 3 us (eliminated the rebalancing spike).
```

---

## Story Card: Data Race in KV-Cache Quantization

**Setup:** vLLM inference, KV-cache is quantized in a background thread to save memory. Inference threads read from the cache.

**Bug:** Inference thread reads KV-cache while quantization thread is modifying it (no lock).

**Symptom:** P99.9 latency spikes to 100+ ms, intermittent crashes.

**Root cause:** Data race. Compiler optimizations assumed no race, reordered reads/writes, broke semantics.

**Fix:** Add a reader-writer lock (RwLock). Quantization: write lock (exclusive). Inference: read lock (shared).

```cpp
std::shared_mutex kv_cache_lock;

// Inference thread
std::shared_lock<std::shared_mutex> lock(kv_cache_lock);  // Read lock
float attn = compute_attention(kv_cache);  // Safe: multiple readers

// Quantization thread
std::lock_guard<std::shared_mutex> lock(kv_cache_lock);   // Write lock
quantize_kv_cache(kv_cache);  // Exclusive access
```

**Lesson:** Data races aren't always obvious. They manifest as rare P99.9 spikes, not crashes. Use ThreadSanitizer to catch them.

---

## Q&A

**Recall 1:** What's the difference between a data race and undefined behavior?

*Must-say:*
- **Data race:** Two threads access the same memory, at least one writes, without synchronization. May or may not cause UB (depends on alignment, access type).
- **Undefined behavior:** The C++ standard makes no guarantees about the result. Compiler can do anything.
- Data races often lead to UB, but not always (e.g., reading stale cache is usually not UB, just wrong results).

**Probe 1:** You see a data race in ThreadSanitizer: Thread 1 reads counter, Thread 2 writes counter. Should you use `std::atomic` or a `std::mutex`?

*Expected:*
- If only one write per counter: use `std::atomic` (lighter-weight).
- If multiple reads per write: `std::atomic` is faster.
- If protecting a complex structure (e.g., entire vector): use `std::mutex`.
- Rule of thumb: atomic for simple counters, mutex for complex data.

**Probe 2:** You have a tight loop that increments a global counter. You use `std::mutex` for safety. Performance is bad (single-threaded on 8 cores). What's the issue? How do you fix it?

*Expected:*
- Lock contention: all threads compete for the global lock.
- Fix 1: Use `std::atomic<int>` instead (no lock overhead).
- Fix 2: Use thread-local counters, then sum at the end (8 separate atomics, less contention).
- Fix 3: Use a lock-free counter (e.g., crossbeam::AtomicUsize in Rust-like patterns, but C++ has atomics built-in).

**Numeric 1:** Thread 1 acquires a lock (100 ns acquire time). Thread 2 waits. Thread 1 holds the lock for 10 us. What's the latency for Thread 2's critical section (100 ns work)?

*Working:*
- Thread 2 waits: 10 us (while Thread 1 holds lock) + 100 ns (acquire) + 100 ns (work) = ~10.2 us.
- But if Thread 1 holds the lock for a long time, Thread 2 may be descheduled (context switch), adding ms of delay.

**Numeric 2:** A linked list has 1000 nodes, each 256 bytes, scattered in memory (random order). CPU L3 cache is 20 MB. Traversal time?

*Working:*
- L3 can hold: 20 MB / 256 bytes per node = 80K nodes.
- Traversal hits all 1000 nodes, only ~80 fit in L3.
- Miss rate: (1000 - 80) / 1000 ≈ 92%.
- Each miss: 100 ns. Each hit: 5 ns.
- Average: 0.08 * 5 + 0.92 * 100 ≈ 92.4 ns per node.
- Total: 1000 * 92.4 ns ≈ 92 us.

---

## Questions for the Interviewer

- How do you detect data races in your codebase? (ThreadSanitizer, manual code review, production monitoring?)
- Have you had to optimize latency by changing data structures (e.g., array vs linked list)?
- What synchronization primitives do you use most? (mutex, atomics, lock-free queues, etc.)
- How do you balance correctness (safety) with performance (minimal locks)?
