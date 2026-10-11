# Observing Latency: Flame Graphs and Tail Distribution

## Overview

A sub-microsecond latency system is worthless if you can't measure and debug it. This lesson covers:
1. Profiling tools: `perf`, flame graphs, and tail-latency attribution.
2. Interpreting flame graphs (what does CPU time actually mean?).
3. Tail vs mean: why P99.9 spikes come from unexpected places.
4. Production observability: histogram buckets and SLOs.

---

## Problem: Why Does P99.9 Spike?

You have a system with P50 latency 0.2 us, but P99.9 is 5 us (25x worse). Where does the extra 4.8 us come from?

Options:
1. Tree rebalancing (red-black tree insert worst-case O(log n)).
2. Cache miss (L3 miss = 40 ns, main memory miss = 100 ns, all else is 10–20 ns).
3. Memory allocation (page refill = 5–10 us).
4. OS scheduling (context switch = 10–100 us, worst-case).

**The only way to know is to measure.** Guess wrong, and you'll optimize the wrong thing.

---

## Tool: `perf` and Flame Graphs

`perf` is a Linux profiler that samples the CPU stack at regular intervals (e.g., every 1000 cycles, ~333 ns on a 3 GHz CPU).

```bash
# Run the order book benchmark under perf
perf record -F 10000 -g -- ./order-book-bench

# Generate a flame graph
perf script | stackcollapse-perf.pl | flamegraph.pl > bench.svg

# Open bench.svg in a browser (or Speedscope)
```

**Flame graph output:**

```
The x-axis is time (left to right = start to finish of benchmark run).
The y-axis is call stack depth (bottom = user code, top = kernel).
The height of each block is proportional to how much time was spent in that function.
The color is often random (or meaningful, depending on tool).
```

**Real example from OrderBookEngine:**

```
Top functions by time spent:
  1. OrderBook::add_order (40% of time)
  2. std::map::insert (red-black tree rebalance) (25% of time)
  3. malloc/free (10% of time)
  4. memcpy (5% of time)
  5. Everything else (20% of time)
```

**What this tells you:**
- If you want to optimize latency, target the top 40% (add_order).
- The red-black tree is the #2 consumer. Switching to a different data structure (e.g., skip list, heap) might help.
- malloc/free is still 10%, which means you're not using pre-allocated pools (or pools are leaking).

---

## Interpreting a Flame Graph

```
                    ┌──────────────────────────────────┐
                    │   benchmark() (main loop)        │
                    └──────────────────────────────────┘
                           ↙                      ↖
            ┌─────────────────────┐       ┌───────────────┐
            │  add_order()        │       │  match()      │
            └─────────────────────┘       └───────────────┘
                    ↙              ↖              ↙
        ┌──────────────┐    ┌────────────┐   ┌──────────┐
        │ map::insert()│    │ memcpy()   │   │ fill()   │
        └──────────────┘    └────────────┘   └──────────┘
             ↙         ↖
     ┌──────────┐   ┌──────────┐
     │ rebalance│   │ _rb_tree │
     └──────────┘   └──────────┘
      (tall, wide)  (short, narrow)
```

Reading this graph:
- **Width** = total time spent in this function (and its children).
- **Height** = call stack depth (how nested it is).
- **Tall and wide** = function is called many times and takes a lot of time (rebalance).
- **Short and narrow** = function is called few times or is fast (_rb_tree node access).

---

## Tail Latency Attribution

Flame graphs show *average* CPU time. To understand tail latency, you need a different approach.

```
Method 1: Conditional sampling
  Modify the profiler to only sample when latency exceeds a threshold (e.g., samples when elapsed time > 1 us).
  This gives you a "tail flame graph" showing what's happening in slow requests.
  
  Example: OrderBookEngine tail flame graph shows:
    - 60% in map::insert (tree rebalance)
    - 30% in memory access (cache miss, page fault)
    - 10% in lock/CAS (SPSC queue contention)

Method 2: Histogram + bucketing
  Collect latency percentiles: P50, P95, P99, P99.9
  For each bucket, record a sample flame graph.
  
  Example:
    P50 (0.2 us): flame graph shows mostly in-L3-cache memory access.
    P99.9 (5 us): flame graph shows map::insert + tree rebalance.
    
  This tells you: median latency is memory-bound, tail latency is tree-bound.

Method 3: Offline analysis
  Instrument the code: before/after timestamps around each operation.
  log(operation, start_us, end_us, lat_us, cause)
  
  Analyze: for lat_us > threshold, what was the operation?
  Result: tail latencies are clustered around tree rebalances and cache misses.
```

---

## Production Observability: SLOs and Histograms

In production, you can't always run `perf` (overhead, privacy). Instead, emit histogram metrics.

```cpp
// Latency histogram (milliseconds)
struct LatencyHistogram {
  std::atomic<uint64_t> buckets[20];  // [0.1, 0.2, 0.3, ... 1.0, >1.0 ms]
};

// After each order match:
void record_latency(uint64_t latency_us) {
  uint32_t bucket = std::min(19, (uint32_t)(latency_us / 100));  // 100 us per bucket
  ++histogram.buckets[bucket];
}

// Periodic flush (every minute):
void emit_metrics() {
  for (int i = 0; i < 20; ++i) {
    uint64_t count = histogram.buckets[i].exchange(0);
    emit_metric("order_match_latency", {
      {"bucket_us", i * 100},
      {"count", count}
    });
  }
}
```

