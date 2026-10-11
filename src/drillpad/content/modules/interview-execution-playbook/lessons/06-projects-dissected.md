# Your Projects Dissected: Real Analysis & Interview Value

## What Interviewers Actually Care About

```
What you think:
  "I built a 1.8M orders/sec order book"
  
What interviewer hears:
  "I claim 1.8M. Did you measure it? What was the bottleneck?"
  
What separates good from great:
  "Real bottleneck was std::map rebalancing (not lock-free queue).
   Switched to sorted vector. P99.9 latency improved 2x.
   Here's the data."
```

**Interview signal:**
- Big number + no analysis: 60 points (sounds good, but unsubstantiated)
- Big number + real bottleneck + fix: 90 points (shows deep understanding)

## OrderBook Engine (1.8M Orders/Sec)

**What matters:**

```
Claim: 1.8M orders/sec, P99.9 0.21µs

Good interview answer:
  "Bottleneck wasn't what I thought (lock-free queue),
   it was actually data structure efficiency (std::map vs vector).
   
   Trade-off: sorted vector loses O(n) insertion,
   gains O(1) cache locality.
   
   Cost: Implementation complexity (manual binary search).
   Benefit: 2x latency improvement.
   
   Measurement: Used perf with CPU pinning, disabled turbo boost."

What interviewer learns:
  - You profiled (didn't guess)
  - You found real bottleneck (not obvious one)
  - You measured (not just "it's fast")
  - You made tradeoff decision (conscious choice)
```

**Interview questions to practice:**

1. "What was your actual bottleneck?" (Not lock-free queue!)
2. "How did you measure it?" (Perf, CPU affinity, methodology)
3. "What trade-offs did you make?" (Cache locality vs insertion speed)
4. "What would break at 10M orders/sec?" (Sharding strategy)

## Payment Adapter (6 Days → 5 Minutes)

**What matters:**

```
Claim: 6 days → 5 min (1728x speedup)

Good interview answer:
  "Bottleneck: Synchronous API calls to payment processor.
   
   Solution: Async batching + idempotency keys.
   
   Trade-offs:
   - Latency: user sees 202 instead of immediate response
   - Complexity: idempotency state, reconciliation job
   - Cost: additional storage for idempotency keys
   
   Result: 1728x speedup from parallelization.
   
   Failure mode: If payment processor down, we queue.
   Recovery: Manual reconciliation daily."

What interviewer learns:
  - You identified synchronous I/O as bottleneck
  - You understood the failure mode
  - You thought about recovery
  - You accepted latency tradeoff for throughput
```

**Interview questions to practice:**

1. "What if payment processor fails?" (Queue, retry, reconciliation)
2. "How do you prevent double-charge?" (Idempotency key)
3. "What's your recovery time?" (Next reconciliation job)

## vLLM Continuous Batching (2.4x Speedup)

**What matters:**

```
Claim: 2.4x speedup via continuous batching

Good interview answer:
  "Traditional batching: wait for N requests, process together.
   Problem: decode phase is memory-bound (can't use 100% compute).
   
   Continuous batching: interleave prefill (compute-bound) with
   decode (memory-bound) to keep GPU busy.
   
   Measurement:
   - Before: 40% GPU utilization (idle waiting for batches)
   - After: 85% GPU utilization (overlapped work)
   
   Trade-off: Complexity (scheduling algorithm is harder).
   
   Bottleneck: Network bandwidth (if multi-region, latency kills it)."

What interviewer learns:
  - You understand roofline model (compute vs memory bound)
  - You know GPU utilization matters
  - You measured utilization (not guessed)
  - You can reason about when technique applies
```

**Interview questions to practice:**

1. "Why 2.4x and not more?" (Other bottlenecks, not just batching)
2. "When does continuous batching fail?" (High latency demand, small batches)
3. "How would you debug low GPU utilization?" (Profiler, memory bottleneck check)

## FlowState (Streaming Alignment, Honest Benchmark)

**What matters:**

```
Claim: "Honest benchmark - Polars 1.4x faster, but here's why mine matters"

Good interview answer:
  "I initially claimed 1.8x faster. After honest benchmarking:
   - Polars: 100ms (optimized, single-threaded)
   - Mine: 140ms (streaming, handles unbounded data)
   
   So Polars 1.4x faster on this benchmark.
   
   But different workload: unbounded streaming alignment.
   Polars must load all data (OOM on 1TB stream).
   Mine: constant memory (streaming semantics).
   
   Trade-off: Peak performance vs unbounded scale.
   
   Interview signal: I measured honestly, even when result was bad.
   Showed when my approach wins (unbounded case)."

What interviewer learns:
  - You're honest about results (even unfavorable)
  - You understand workload differences
  - You don't oversell
  - You know your advantage (unbounded vs peak performance)
```

**Interview questions to practice:**

1. "Your project is slower than Polars. Why should we care?" (Different use case)
2. "How would you measure against a streaming competitor?" (Constant memory metric)
3. "What's the real win here?" (Unbounded data handling, not peak speed)

## Meta-Lesson: Interview Prep from Your Projects

```
For each project, prepare:

1. The Real Bottleneck
   (Not the obvious one you think, the one you actually found)
   
2. How You Measured It
   (Tools, methodology, CPU pinning, warmup runs)
   
3. The Trade-Off You Made
   (What you gave up, what you gained)
   
4. The Failure Mode
   (What breaks your optimization at scale)
   
5. When Your Approach Wins
   (Edge case where it's better than obvious solution)

Questions to answer before interview:
  - Can you defend every number on your resume?
  - Can you explain the bottleneck without sounding like you guessed?
  - Do you understand when your optimization applies vs when it doesn't?
  - Have you measured (not just assumed)?
```

