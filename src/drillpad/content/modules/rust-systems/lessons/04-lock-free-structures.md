# Lock-Free Data Structures in Rust

## Overview

Lock-free structures eliminate mutex contention by using atomic operations. This lesson covers:
1. Why lock-free is hard in Rust (ownership + atomics)
2. Atomic operations: CAS, load/store ordering
3. Common patterns: MPSC queue, stack, ABA problem
4. When NOT to use lock-free (spoiler: usually mutex is fine)

---

## The Problem: Mutex Contention

When multiple threads compete for a mutex, the loser blocks. At scale, this kills throughput:

```rust
use std::sync::Mutex;

let counter = Mutex::new(0);

// Thread 1: increment
loop {
    let mut c = counter.lock().unwrap(); // Waits if locked
    *c += 1;
}

// Thread 2: increment
loop {
    let mut c = counter.lock().unwrap(); // Waits if locked
    *c += 1;
}

// If thread 1 holds lock for 100ns, thread 2 waits 100ns.
// At 1M operations/sec, you lose 10% throughput to waiting.
```

**Lock-free alternative:**

```rust
use std::sync::atomic::{AtomicUsize, Ordering};

let counter = AtomicUsize::new(0);

// Thread 1: increment
loop {
    counter.fetch_add(1, Ordering::Relaxed); // No wait
}

// Thread 2: increment
loop {
    counter.fetch_add(1, Ordering::Relaxed); // No wait
}

// Both proceed without blocking. No contention.
```

---

## Atomic Ordering: The Trap

Rust atomics let you choose ordering semantics. Most people pick wrong:

```rust
// WRONG: Overkill, slow
atomic.store(42, Ordering::SeqCst);

// RIGHT: Relaxed is fine for simple counters
atomic.store(42, Ordering::Relaxed);

// DEPENDS: RwLock update requires Release
atomic.store(42, Ordering::Release);
```

**Ordering levels (slow → fast):**

1. **SeqCst (Sequential Consistency):** Slowest, safest. Full barrier.
   - Use: When all operations must be globally ordered (rare).
   - Example: Global state that affects all threads.

2. **Release / Acquire:** Medium speed. One-way sync.
   - Use: Signaling between threads (producer → consumer).
   - Example: Producer stores data with Release, consumer reads with Acquire.

3. **Relaxed:** Fastest. No ordering guarantee.
   - Use: Independent counters, flags without synchronization.
   - Example: Telemetry counter (increments don't need to sync).

**Real example:**

```rust
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};

// Telemetry: no ordering needed
let requests_total = AtomicUsize::new(0);
requests_total.fetch_add(1, Ordering::Relaxed); // Fast

// Signaling: requires Release/Acquire
let ready = AtomicBool::new(false);
ready.store(true, Ordering::Release); // Producer

if ready.load(Ordering::Acquire) { // Consumer
    // Sees all stores before release
}
```

---

## CAS Pattern: Compare-and-Swap

CAS is the foundation of lock-free structures. It atomically reads, compares, and writes:

```rust
// Pseudocode
fn compare_exchange(
    &self,
    current: usize,
    new: usize,
) -> Result<usize, usize> {
    // Atomic:
    if *self == current {
        *self = new;
        Ok(current)
    } else {
        Err(*self) // Return what we actually found
    }
}
```

**Example: increment without atomic fetch_add**

```rust
use std::sync::atomic::{AtomicUsize, Ordering};

let counter = AtomicUsize::new(0);

// Incorrect: separate read + write race condition
let val = counter.load(Ordering::Relaxed);     // Read 5
let val = counter.load(Ordering::Relaxed);     // Still reads 5
counter.store(val + 1, Ordering::Relaxed);     // Write 6

// Correct: CAS loop
loop {
    let current = counter.load(Ordering::Relaxed);
    let new = current + 1;
    match counter.compare_exchange(
        current,
        new,
        Ordering::Relaxed,
        Ordering::Relaxed,
    ) {
        Ok(_) => break,  // Success
        Err(_) => {},    // Retry loop
    }
}
```

---

## The ABA Problem

ABA is a classic lock-free bug: you check `value == A`, but by the time you act, another thread changed it A → B → A.

```rust
// Stack pop: ABA bug
struct Node<T> {
    data: T,
    next: AtomicPtr<Node<T>>,
}

fn pop(head: &AtomicPtr<Node<T>>) -> Option<T> {
    loop {
        let current = head.load(Ordering::Acquire);
        if current.is_null() { return None; }
        
        // CAS: try to remove node
        let next = unsafe { (*current).next.load(Ordering::Acquire) };
        match head.compare_exchange(
            current,
            next,
            Ordering::Release,
            Ordering::Acquire,
        ) {
            Ok(_) => {
                unsafe { return Some(Box::from_raw(current).data) };
            }
            Err(_) => continue, // Retry
        }
    }
}

// Thread 1: pop (sees head = Node A)
// Thread 2: pop Node A, push Node A back (A → B → A)
// Thread 1: CAS sees head == A (outdated), pops Node A
// Result: Memory corruption (Node A freed, then accessed)
```

**Solution: Versioning (ABA counter)**

```rust
struct Versioned<T> {
    data: T,
    version: usize, // Incremented on each update
}

// Now: A.v1 → B → A.v2 (different, CAS fails)
```

---

## When NOT to Use Lock-Free

Lock-free is faster for **low-contention** scenarios. But:

```rust
// Contention: 10 threads, all writing same counter
// Lock-free: Each CAS retry costs ~200 cycles
// Mutex: Lock hold = 10 cycles, contention = rare
// Winner: Mutex (lower total latency)

// No contention: 1 producer, 1 consumer
// Lock-free: Direct atomic store/load
// Mutex: Lock acquire = 100 cycles
// Winner: Lock-free (much faster)
```

**Rule of thumb:**
- Single-threaded or read-heavy? → Mutex fine
- Contended writes? → Mutex often better
- Independent counters? → Atomics
- Single producer/consumer? → Lock-free queue

---

## Key Takeaways

1. **Lock-free ≠ always faster** (benchmark your contention)
2. **Ordering matters** (Relaxed for independent ops, Release/Acquire for sync)
3. **CAS loops retry on conflict** (exponential backoff if highly contended)
4. **ABA is real** (version your pointers)
5. **Rust prevents use-after-free** (compiler catches most mistakes, unlike C++)

---

## Q&A

**Q: What's the overhead of lock-free?**

Lock-free CAS loop:
- Uncontended: 1–2 cycles (direct store)
- Contested: 200–400 cycles per retry (cache miss, retry loop)

Mutex:
- Uncontended: ~10 cycles (lock acquire)
- Contested: 100–1000 cycles (wait in kernel)

**Q: Should I implement lock-free myself?**

Almost never. Use `crossbeam::queue` or `dashmap` instead. They're battle-tested and faster than your hand-rolled version.

**Q: How do I debug lock-free bugs?**

Lock-free bugs are non-deterministic. Use:
- ThreadSanitizer: `TSAN_OPTIONS=halt_on_error=0 cargo test --release`
- Loom: `#[loom::test]` for exhaustive checking
- Logging with timestamps
