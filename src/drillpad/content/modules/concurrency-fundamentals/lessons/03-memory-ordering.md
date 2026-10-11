# Memory Ordering: Acquire/Release vs Sequential Consistency

## Why Memory Ordering Matters

Modern CPUs reorder instructions for performance:

```cpp
int x = 0, y = 0;

// Thread 1
x = 1;
y = 1;

// Thread 2
if (y == 1) {
    assert(x == 1);  // Safe?
}
```

On a single-threaded CPU: This assertion always passes.

On modern CPUs (with reordering): The assertion might fail!

**Why?** The CPU might execute:
1. Thread 1: y = 1 (instead of x = 1 first)
2. Thread 2: reads y == 1, reads x == 0
3. Thread 1: x = 1 (reordered from earlier)

The CPU reordered the writes to optimize cache usage.

## Memory Ordering Guarantees

When you use `std::atomic`, you can specify what ordering guarantee you want:

```cpp
x.store(1, std::memory_order_relaxed);     // No guarantee (fastest)
x.store(1, std::memory_order_release);     // One-way synchronization
x.load(std::memory_order_acquire);         // One-way synchronization
x.store(1, std::memory_order_seq_cst);     // Total order (slowest)
```

### Ordering Level 1: Relaxed (No Synchronization)

```cpp
std::atomic<int> x = 0, y = 0;

// Thread 1
x.store(1, std::memory_order_relaxed);
y.store(1, std::memory_order_relaxed);

// Thread 2
if (y.load(std::memory_order_relaxed) == 1) {
    // x might still be 0 (reordering is allowed)
}
```

**When to use:** Counters, statistics (order doesn't matter)

**Performance:** ~1 nanosecond overhead

### Ordering Level 2: Acquire/Release (One-Way Synchronization)

```cpp
std::atomic<bool> ready = false;
int data = 0;

// Thread 1 (writer)
data = 42;
ready.store(true, std::memory_order_release);  // Release: all prior stores are visible

// Thread 2 (reader)
if (ready.load(std::memory_order_acquire)) {   // Acquire: sees all stores before release
    assert(data == 42);  // Always true
}
```

**How it works:**
- `Release`: "Make all prior memory operations visible before this store"
- `Acquire`: "Don't proceed until I see all stores before the release"

**When to use:** Lock-free queues, producer-consumer, Mutexes (acquire lock, release lock)

**Performance:** ~3-5 nanoseconds overhead

### Ordering Level 3: Sequential Consistency (Total Order)

```cpp
std::atomic<int> x = 0, y = 0;

// Thread 1
x.store(1, std::memory_order_seq_cst);

// Thread 2
y.store(1, std::memory_order_seq_cst);

// Thread 3
if (y == 1 && x == 0) {
    // This is guaranteed impossible with seq_cst
}
```

**Guarantee:** All atomic operations happen in a single global order (like a lock, but on per-operation basis).

**Performance:** ~10-15 nanoseconds overhead

**When to use:** Complex synchronization where you're not sure (simplicity > performance)

## Real Example: Lock-Free Queue (Acquire/Release)

```cpp
struct LockFreeQueue {
    std::atomic<Node*> head;
    std::atomic<Node*> tail;
    
    void push(int value) {
        Node* n = new Node{value, nullptr};
        
        Node* old_tail;
        do {
            old_tail = tail.load(std::memory_order_acquire);  // Acquire
            // Modify list
        } while (!tail.compare_exchange_weak(old_tail, n, 
                                            std::memory_order_release,  // Release
                                            std::memory_order_acquire));
    }
    
    int pop() {
        Node* h = head.load(std::memory_order_acquire);  // Acquire: see push's changes
        int v = h->value;
        head.store(h->next, std::memory_order_release);  // Release: make pop visible
        delete h;
        return v;
    }
};
```

**Why acquire/release here?**
- Push writes new node, then updates tail (release)
- Pop reads tail (acquire), guaranteed to see the new node
- Minimal overhead compared to seq_cst

## Choosing the Right Ordering

| Scenario | Ordering | Why |
|---|---|---|
| **Counter (read/write by different threads)** | Relaxed | Order doesn't matter, pure speed |
| **Lock implementation** | Acq/Rel | Lock acquire = acquire, unlock = release |
| **Producer-consumer queue** | Acq/Rel | Producer releases, consumer acquires |
| **Multiple accesses with complex ordering** | Seq_cst | Safer (can prove correctness) |

## Pitfall: Forgetting Ordering

```cpp
std::atomic<bool> ready = false;
int data = 0;

// WRONG
data = 42;
ready.store(true);  // Default: seq_cst, but doesn't sync with consumer!

// Thread 2
if (ready.load()) {  // Default: seq_cst
    // data might still be 0 (CPU reordered the non-atomic write)
}
```

**Problem:** `data` is not atomic, so no ordering guarantee. CPU reorders freely.

**Fix:** Either atomize the data, or use a synchronization point:

```cpp
std::atomic<int> data = 0;
std::atomic<bool> ready = false;

// Thread 1
data.store(42, std::memory_order_relaxed);  // No sync needed, will be synced by ready
ready.store(true, std::memory_order_release);  // Release synchronizes with acquire

// Thread 2
if (ready.load(std::memory_order_acquire)) {
    assert(data.load(std::memory_order_relaxed) == 42);  // Safe (data written before ready release)
}
```

## Interview Pattern: Choosing Ordering

```
Q: "Implement a lock-free counter. What memory ordering?"

Weak answer:
  "Sequential consistency, it's safest"
  (❌ Correct but unnecessarily slow)

Strong answer:
  "Relaxed. Reasons:
  
  1. What are we synchronizing?
     Just incrementing a counter, no dependencies
  
  2. What's the threat?
     Thread 1 increments, Thread 2 increments
     Order matters only for the counter's correctness
     But a counter is inherently approximate at high scale
     (exact count is pointless if threads keep updating)
  
  3. Why relaxed is safe:
     - CAS guarantees atomicity (value updates atomically)
     - Memory ordering doesn't change that
     - Counter will have correct updates, just not ordered
  
  4. Cost:
     - Relaxed: ~1ns per op
     - Acquire/Release: ~3ns per op
     - Seq_cst: ~10ns per op
     
     For a counter that might be incremented 1M times/sec,
     that's 3-10 microseconds of overhead per second.
  
  If counter increments were part of a lock acquisition,
  then acquire/release would be correct (we're synchronizing with the lock)."

Why this signals good judgment:
  - You measured the cost (not abstract)
  - You chose the minimal ordering needed
  - You explained the synchronization requirements
```

## What This Signals

- You understand hardware memory models (not just "atomics are safe")
- You can choose the right ordering for performance
- You know acquire/release is the practical choice (faster than seq_cst)
- You're aware of non-atomic data still needs synchronization
