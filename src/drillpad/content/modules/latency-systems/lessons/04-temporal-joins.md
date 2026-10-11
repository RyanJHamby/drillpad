# Temporal Joins: As-Of Alignment and Watermarks

## Overview

Temporal joins (as-of joins) are fundamental in quantitative finance and streaming systems. This lesson covers:
1. The problem: joining out-of-order time-series data without look-ahead bias.
2. Algorithm: O(n + m) merge-scan on sorted data.
3. Streaming: watermark semantics and delayed arrival handling.
4. Real-world: FlowState's partitioned replay pipeline.

---

## The Problem: Look-Ahead Bias

Imagine you're building a training dataset for a price prediction model:

```
Trades (what you want to predict from):
  2024-01-15 10:00:00.001234567 ns, AAPL, $150.23, qty=100
  2024-01-15 10:00:00.002000000 ns, AAPL, $150.25, qty=50
  2024-01-15 10:00:00.005000000 ns, AAPL, $150.30, qty=200

Quotes (context: bid-ask at time of trade):
  2024-01-15 10:00:00.000500000 ns, AAPL, bid=$150.20, ask=$150.26
  2024-01-15 10:00:00.001000000 ns, AAPL, bid=$150.22, ask=$150.28
  2024-01-15 10:00:00.004000000 ns, AAPL, bid=$150.24, ask=$150.32
  2024-01-15 10:00:00.010000000 ns, AAPL, bid=$150.28, ask=$150.35

Goal: For each trade, find the most recent quote *at or before* that trade's timestamp.
```

**Look-ahead bias (WRONG):**
```
Trade @ 10:00:00.001 joined with quote @ 10:00:00.010 ← BAD, this quote came 9 ns later
Result: Model trains on future information, backtests look great, production fails.
```

**Correct (as-of join):**
```
Trade @ 10:00:00.001 joined with quote @ 10:00:00.001 (or earlier, whichever is latest)
Result: Model only sees data available at trade time.
```

---

## Algorithm: O(n + m) Merge-Scan

Data is pre-sorted by timestamp (this is a requirement).

```
Trades (sorted):                Quotes (sorted):
[1] T1 @ 001 ns                 [1] Q1 @ 0500 ns
[2] T2 @ 002 ns                 [2] Q2 @ 1000 ns
[3] T3 @ 005 ns                 [3] Q3 @ 4000 ns
                                [4] Q4 @ 10000 ns

Two pointers:
  t_ptr = 0 (current trade)
  q_ptr = 0 (current quote, or last quote ≤ trade timestamp)

Step 1: Trade T1 @ 001 ns
  Q1 @ 0500 ns > T1 @ 001 ns (quote is in the future)
  → Use the *previous* quote (none yet, or use "empty" quote)
  → Emit: (T1, empty)
  
Step 2: Trade T2 @ 002 ns
  Q1 @ 0500 ns > T2 @ 002 ns (quote still in future)
  → Use previous quote (empty)
  → Emit: (T2, empty)
  
Step 3: Trade T3 @ 005 ns
  Q1 @ 0500 ns > T3 @ 005 ns? No, 0500 < 005 ? NO, 500 > 5. Wait.
  
  Let me redo: nanoseconds, so 0500 ns = 500 ns.
  T3 @ 5000 ns
  Q1 @ 500 ns < 5000 ns ✓
  Q2 @ 1000 ns < 5000 ns ✓
  Q3 @ 4000 ns < 5000 ns ✓
  Q4 @ 10000 ns > 5000 ns
  
  → Use Q3 (last quote ≤ T3)
  → Emit: (T3, Q3)
```

**General algorithm:**

```
i = 0, j = 0  // pointers into trades and quotes
while i < len(trades):
  t = trades[i]
  
  // Advance quotes until we pass t's timestamp
  while j < len(quotes) and quotes[j].timestamp <= t.timestamp:
    j += 1
  
  // j now points to the first quote *after* t
  // Use quotes[j-1] (the last quote *at or before* t)
  if j > 0:
    q = quotes[j-1]
    emit(t, q)
  else:
    emit(t, None)  // No quote available yet
  
  i += 1
```

**Complexity:** O(n + m) because:
- Each trade is visited once (i loop).
- Each quote is visited once (inner j loop only advances, never backtracks).
- Total work = n + m.

This is much better than nested-loop (O(n * m) comparisons).

---

## Nanosecond Precision and No Float Timestamps

```
Float (wrong):
  timestamp = 1705324800.001234567 (seconds since epoch as float64)
  Loss of precision: float64 has 53 bits of precision.
  53 bits ≈ 10^15 range. For timestamps at 10^18 nanoseconds,
  precision is ~1000 ns. You lose ordering.

Integer nanoseconds (right):
  timestamp_ns = 1705324800001234567 (int64, nanoseconds since epoch)
  Full precision, no loss, direct comparison.
```

---

## Streaming Joins and Watermarks

Batch mode: all data is already sorted and available. Stream mode: quotes and trades arrive out of order in real time.

```
Timeline:
  T_stream: T1 arrives @ 001 ns
  T_stream: T2 arrives @ 003 ns
  T_stream: Q1 arrives @ 0500 ns (LATE, but in time order within quotes)
  T_stream: T3 arrives @ 005 ns
  T_stream: Q2 arrives @ 1000 ns
  T_stream: T4 arrives @ 010 ns

Problem: When should we emit (T1, Q1)? We don't know if a later quote will arrive.

Solution: Watermark (timestamp threshold).
  Invariant: A watermark W means no future event with timestamp < W will arrive.
  Once watermark reaches 001 ns, you're safe to emit (T1, best_quote_at_001).
```

