# Memory Pools, RAII and Latency Predictability

## Overview

Memory allocation is invisible to most applications until you profile for latency. This lesson teaches:
1. Why `malloc` has tail latency spikes (page refills, locks).
2. How to design predictable allocation with pre-allocated pools.
3. RAII (Resource Acquisition Is Initialization) as a latency guarantee.
4. Thread-local vs shared pools (trade-offs).

---

## Problem: Malloc Tail Latency Spikes

```
Time (log scale):
Alloc 1:    10 ns (fast path, allocator has free block)
Alloc 2:    10 ns
...
Alloc 100:  10 ns
Alloc 101:  10,000 ns (10 us!)  ← Page refill: allocator calls madvise(), 
                                  OS kernel page-faults, returns new memory
Alloc 102:  10 ns
Alloc 103:  10 ns
...
Alloc 2000: 5,000 ns (5 us)      ← Another page refill
Alloc 2001: 10 ns
```

**Why?** 
- The allocator maintains a pool of free blocks.
- Once the pool is exhausted, it asks the OS for more pages.
- The OS page-fault handler is not real-time; it can take microseconds.
- If another process is also allocating, locks contend, making it worse.

**Consequence:**
- P50 latency is fine (~10 ns per allocation).
- P99.9 latency is dominated by the rare page-fault events (~5–10 us).
- Your latency budget is ruined by an invisible allocator spike.

---

## Solution 1: Pre-Allocated Pool (Bounded, Predictable)

```
Startup phase (once, not repeated):
  1. Allocate 10 MB in one go via malloc (or mmap with MAP_HUGETLB for 2 MB pages).
  2. Carve into fixed-size slots (e.g., 256 byte Order structs).
  3. Maintain a free-list stack of available slots.

Runtime (for each order):
  Allocation: pop from stack → O(1), ~10 ns, no kernel call.
  Deallocation: push to stack → O(1), ~10 ns, no kernel call.
```

**Memory layout:**

```
Allocated at startup (10 MB contiguous):
  ┌─────────────────────────────────────────────┐
  │ Order[0] │ Order[1] │ Order[2] │ ... │ Order[39999] │
  │ 256 B    │ 256 B    │ 256 B    │     │ 256 B        │
  └─────────────────────────────────────────────┘
  All of this is allocated upfront in one malloc() call.
  No page refills during runtime.

Free-list (stack of pointers):
  ┌─────────────────────┐
  │ Order[39999]        │ ← pop() returns this
  │ Order[39998]        │
  │ Order[39991]        │
  │ Order[39990]        │
  │ ...                 │
  └─────────────────────┘
```

---

## Implementation: Thread-Local vs Global Pool

### Option 1: Global Pool with Mutex (Simple, Some Contention)

```cpp
class GlobalOrderPool {
  std::vector<Order> storage;
  std::stack<Order*> free_list;
  std::mutex lock;
  
public:
  Order* allocate() {
    std::lock_guard<std::mutex> g(lock);
    Order* o = free_list.top();
    free_list.pop();
    return o;  // 10 ns + ~100 ns lock acquisition
  }
  
  void deallocate(Order* o) {
    std::lock_guard<std::mutex> g(lock);
    free_list.push(o);  // 10 ns + ~100 ns lock acquisition
  }
};
```

**Pros:** Simple, shared memory efficient.
**Cons:** Lock contention if producer and consumer both allocate frequently. ~100–200 ns lock overhead per allocation.

### Option 2: Thread-Local Pools (No Contention, More Memory)

```cpp
thread_local std::stack<Order*> free_list;  // Each thread has its own

Order* allocate() {
  Order* o = free_list.top();
  free_list.pop();
  return o;  // 10 ns, NO lock
}

void deallocate(Order* o) {
  free_list.push(o);  // 10 ns, NO lock
}
```

**Pros:** No lock contention, ~10 ns constant latency.
**Cons:** Each thread wastes memory (needs its own pre-allocated block). If producer allocates 100 orders/thread and consumer deallocates them, each thread needs its own pool.

**Real-world trade-off:**
- Order book matcher has 1–2 matcher threads (not many).
- Thread-local pools are cheap: 2 threads * 10 MB pool = 20 MB (acceptable).
- Contention on global pool would kill latency if both threads allocate simultaneously.
- → Use thread-local pools.

---

## RAII and Latency Guarantees

RAII (Resource Acquisition Is Initialization) means: constructor allocates, destructor deallocates. This is a latency guarantee if done right.

```cpp
class OrderPoolGuard {
  Order* order;
  OrderPool& pool;
  
public:
  OrderPoolGuard(OrderPool& p) : pool(p) {
    order = pool.allocate();  // Acquire in constructor
  }
  
  ~OrderPoolGuard() {
    pool.deallocate(order);   // Release in destructor
  }
  
  Order* get() { return order; }
};

// Usage in matching loop:
for (auto incoming = queue.dequeue(); incoming; incoming = queue.dequeue()) {
  OrderPoolGuard guard(order_pool);
  Order* o = guard.get();
  
  *o = *incoming;  // Copy order data
  insert_into_book(o);  // Insert into buy/sell trees
  
  // If exception or early return happens, destructor runs, order is freed
}
```

