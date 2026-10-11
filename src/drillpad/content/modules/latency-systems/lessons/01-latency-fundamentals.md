# Latency Fundamentals: What the Numbers Mean

## Overview

Latency is the primary design constraint in order-driven finance. Confusing latency metrics (P50 vs P99.9, throughput vs latency tail, measurement environment bias) has cost careers.

This lesson teaches you to:
1. Distinguish percentile latency from mean/throughput
2. Spot when latency numbers are misleading (measurement environment, isolation, hardware variability)
3. Reason about latency budgets in a system

---

## Key Concepts

### Percentile Latency vs Throughput

Latency is always a distribution, never a single number.

```
Timeline of 1000 requests (sorted by time-to-complete):
                        
P50  (median):    ███████████                    (500 faster, 500 slower)
P95  (95th %ile): ███████████████████            (50 slower)
P99  (99th %ile): ████████████████████████       (10 slower)
P99.9 (tail):     ████████████████████████████   (1 slower)

Throughput is how many you can pump through per second, independent of latency.
High throughput + high P99.9 means you're dropping quality of life for users.
```

**Interview probe:** Why does a trade-execution system care about P99.9 latency, not P50?

### Hardware and Measurement Environment

Your number is only meaningful in your test harness.

```
Measurement axis:  Apple M4 laptop vs EC2 c6i.large (dedicated instance vs shared noisy neighbor)
CPU isolation:     Shared machine vs pinned core vs dual-core affinity
Turbo/governor:    Enabled (dynamic) vs disabled (reproducible)
Warm cache:        First run (cold) vs 100th run (hot)

Example: OrderBookEngine's order-matching latency is:
- Local (Apple M4, shared, turbo on): P50=0.21 us, P99.9=4.7–5.2 us
- EC2 (isolated core, turbo off):    P50=0.208 us, P99.9=3.09–3.23 us

EC2 is BETTER, not worse, because the measurement is fair. Apple's numbers are
useful for "is this obviously broken?" but not for publication/resume claims.
```

**Interview probe:** You have latency numbers from your laptop and from staging. Which one do you publish? Why?

---

## Latency Budget and System Decomposition

A real order matching engine has multiple stages; each adds latency.

```
Ingestion pipeline for a single order:
    
    Order arrives
         ↓ [≤1 us ingestion: check message format]
    Parse message header
         ↓ [≤1 us format validation]
    Validate order (price, size, symbol)
         ↓ [≤0.5 us lookup symbol in symbol table]
    Symbol table lookup
         ↓ [10–50 us contention if no pool; ≤0.1 us with pre-allocated pool]
    Allocate order struct (from memory pool)
         ↓ [≤1 us in-order tree insert (best case) or ≤10 us (rebalance)]
    Insert into buy/sell trees
         ↓ [≤5 us: match against best ask/bid, fill until exhausted]
    Matching loop (scan fill)
         ↓ [≤0.5 us serialize response]
    Format response
         ↓
    P50 total: 0.2 us (in-memory, no matches)
    P99.9 total: 5–10 us (tree rebalance + multiple fills)
```

Each stage's latency is *visible* to the system as a whole. If one stage doesn't
have a latency budget (e.g., "just allocate memory without pre-pooling"), it
becomes a latency tail contributor.

---

## The Clock Matters: Actual Microseconds vs Nanoseconds

```
Wall-clock time units (remember these):
    1 second = 10^9 nanoseconds = 10^6 microseconds

On a CPU at ~3 GHz (3 billion cycles per second):
    1 nanosecond = ~3 CPU cycles
    1 microsecond = ~3000 CPU cycles
    1 millisecond = ~3 million CPU cycles

Memory latencies (approximate, measured in cycles → time):
    L1 cache hit:     4 ns (~12 cycles)
    L2 cache hit:     12 ns (~36 cycles)
    L3 cache hit:     40 ns (~120 cycles)
    Main memory hit:  100 ns (~300 cycles)
    Disk read (SSD):  1–10 microseconds

A 5 microsecond P99.9 order-match latency means:
    - Every 200 orders (1 in 200, on average) takes ≥5 us
    - That's ~15,000 CPU cycles lost to memory stalls, branching misses, or OS scheduling
    - In an order book with 100K orders/sec, that's 500 tail-latency orders per second
    - On a single-core affinity, even one context switch (10–100 us) ruins the latency profile
```