**Watermark-based join:**

```
Watermark semantics:
  - Input: quote_watermark_ns, trade_watermark_ns
  - Process all trades with timestamp ≤ quote_watermark_ns
  - For each trade, find the last quote with timestamp ≤ trade_timestamp
  - Emit (trade, quote)
  - Update output watermark to min(quote_watermark_ns, trade_watermark_ns)

Example:
  quote_watermark = 4000 ns
  trade_watermark = 10000 ns
  
  Emit (T1 @ 001, Q1 @ 0500) — safe, quote watermark covers it
  Emit (T2 @ 002, Q1 @ 0500) — safe
  Emit (T3 @ 005, Q3 @ 4000) — safe, quotes up to 4000 ns are available
  
  Cannot emit T4 @ 010 yet, because quote watermark is only 4000 ns.
  Wait for quote watermark to advance to ≥ 10000 ns (or beyond).
```

---

## Real-World: FlowState Partitioned Replay

FlowState handles large datasets that don't fit in memory:

```
Pipeline:
  1. Read partitions (Hive-style, partitioned by date + symbol).
  2. For each symbol, read its trades and quotes partitions.
  3. Merge-scan within each symbol (as-of join).
  4. Write results to arrow IPC (zero-copy to GPU).
```

**Performance optimization:**

```
Naive: Read all trades into memory, read all quotes, run merge-scan.
  Problem: For 1000 symbols, 1 year of data, you need 100s of GB.

FlowState: Streaming merge-scan.
  1. Open both trades and quotes partitions.
  2. Use a 64 KB ring buffer per symbol (not the full dataset).
  3. Merge-scan yields results incrementally.
  4. Results are Arrow batches (GPU-ready, no extra copy).
  5. One batch completes while the next is being read.
```

**Measured on Apple M4 (Oct 2026):**
- 1M trades, 500K quotes: ~12.3 ms (FlowState), ~8.7 ms (Polars), ~75 ms (pandas).
- Polars is 1.4x faster on this workload (both use similar algorithms; Polars has more vectorization).
- FlowState's value is the surrounding pieces (watermark streaming, partitioned replay, the SPSC pipeline).

---

## Story Card: FlowState Benchmark Lesson

**Setup:** Built FlowState as a faster alternative to pandas `merge_asof`. Initial README claimed 1.8x speedup over Polars.

**Decision:** Re-ran benchmarks to verify for publication (required by pow rules). Polars was actually 1.4x *faster*.

**Result:** Rewrote the README to be honest: Polars is faster on this specific workload. FlowState's value is not raw join speed, but:
- Watermark streaming (production alignment on live feeds).
- Partitioned replay (can handle datasets > memory).
- GPU-direct output (Arrow IPC, no copy).

**What changed:**
- Realized the old benchmark was run on a suboptimal Polars config (or on an older Polars version).
- Learned to separate marketing ("fastest") from technical truth ("different trade-offs").
- Gained respect from the community by being honest about limitations.

**In an interview:**
- Q: "Why isn't FlowState faster than Polars if you built it for speed?"
- A: "Different constraints. Polars optimizes for batch, in-memory joins. FlowState optimizes for streaming watermarks and partitioned data that doesn't fit in memory. Raw join speed is not the constraint in my use case; watermark semantics and disk-based replay are. Polars is the right tool if all your data fits in memory and order doesn't matter."

---

## Q&A

**Recall 1:** Explain look-ahead bias in a temporal join. Why is it bad?

*Must-say:*
- A trade at time T is joined with a quote *after* time T (from the future).
- Model trains on future information (data leak).
- Backtests look great, production fails because future data isn't available.

*Model answer:*
- Point-in-time correctness means: trade at T is joined with the latest quote at or before T, never after.
- If you violate this, you're giving the model information it wouldn't have in production.

**Probe 1:** You have trades and quotes sorted by timestamp. Walk me through the merge-scan algorithm for a single trade.

*Expected:*
- Advance the quote pointer until quote_timestamp > trade_timestamp.
- The quote at the *previous* position is your match (last quote ≤ trade).
- Emit (trade, quote).

**Probe 2:** In a streaming join, how do you know when it's safe to emit a result?

*Expected:*
- Watermark: once watermark reaches or exceeds the result's timestamp, you're safe to emit.
- If you emit before the watermark, you risk having a later quote arrive with an earlier timestamp.

**Numeric 1:** You have 1 million trades and 5 million quotes, both sorted. What's the time complexity of the merge-scan join?

*Expected:* O(n + m) = O(1M + 5M) = O(6M). Linear.

**Numeric 2:** Your merge-scan join runs in 182 ms on a 10M trades × 5M quotes dataset. How many trades per millisecond?

*Working:* 10M trades / 182 ms ≈ 55,000 trades/ms = 55M trades/sec.

---

## Questions for the Interviewer

- How do you handle late-arriving data in your streaming pipeline? Do you have a grace period (watermark + lateness)?
- For partitioned datasets, how do you size the buffers to balance I/O with memory?
- Do you use columnar format (Arrow, Parquet) for temporal data? Why?
- How do you test temporal joins for look-ahead bias? (Point-in-time validation, golden dataset?)
