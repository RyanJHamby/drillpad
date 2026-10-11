# Trading: Order Book Matching Engine (Sub-Microsecond Latency)

## Typical Contexts: trading and low-latency systems

**Problem:** Match buy and sell orders in sub-microsecond latency.
- Throughput: 1M orders/sec
- P50: < 1 µs
- P99.9: < 5 µs
- No timeouts allowed

**Why hard:** Latency dominates everything else (cost, features, scaling).

---

## Architecture

```
Network packet arrives
  ↓ (1 us so far)
Validate format (format validation: 50 ns)
  ↓
Symbol lookup (hash map, L1 hit: 5 ns)
  ↓
Find price level (red-black tree, L3 hit: 50 ns)
  ↓
Match against counterparties (iteration: 100-300 ns depending on fill count)
  ↓
Serialize response (memcpy: 50 ns)
  ↓
Send back on network
  ↓ (total: 0.2-1 µs)
```

**Critical constraints:**
- No malloc (pre-allocate pools)
- No locks (lock-free SPSC queue)
- Memory layout matters (cache locality)
- CPU cache misses kill you (50 ns each)

---

## Real Design (OrderBookEngine from Your Resume)

Your claim: "P50 0.21 µs, P99.9 3.1–3.2 µs, up to 1.8M orders/sec"

```
Data structures:
├─ Buy side: std::map<price, std::deque<Order>>
├─ Sell side: std::map<price, std::deque<Order>>
├─ Order pool: pre-allocated 1M orders, free-list allocation
├─ SPSC queue: lock-free producer (network) → consumer (matcher)
└─ Cache-line padding: prevent false sharing across cores

Matching algorithm:
  1. Receive order from SPSC queue (lock-free, ~50 ns)
  2. Allocate order from pool (free-list pop, ~10 ns)
  3. Find price level in map (log2(10K) = 13 lookups, ~50 ns each = 650 ns)
  4. Match against deque (FIFO scan, ~100 ns per fill)
  5. Serialize fills (memcpy, ~50 ns)
  
  Total: 50 + 10 + 650 + 100 + 50 = 860 ns ≈ 0.86 µs
  
  Optimizations:
  - Pre-warming tree (fill with dummy orders to ensure nodes in cache)
  - Batch fills (serialize 4 fills at once instead of 1)
  - Inline hot paths (force compiler to inline matching loop)
  - CPU affinity (pin matcher thread to core, avoid context switches)
```

---

## Design Decisions

**Why std::map instead of hash map?**
- Ordered iteration (match best price first)
- Can't hash prices efficiently (continuous range)

**Why SPSC queue instead of MPSC?**
- Single producer (network thread)
- Lock-free (no atomics overhead)
- FIFO ordering (important for fairness)

**Why pre-allocated pools instead of malloc?**
- malloc latency spikes after ~100K allocations (page refills)
- Pool: constant 10 ns allocation (just pop free-list)

**Why single-threaded matcher instead of parallel?**
- Parallel → contention on order book lock
- Single-threaded → no lock overhead, runs at full CPU speed
- If throughput needed: shard by symbol (multiple books)

---

## Interview Angles

**Q: How do you achieve P50 0.21 µs?**
A: Every nanosecond counts. Pre-allocation, lock-free queue, cache-friendly data structures, CPU affinity, inline hot paths.

**Q: What's your bottleneck at 1.8M orders/sec?**
A: CPU core saturated (one matcher thread). To scale: shard by symbol (multiple order books, one matcher each).

**Q: How do you measure P99.9?**
A: Timestamp both sides (network arrival + matcher return), histogram latencies, find 99.9th percentile.

**Q: What would break P99.9?**
A: Page fault, context switch, cache miss, tree rebalancing, GC pause (use no-GC languages).

---

## Q&A

**Recall 1:** Why does latency matter more than throughput in trading?

*Must-say:*
- Microseconds = money (arbitrage windows close fast)
- Throughput matters, but latency determines profitability
- 1 µs vs 10 µs = 9x slower at matching = lose opportunities

**Probe 1:** Order book has 10K price levels. Tree traversal is 13 lookups * 50ns = 650ns. How do you reduce this?

*Expected:*
- Pre-warming: fill tree with dummy orders, keep nodes in cache
- Or: use flat structure (array by price bucket) instead of tree
- Or: batch orders (collect N orders, match all at once)

**Numeric 1:** You have 1.8M orders/sec. If you add logging (1 µs overhead per order), throughput drops to?

*Working:*
- With logging: 0.2 µs + 1 µs = 1.2 µs per order
- Throughput: 1 / 1.2µs = 833K orders/sec (55% drop!)
- Lesson: even small overhead matters at scale

---

## Questions for the Interviewer

- What's your current P99.9 latency? (Is it a bottleneck?)
- How do you measure latency? (CPU timer? Network timestamp?)
- What's your largest bottleneck right now? (matching, allocation, serialization?)
- How do you test latency? (hardware-in-loop, simulation?)