**Guarantee:** The Order is *always* deallocated, even if an exception is thrown during matching. No resource leak, no dangling pointers.

**Latency guarantee:** Deallocation is O(1), ~10 ns. No deferred cleanup queue, no background thread, no garbage collection pauses.

---

## Tail Latency Breakdown with Pools

Real measurement (OrderBookEngine, EC2):

```
Operation with pre-allocated pool:
  Allocate from pool:      ~10 ns
  Copy order data:         ~30 ns
  Insert into buy tree:    ~100 ns (red-black tree insert, amortized)
  Check for matches:       ~20 ns
  If match, allocate fill: ~10 ns
  Deallocate fill:         ~10 ns
  ─────────────────────
  P50 (no fill):           ~170 ns
  P99.9 (with fill):       ~300 ns

Without pre-allocated pool (malloc per order):
  Allocate via malloc:     ~10 ns (fast path) or ~10,000 ns (page refill)
  Everything else:         ~200 ns
  ─────────────────────
  P50 (mall fast path):    ~210 ns
  P99.9 (malloc refill):   ~10,200 ns

50x difference in P99.9! All from memory allocation.
```

---

## Story Card: FlowState Temporal Join Memory

**Setup:** Built FlowState temporal alignment engine in Rust. Data flow: read partitions → merge-join trades/quotes → output result. Early version used Rust's default allocator.

**Decision:** Profiled and found allocation overhead in the merge-scan loop. Switched to pre-allocating output buffers.

**Result:** Reduced per-join latency spikes by ~40% (from 2.5 ms to 1.8 ms on 10M row joins). Throughput increased from 45 joins/sec to 75 joins/sec.

**What changed:**
- Recognized that "functional" Rust code (let x = Vec::new() in each iteration) pays allocation tax.
- Learned that pooling and reuse in hot loops is worth the "mutability cost" in Rust (requires &mut, breaks functional style).
- Trade-off: code is less elegant, latency is much better.

**In an interview:**
- Q: "Rust is all about memory safety. Doesn't pooling add complexity?"
- A: "Yes, but latency constraints override. We pool output buffers, use `unsafe` only in the hot merge loop (with SAFETY comment), and validate correctness with property tests. The alternative is paying 10–100 us per join, which is unacceptable."

---

## Q&A

**Recall 1:** Explain why `malloc` has tail latency spikes. What causes them?

*Must-say:*
- Allocator maintains free blocks. Once exhausted, it asks the OS for more pages.
- OS page-fault handler is not real-time.
- Multiple processes competing for memory increase contention.

*Model answer:*
- `malloc` returns cached free blocks in ~10 ns (O(1) stack pop).
- After ~100 allocations (depending on block size), free pool is exhausted.
- Next `malloc` call hits the allocator's slow path: calls `mmap()` or `brk()` (kernel calls).
- OS kernel acquires a lock on the page table, allocates a page, returns memory (≥1 us, often 5–10 us).

**Probe 1:** You have a global pool with one mutex. Producer thread allocates, consumer thread deallocates. What's the lock contention pattern?

*Expected:*
- Both threads lock and unlock on every allocation/deallocation.
- Contention is low if they don't allocate at exactly the same time (unlikely for producer/consumer).
- But even uncontended, lock acquisition is ~100 ns per call (memory barrier + atomic CAS).
- Thread-local pools would be better.

**Probe 2:** Your order book pre-allocates 100K orders at startup. What if you run out?

*Expected:*
- The application should reject incoming orders (or queue them, but that adds latency).
- Alternatively, implement a "overflow" allocator that mallocates more, but marks these as slow and monitors them.
- In production, you size pools based on peak load + 20% buffer (requires capacity planning).

**Numeric 1:** You pre-allocate 1M order structs at 256 bytes each. How much memory (in GB)?

*Working:* 1M * 256 bytes = 256 MB = 0.25 GB.

**Numeric 2:** Allocation with global pool takes ~110 ns (10 ns + 100 ns lock). Without pool, malloc fast path is 10 ns, malloc slow path (page refill) is 5000 ns. If 1% of allocations hit the slow path, what's the P99 latency?

*Working:*
- With pool: P99 is still ~110 ns (lock is deterministic).
- Without pool: P99 is dominated by the 1% slow path: 0.99 * 10 ns + 0.01 * 5000 ns ≈ 60 ns average, but P99 is 5000 ns (the slow path percentile).

---

## Questions for the Interviewer

- How do you size memory pools for peak load? Do you have monitoring for pool exhaustion?
- Do you use thread-local or global pools? Have you benchmarked both?
- What's your deallocation strategy for failed orders? (Quick return to pool vs deferred cleanup?)
- How do you handle exceptions or errors in the allocation path without leaking memory?