**Numeric exercise:** Your system can do 1M orders/sec at P50=1 us. What is the raw latency budget (in CPU cycles) for a single order on a 3 GHz CPU?

---

## Story Card: OrderBookEngine Benchmarking Lesson

**Setup:** Built a low-latency order book in C++20. Expected lock-free SPSC queue to beat mutex + queue, as textbooks say.

**Decision:** Benchmark locally (laptop) vs staged environment (EC2). Local showed 1.04x speedup; EC2 showed 0.56–0.59x slowdown.

**Result:** Lock-free queue *loses* on EC2 because the benchmark pins both threads to a *single shared core*. The spinning thread steals CPU time from the consumer, making the mutex version *faster* because it blocks and yields the core. Dual-core affinity (re-running with `taskset -c 0,1`) was pending.

**What changed:** 
- Recognized measurement environment as the primary driver, not the algorithm
- Learned that "lock-free = faster" is a harmful assumption without contention modeling
- Documented both results publicly instead of smoothing over the unexpected one

**In an interview:**
- Q: "Why did your lock-free queue lose on EC2?"
- A: "Contention model. On a single shared core, spinning is actively harmful. Textbook lock-free is best-case-specific: multiple cores + high contention. I had neither."

**Resume bullet (honest version):**
*"Built low-latency order book with sub-microsecond P50 latency on EC2 isolated core. Lock-free SPSC queue was slower than mutex on single-core contention; documented both configurations in public benchmark (results/). "* 

Not: *"Built fastest order book with lock-free queue."*

---

## Q&A: Key Takeaways (Self-grade)

**Recall 1:** You observe P50=1 us, P99.9=10 us latency for order matching. What are two reasons the tail (P99.9) could be 10x the median?

*Must-say:*
- Tree rebalancing during inserts (worst-case O(log n) insert, not amortized)
- Memory stall: order struct not in L3 cache, falls through to main memory (~100 ns)
- OS context switch between producer/consumer threads
- Lock contention if queues or pools aren't isolated

*Model answer (pick 2):*
- Algorithm: std::map red-black tree rebalancing is O(log n) = O(10–15) operations worst-case; P50 hit fast path, P99.9 hits rebalance.
- Hardware: L3 cache misses (40 ns miss penalty) or main memory misses (100 ns penalty) during lookup. With pre-allocated memory pools, misses are rare; without them, misses dominate P99.9.

**Probe 1:** You benchmark on your MacBook and on EC2 and get different numbers. How do you pick which one to quote on your resume?

*Expected:* EC2 isolated core, turbo off, because it's reproducible and fair. Laptop numbers are useful for "is this broken" but reflect your specific hardware.

**Probe 2:** You have a 5 us latency budget for order matching. The lock is taking 1 us, memory pool allocation is taking 0.5 us, tree insert is 0.1 us, and matching loop is 2 us. Where do you focus first?

*Expected:* Matching loop. It's the largest consumer. But also ask: can you pre-compute it? Are you scanning too many orders? Is there a fast-path (empty book vs. multiple fills)?

**Probe 3:** Your system processes 1M orders/sec and P99.9 tail is 10 us. How many orders per second see ≥10 us latency?

*Expected:* 1M * 0.001 = ~1000 orders/sec (roughly 1 in 1000).

---

## Questions for the Interviewer

- How does your company measure latency in staging vs production? Do you account for network round-trip?
- What's your P99.9 latency target for order matching? What's the business impact if you miss it by 2x?
- Do you use CPU pinning in production? How do you handle OS scheduling jitter?
