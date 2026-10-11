# Concurrency: Mutexes vs RW Locks vs Atomics vs Semaphores

## When to Use Each

```
Problem: Shared data, multiple threads

Mutex (mutual exclusion):
  - Lock/unlock paired operations
  - Only one thread holds lock
  - Cost: 50-200 nanoseconds per lock/unlock
  - Use: General shared state

RW Lock (reader-writer lock):
  - Many readers OR one writer
  - Readers don't block each other
  - Writer blocks all readers
  - Cost: 100-300ns (higher overhead than mutex)
  - Use: Read-heavy workloads (>90% reads)

Atomic (lock-free):
  - CAS on single value
  - No blocking, no lock overhead
  - Cost: 5-20 nanoseconds
  - Use: Simple counters, flags, single shared value

Semaphore (counting):
  - Count-based, can wait if count=0
  - Cost: Same as mutex (blocking)
  - Use: Resource pooling (limited slots)
```

## Trading Interview: When Does Mutex Fail?

```
Q: "Your matching engine uses a mutex for the order book. Why is it slow?"

Weak answer:
  "Add more threads?"
  (❌ More threads = more contention)

Strong answer:
  "Mutex creates a bottleneck at scale.
  
  Problem: Every order requires lock.
   At 1M orders/sec, lock contention is severe.
   Threads spend more time waiting than processing.
  
  Solution: Lock-free data structures or partitioning.
   - Lock-free: No blocking, but complex
   - Partitioning: Shard orders by symbol
     Each partition has own mutex
     No contention across symbols
     Result: N-way parallelism instead of serialized
  
  I'd measure contention first (lock_stat, perf),
  then choose solution based on data."
  (✅ Shows understanding of bottleneck)
```

## RW Lock Trade-Off

```
Good for: Cache lookup
  99% reads (hit), 1% writes (invalidation)
  RW lock outperforms mutex
  
Bad for: Balanced workload
  50% reads, 50% writes
  RW lock overhead makes it slower than mutex
  
Measurement:
  RW Lock cost = 200ns per op
  Mutex cost = 100ns per op
  Crossover: 50/50 read/write ratio
```

## Interview Red Flags vs Green Flags

🚩 **Red flags:**
- "Mutex is always best" (depends on contention)
- "RW lock for everything read-heavy" (overhead costs)
- "Atomic is always faster" (only for single values)

✅ **Green flags:**
- "Measure contention first, pick lock type based on data"
- "Lock-free for latency-critical, mutex for simplicity"
- "Understand lock cost: ns per op, not just binary"