**Metrics you want:**
- Count per bucket (what % of requests are in each latency range?)
- P50, P95, P99, P99.9 (computed from buckets)
- SLO miss rate: % of requests > SLO threshold (e.g., > 10 us)

**Example SLO:**
```
SLO: 99% of order matches complete in < 10 us.
Metric: If (count > 10 us) / total > 0.01, page oncall.
```

---

## Real Example: OrderBookEngine Flame Graph

From the published benchmark (EC2 c6i.large, 1M orders, available at speedscope.app):

```
Top time consumers (cumulative, from the flame graph):
  add_order():           65%
    └─ map::insert():    40% (red-black tree insert + rebalance)
    └─ find():          15% (lookup best price)
    └─ memcpy():        10% (copy order to pool)
  
  match():              20%
    └─ tree walk:       10%
    └─ fill alloc:      10%
  
  queue operations:     10%
    └─ SPSC push/pop:    8%
    └─ yield/spin:       2%
  
  Other (system):        5%
```

**Interpretation:**
- The #1 target for optimization is map::insert (40% of time).
- A faster data structure (skip list, B-tree) could reduce this.
- However, the absolute latency is already small (~0.2 us P50). Optimizing away 40% might save 0.08 us, dropping P50 to 0.12 us. This is useful, but not game-changing.
- The bigger win is ensuring tree rebalance doesn't blow up P99.9. This means confirming that rebalance is amortized (rare) and not hitting worst-case.

---

## Story Card: OrderBookEngine Benchmark + Speedscope

**Setup:** Built order book with sub-microsecond latency, claimed it publicly. But had only profiled locally; never published the flame graph.

**Decision:** Ran `perf` on EC2, generated flame graph, published it on Speedscope (speedscope.app is an interactive flame graph viewer).

**Result:** Community could click around, hover over functions, see actual time distribution. Questions like "where's the time going?" were answerable by the data, not assertions.

**What changed:**
- Realized a flame graph is as important as the latency number itself. P50=0.2 us is meaningless without context; the graph shows you're memory-bound on L3 cache, not CPU-bound.
- Learned that publishing the raw `perf` data (or an interactive viewer) builds trust more than a single number.

**In an interview:**
- Q: "How do you know where the latency is coming from?"
- A: "Profiling. I publish the flame graph so anyone can inspect it. For tail latency, I also run conditional sampling: only capture stack traces when latency exceeds 1 us. That shows me the tree rebalance is the tail driver, not the happy path."

---

## Q&A

**Recall 1:** In a flame graph, what does the width of a function's block represent? What does the height represent?

*Must-say:*
- Width = total time spent in that function (CPU time used).
- Height = call stack depth (how many nested function calls deep).

*Model answer:*
- Wider block = function uses more CPU time (sum of all its samples).
- Taller stack (higher Y position) = function is called from deeper in the call stack.
- A tall, wide block is a deep function that runs a lot. Optimize there first.

**Probe 1:** Your P99.9 latency is 10x your P50 latency. You profile and see that the tail flame graph has a lot of time in malloc, but the P50 graph doesn't. What does this tell you?

*Expected:*
- malloc is not the bottleneck for median latency (fast path dominates).
- But malloc page-refill (slow path, rare) is the tail driver.
- Solution: use pre-allocated pools to guarantee O(1) allocation.

**Probe 2:** You instrument your code with before/after timestamps. For P99.9 latencies (say, 10 us), you see:
  - 40% of time in tree insert.
  - 30% of time in memory access (cache miss).
  - 20% in lock/CAS (SPSC queue).
  - 10% other.

Where do you focus first?

*Expected:*
- Tree insert is the largest, but check: is it *always* tree insert in the tail? Or does it vary?
- If tree insert is consistently the 40% top consumer, optimize it (different data structure).
- If it varies, investigate: are the tail cases (10 us) from different code paths? Maybe sometimes you're filling multiple orders (longer matching loop), sometimes memory is slow.

**Numeric 1:** Your flame graph shows 1000 samples (perf ran with 1000 Hz sampling rate for 1 second). A function has 100 samples in the graph. What % of time was spent in that function?

*Working:* 100 / 1000 = 10%.

**Numeric 2:** You emit a histogram with 10 buckets, each 100 us wide. In a 1-hour run, bucket[9] (900–999 us) has 50 counts. What's the percent of requests > 900 us?

*Working:*
- 1 hour = 3600 seconds. If you have 1M requests/sec, total = 3.6 billion requests.
- 50 requests > 900 us out of 3.6B = 50 / 3.6e9 ≈ 0.0000014% (incredibly rare).

---

## Questions for the Interviewer

- Do you run production profiling (low-overhead), or only staging profiling?
- How do you collect tail latency attribution? Conditional sampling, instrumentation, or post-hoc analysis?
- What's your SLO for order matching latency? How do you monitor it?
- Do you publish flame graphs or latency histograms to the team?
