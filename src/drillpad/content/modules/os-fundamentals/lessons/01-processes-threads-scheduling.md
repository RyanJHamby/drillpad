# Processes, Threads, and Scheduling: The Cost of Context Switching

## Overview

This lesson covers:
1. Process vs thread vs coroutine (isolation, overhead, cost)
2. Context switching (what happens, why it's expensive)
3. CPU scheduling (preemption, time slices, latency)
4. How to minimize context switches (CPU affinity, busy-waiting)

---

## Process vs Thread vs Coroutine

```
PROCESS:
  - Own memory space (virtual address space isolated)
  - Own file descriptors
  - Create cost: ~1 microsecond (fork) + page table setup
  - Context switch: expensive (TLB flush, cache miss)
  - Use: Isolation, separate programs

THREAD:
  - Shared memory (same virtual address space)
  - Own stack, registers
  - Create cost: ~100 nanoseconds (much cheaper)
  - Context switch: cheaper than process (no TLB flush)
  - Use: Parallel work within same program

COROUTINE (async/await, fibers):
  - Shared memory, shared OS thread
  - Explicit yield (not preempted)
  - Create cost: ~50 nanoseconds (just allocate stack)
  - Context switch: no OS involvement, ~100 nanoseconds
  - Use: Thousands of concurrent tasks without OS overhead
```

**Example: Web server handling 10,000 connections**

```
Process-per-connection:
  10,000 processes × 1µs creation = 10ms overhead
  Each process: ~50MB memory (10GB total) ← memory explosion
  Context switching: massive (10k context switches per second)
  Verdict: No

Thread-per-connection:
  10,000 threads × 100ns creation = 1ms overhead
  Each thread: ~8MB stack (80GB stack memory!) ← still bad
  Context switching: 10k switches/sec, each ~5µs = 50ms overhead
  Verdict: No, too much context switching

Coroutine-per-connection (async/await):
  10,000 coroutines × 50ns = 0.5µs overhead
  Each coroutine: ~4KB stack (40MB total) ← tiny
  Context switching: user-level, 0 OS overhead
  Verdict: Yes, this is how async web servers work (Node.js, Python asyncio)
```

---

## Context Switching Cost

When OS switches from thread A to thread B:

```
Time 0: Thread A running
  CPU: A's registers loaded, A's cache hot
  TLB: A's page table translations cached

Time 100ns: OS decides to switch
  Interrupt: Timer interrupt fires (usually 10ms slice)
  
Time 100ns+: Save state
  Save A's registers to memory
  Save A's instruction pointer (where to resume)
  Flush TLB? Maybe, depends on OS
  
Time 200ns: Load new thread
  Load B's registers from memory
  Load B's instruction pointer
  Flush cache? No, but cache is now wrong for A
  
Time 300ns: Thread B runs
  B's code runs, but cache misses happen
  L3 miss rate: ~40% initially (A's data still in cache)
  Each miss: ~100 nanoseconds

Result: Context switch overhead = 200ns (register save/load) + cache miss penalty
Total: ~1-5 microseconds per context switch
```

**Latency spike from context switch:**

```
Thread A running tight loop (order book matching)
  Normal latency: 0.2 microseconds per order
  
At 10ms boundary: OS timer interrupt
  Context switch to unrelated thread B
  B's cache miss, takes 5µs
  B yields after 10ms (uses full time slice)
  
OS switches back to A
  A's cache is now cold (B evicted A's data)
  First few orders take 5µs instead of 0.2µs
  
Result: Latency spike from 0.2µs → 5µs (25x worse!)
```

---

## Scheduling: Preemption and Time Slices

**Preemptive scheduling (default on Linux, Windows):**

```
OS assigns each thread a time slice (usually 10ms)

Thread A: runs for 10ms
OS interrupt: "A, your time is up"
OS context switch: A → B (100-1000ns overhead)
Thread B: runs for 10ms
OS interrupt: "B, your time is up"
OS context switch: B → C
Thread C: runs for 10ms
...
Result: All N threads get fair share, but constant context switching
```

**Cooperative scheduling (user-level, async/await):**

```
Coroutine A: runs until await point
Coroutine A: yield, "I'm waiting for I/O"
Coroutine B: runs until await point
Coroutine B: yield, "I'm waiting for I/O"
Coroutine C: runs until await point
...
Result: No OS overhead, but requires code to yield (explicit)
```

**Real-time (critical for trading):**

```
SCHED_FIFO: First-in-first-out, no time slices
  High-priority thread A preempts everything
  Thread A runs until it yields (explicit)
  No timer interrupts (no latency spikes from OS)
  
Linux example:
  struct sched_param param;
  param.sched_priority = 90;  // High priority
  pthread_setschedparam(thread, SCHED_FIFO, &param);
```

---

## CPU Affinity: Bind Thread to Core

**Without affinity (default):**

```
Thread A: starts on Core 0
  Loads data into Core 0's L3 cache
  Runs for 10ms, cache is hot
  
OS timer interrupt: switch to Core 1
  Core 1 doesn't have A's cache
  A reloads data from main memory (100ns per load)
  L3 miss rate: 100% initially
  
Result: Cache pollution, latency spike
```

**With affinity (CPU pinning):**

```
Thread A: pinned to Core 0
  Loads data into Core 0's L3 cache
  
OS timer interrupt: still on Core 0 (maybe switch to another thread pinned to Core 0)
  Same L3 cache
  Cache hit rate: high
  Latency: stable
  
Result: Predictable latency, no cache thrashing
```

**Linux example:**

```cpp
#include <pthread.h>
#include <sched.h>

cpu_set_t set;
CPU_ZERO(&set);
CPU_SET(0, &set);  // Pin to Core 0
pthread_setaffinity_np(thread, sizeof(cpu_set_t), &set);
```

**Real impact: Order book latency**

```
Without affinity: P99.9 latency = 5 microseconds (context switches)
With affinity:    P99.9 latency = 0.3 microseconds (no context switches)

16x improvement just from not switching CPUs!
```

---

## Busy-Waiting vs Sleep

When waiting for work:

```
Busy-waiting (spin loop):
  while (!has_work) { }  // Check constantly
  
  Pros: Immediately notice work (no latency)
  Cons: Consume 100% CPU even if idle
  
Sleep:
  pthread_wait(&condition, &mutex);
  
  Pros: Low CPU usage
  Cons: Wake-up latency (typically 10-100µs)
  
Hybrid (spin then sleep):
  for (int i = 0; i < 1000; i++) {
    if (has_work) break;
    usleep(1);  // Short spin, then sleep
  }
  
  Pros: Low latency (if work comes within 1ms) + low CPU (after 1ms)
```

**Trading systems:**

```
Market order arrives every 50 microseconds on average
Expected: Should process within 50µs to stay ahead

Busy-waiting: process in <1µs (always ready)
  Cost: 1 core @ 100% CPU (but market is open 6.5 hours, worth it)

Sleep: process in 10-100µs (wake-up latency)
  Cost: lower CPU, but might miss market tick
  
Real systems: Usually busy-wait on hot threads, sleep on background
```

---

## Most Likely Interview Questions

**Q1: "Your latency spiked to 5µs sometimes. Why?"**

A: "Context switch. Thread was pinned to Core 0, but OS preempted it at 10ms boundary. Thread resumed on a different core (or even same core, but cache was evicted). L3 miss rate spiked, latency went up 25x. Fix: use SCHED_FIFO to avoid preemption, or increase time slice."

**Q2: "How many threads should I use?"**

A: "Depends on workload. I/O-bound (web server): more threads than cores (10-100x), because most are blocked. CPU-bound (compute): threads = cores (maybe +1-2 for scheduling gaps). Too many threads = constant context switching = low throughput."

**Q3: "Should I use async/await or threads?"**

A: "Async/await if: thousands of connections, mostly I/O-bound (network latency hides user-level overhead). Threads if: <1000 concurrent tasks, need simplicity. Async: lower overhead, but explicit yield needed. Threads: higher overhead, but implicit (preempted at any time)."

**Q4: "How do you reduce context switch latency?"**

A: "Three tactics: (1) CPU affinity: pin thread to core, avoids TLB/cache misses. (2) Real-time priority (SCHED_FIFO): avoid OS preemption. (3) Reduce thread count: fewer threads = fewer context switches. Trading: 1-2 hot threads pinned to 2 cores, rest at low priority."

**Q5: "What's the difference between process and thread?"**

A: "Process: isolated memory (own virtual address space), slower to create (~1µs), expensive context switch (TLB flush). Thread: shared memory, faster (~100ns), cheaper context switch. Use processes for isolation (separate services). Use threads for parallelism within same program."

---

## Key Takeaways

1. **Context switch costs: 200ns-5µs** (register save/load + cache miss)
2. **CPU affinity prevents cache thrashing** (pin thread to core)
3. **SCHED_FIFO avoids preemption** (no time slices, explicit yield only)
4. **Coroutines have 100x less overhead than threads** (no OS involvement)
5. **Threads = I/O-bound, coroutines = scale
