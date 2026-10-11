# Lock-Free: Compare-and-Swap (CAS) Atomic Operations

## The Mutex Problem (Why Lock-Free Matters)

```
Mutex-protected counter:
  Thread A: lock(mutex) → read balance → write balance → unlock()
  Thread B: blocked waiting for lock
  Thread C: blocked waiting for lock
  
  At 1000 threads contending, threads spend 90% time waiting for lock.
  Context switching overhead: 1-10 microseconds per lock/unlock.
  
Lock-free counter:
  Thread A: atomic_increment(counter)  ← no lock, no wait
  Thread B: atomic_increment(counter)  ← runs in parallel
  Thread C: atomic_increment(counter)  ← all run simultaneously
  
  At 1000 threads, all make progress (no waiting).
  No context switch overhead.
  Latency: predictable, sub-microsecond.
```

---

## Compare-and-Swap (CAS) Instruction

```
CAS(address, expected, new):
  Read value at address
  IF value == expected:
    Write new to address
    Return true (success)
  ELSE:
    Do NOT write
    Return false (failed, someone changed it)

Example:
  counter = 5
  CAS(counter_addr, 5, 6)
    → Reads 5, expected 5 → writes 6 → returns true
  CAS(counter_addr, 5, 7)
    → Reads 6, expected 5 → fails → returns false (not 5 anymore)

Atomic: CPU guarantees no interference between read and write
```

---

## Lock-Free Increment using CAS

```c
// Mutex version (slow)
void increment_mutex(int* counter) {
    lock(mutex);
    (*counter)++;
    unlock(mutex);
}

// Lock-free version (fast)
void increment_cas(volatile int* counter) {
    while (true) {
        int old_val = *counter;
        int new_val = old_val + 1;
        if (atomic_cas(counter, old_val, new_val)) {
            break;  // Success
        }
        // If failed, retry (someone incremented between read and CAS)
    }
}

// Real usage
volatile int counter = 0;
atomic_increment(&counter);  // atomic_cas loop internally
```

---

## Real Scenario: Lock-Free Order Book

```
OrderBookEngine with 8 threads, all incrementing order count.

Mutex approach:
  Thread 1: lock → read 1000 → write 1001 → unlock (500 ns total, 300 ns waiting)
  Thread 2: waiting 300 ns
  ...
  Thread 8: waiting 2100 ns
  
  Worst case: Thread 8 waits 7 * 300ns = 2.1 µs to do a 50ns operation!

Lock-free approach:
  Thread 1: CAS(counter, 1000, 1001) → 50 ns (success, no waiting)
  Thread 2: CAS(counter, 1001, 1002) → 50 ns (success, runs in parallel!)
  ...
  Thread 8: CAS(counter, 1007, 1008) → 50 ns (success, no waiting)
  
  All threads: ~50 ns (no contention)
```

---

## CAS in Different Languages

```cpp
// C++ (atomic)
#include <atomic>
std::atomic<int> counter(0);
counter.store(5, std::memory_order_release);
int val = counter.load(std::memory_order_acquire);
bool success = counter.compare_exchange_strong(5, 6);

// Java
java.util.concurrent.atomic.AtomicInteger counter = new AtomicInteger(0);
boolean success = counter.compareAndSet(5, 6);
if (success) { /* got it */ }

// Rust
use std::sync::atomic::{AtomicI32, Ordering};
let counter = AtomicI32::new(0);
let success = counter.compare_exchange(5, 6, Ordering::Release, Ordering::Acquire);
```

---

## When CAS is Better than Mutex

```
Best for: Low contention (< 4 threads competing)
  - Most operations succeed on first try
  - No lock overhead
  - Better performance
  
Worse for: High contention (100+ threads)
  - Many retries (CAS fails, must retry)
  - Busy-waiting (spin loop burns CPU)
  - Worse than mutex (which has fair queuing)
  
Solution for high contention:
  - Use mutex (fair, reduces spinning)
  - Or: use lock-free data structure designed for scale
    (partitioning, per-thread counters)
```

---

## Q&A

**Recall 1:** CAS(counter, 5, 6) fails. Why?

*Must-say:*
- Counter is not 5 anymore
- Someone else changed it between your read and CAS
- You must retry with new value
- This is normal, not an error

**Probe 1:** CAS loop retries many times. What does that mean?

*Expected:*
- High contention (many threads fighting for same value)
- CAS keeps failing because value changes each time
- Sign: need to reduce contention (partition counter, use lock)

**Numeric 1:** 8 threads, each doing atomic_increment 1M times. Expected time?

*Working:*
- CAS success: 50 ns per operation
- 8M total operations * 50 ns = 400 ms single-threaded
- With 8 threads parallel: 400ms / 8 = 50 ms (ideal)
- Real: maybe 80-100 ms (some contention, cache misses)

---

## Questions for the Interviewer

- Have you used lock-free in production? (when?)
- At what thread count does mutex become worse than CAS?
- How do you test lock-free code? (race conditions are hard to reproduce)
- What's your policy: "prefer simplicity" or "optimize for latency"?

