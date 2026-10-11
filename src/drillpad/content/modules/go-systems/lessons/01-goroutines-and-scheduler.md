# Goroutines & the Go Scheduler: M:N Threading, Work Stealing, Fairness

## The Problem

You spawn 10,000 goroutines to fetch from 10,000 different URLs. Expected: 10,000 concurrent requests. Reality: Your CPU has 8 cores. How does Go handle this?

```
Traditional: 1 goroutine = 1 OS thread
  10,000 goroutines = 10,000 threads
  OS can only run 8 at once (8 cores)
  Context switch: 1-5 microseconds per switch
  Overhead: Terrible

Go: M:N scheduling
  10,000 goroutines mapped to 8 OS threads (M:N)
  Goroutine is lightweight (~2KB stack)
  OS thread is heavyweight (~2MB stack)
  
Cost:
  10,000 goroutines: 20MB
  10,000 OS threads: 20GB
  20,000x difference!
```

---

## Go Scheduler Architecture

```
CPU-local run queues:

Core 0: [G1, G2, G3]      <- Goroutines
  ├─ OS Thread (M)
  └─ OS Thread (M)

Core 1: [G4, G5, G6]
  ├─ OS Thread (M)
  └─ OS Thread (M)

Core 2: [G7, G8]
  ├─ OS Thread (M)

Core 3: (empty, idle)

Scheduler:
  1. Each P (processor) has local queue of Gs
  2. Each M (thread) executes Gs from P's queue
  3. When M blocks on syscall: P gets new M
  4. Work stealing: Idle P steals from busy P's queue
```

**Key insight:** Goroutines are user-space threads scheduled by Go runtime, not OS.

---

## Context Switching Cost

```
Normal case:
  Goroutine runs → syscall blocks → Scheduler switches to next G
  Cost: Very cheap (~nanoseconds to context switch in user space)

Worst case:
  Go runtime decides: G has run long enough, switch to next G
  Current G has hot data in CPU cache
  New G cold cache miss
  Cost: Higher (cache miss penalty)

Go 1.2+: Preemption points
  Regular function calls
  Loops can't be preempted (prevents fairness issues)
```

---

## Work Stealing

```
Scenario: Uneven load distribution

P0 queue: [G1(heavy), G2, G3, ...]  (100 goroutines)
P1 queue: [G50]  (1 goroutine, finishes quick)

P1 finishes G50:
  Option A: Idle (wait)
  Option B: Steal from P0 (take one)
  
Go: Option B (work stealing)
  P1 steals G2 from P0
  Both P0 and P1 are now busy
  Load balanced!
```

**Trade-off:** Stealing adds latency (check lock, steal) but improves throughput.

---

## Interview Pattern: Goroutine Design

```
Q: "You're building a web scraper.
   Need to fetch 1M URLs concurrently.
   What goroutine pool size?"

Options:
  A) 1M goroutines (one per URL)
  B) 1000 goroutines (limited pool)
  C) Dynamic (start with 10K, add more as needed)

Strong answer:
  "1M goroutines would work (they're cheap).
  But: Each goroutine blocks on network I/O
  Better: Connection pool + limited goroutines
  
  Reasoning:
    - 1M goroutines = 2GB memory (acceptable)
    - But: Network bottleneck, not compute
    - Can't open 1M TCP connections (OS limit ~65K per machine)
    - Better: 10K goroutines + connection pool
      Each goroutine: fetch URL → return connection to pool
      
  Recommendation: 10K goroutines (matches OS connection limit)
    Cost: 20MB memory (cheap)
    Latency: All URLs queued, fetch in batches
    Benefit: No OS-level bottleneck"
```

---

## Checklist: Goroutine Design

- [ ] Goroutine pool size appropriate (10-100x cores typical)
- [ ] Goroutine leaks checked (all goroutines eventually exit)
- [ ] Context cancellation handled (graceful shutdown)
- [ ] Mutex/channel contention monitored
- [ ] GOMAXPROCS set correctly (default: NumCPU)
- [ ] Goroutine profiling enabled (pprof)

## Common Mistakes

1. **"1 goroutine per request, unlimited"**
   - Resource exhaustion under load
   - Limited pool + queue better

2. **"Goroutines are free"**
   - 2KB stack + scheduler overhead
   - 1M goroutines is reasonable, 100M is expensive

3. **"No need for context"**
   - Context for cancellation, timeouts
   - Critical for graceful shutdown

4. **"Mutexes are bad, use only channels"**
   - Channels good for synchronization
   - Mutexes good for shared state
   - Use both appropriately
