# Design Judgment: Latency vs Throughput (Which Lever to Pull First)

## The Core Tension

Latency and throughput are *not* the same, and optimizing for one often hurts the other.

```
Latency = time for single request (milliseconds, microseconds)
Throughput = requests per second (QPS, RPS)

Knobs that increase throughput:
  - Batching (wait for N requests, process together)
  - Larger buffer (queue more requests)
  
Knobs that decrease latency:
  - Immediate processing (no batching)
  - Smaller buffer (early drop)

Problem: These conflict.
Solution: Firm-specific constraint tells you which to optimize.
```

## Firm-Specific Decision Matrix

```
Domain (illustrative) | P99 Latency | Throughput | Lever to Pull First
----------------------|-------------|------------|--------------------
Trading systems       | HARD (100µs) | MEDIUM    | Latency (batch=bad)
AI inference          | SOFT (200ms) | HARD    | Throughput (batch=good)
Cloud / payments      | MEDIUM (50ms) | HARD    | Throughput + SLA bound
```

## Trading: Latency is Constraint

**Trading order matching:**
```
Latency budget: 100µs end-to-end
  - Network: 10µs
  - Matching engine: 50µs
  - Network back: 10µs
  - Margin: 30µs

If you batch to improve throughput:
  Order 1 arrives, put in queue
  Wait 10µs for order 2
  Process both together → Order 1 latency = 10µs + 50µs = 60µs ✓ OK
  
  But with congestion:
  Order 1 arrives, put in queue
  Wait 10µs, still no order 2
  Other orders arrive, queue grows
  Order 1 has to wait 50µs for batch to fill → 100µs + overhead ✗ FAIL

Why batching breaks:
  - You can't predict when next order arrives
  - Queue fills unevenly (latency variance)
  - P99.9 is determined by worst-case batch wait
```

**Correct approach:**
```
NO batching. Process each order immediately.
  - Order 1: 50µs (immediate)
  - Order 2: 50µs (immediate)
  - Order 3: 50µs (immediate)
  
Result: Consistent P99.9, no variance
Cost: Lower throughput (can't batch optimization)

Throughput = 1M orders/sec / 50µs = 20,000 orders/sec (with high latency variance)
vs
Throughput = 1M orders/sec (but needs lower latency per request)
```

**Interview signal:**
```
Q: "How would you optimize your order matching engine from 1M to 2M orders/sec?"

Weak answer:
  "Implement batching: group 100 orders, process in parallel"
  (❌ You just increased P99.9 latency significantly)

Strong answer:
  "Latency is my constraint (100µs). I can't batch without variance.
   Instead:
   1. Lock-free data structure (avoid mutex)
   2. CPU affinity (prevent context switches)
   3. Vector instructions (SIMD matching)
   
   This keeps P99.9 low AND increases throughput to 1.2-1.5M."
  (✅ You understood the constraint, optimized correctly)
```

## AI Infra: Throughput is Constraint

**Anthropic inference (batch size tuning):**
```
Latency budget: 200ms (user can wait for response)
GPU available: 80GB, can fit:
  - Batch 1 = 1 user × 4K context = 8GB KV-cache, latency = 150ms
  - Batch 8 = 8 users × 4K context = 64GB KV-cache, latency = 160ms (prefill) + 30ms (8 decode steps)
  - Batch 16 = 16 users × 4K context = 128GB KV-cache = OUT OF MEMORY

Decision: Use batch 8
  - Throughput: 8 × (150ms prefill + 30ms decode) = 8 users in parallel
  - Latency: 200ms per user (acceptable)
```

**Why batching works here:**
```
User 1: ----[150ms prefill]----[30ms decode]----
User 2:     ----[150ms prefill]----[30ms decode]---- (overlapped)
User 3:         ----[150ms prefill]----[30ms decode]---- (overlapped)

Result: 8 users processed in 200-250ms total
Throughput: 40-48 users/sec (vs 5 users/sec without batching)
Latency: Still 200ms (acceptable for inference)
```

**Interview signal:**
```
Q: "How would you increase inference throughput from 100 to 500 QPS?"

Weak answer:
  "Add more GPU servers"
  (❌ Expensive, doesn't fully utilize current GPUs)

Strong answer:
  "Current batch size = 4 (P99 = 100ms)
   I can increase to batch 16 (P99 = 200ms, still under SLA)
   
   Calculation:
   - Prefill: 4K tokens @ 200 TFLOPS = 100ms
   - Decode: 8 steps @ 1000 TFLOPS = 30ms total
   - Batch 16: 16 overlapped in parallel = 5x throughput
   
   Result: 500 QPS with same hardware. Monitor P99, if < SLA, batch more."
  (✅ You optimized for throughput, kept latency under control)
```

## AWS: Both Matter (But Throughput First)

**Stripe payment processing:**
```
SLA: 99.95% uptime, P99 < 50ms

Latency budget: 50ms
Throughput target: 100k transactions/day = 1.2 TPS (not bottleneck)

Design:
  - Batch 10 payments (reduce DB round-trips)
  - Wait max 5ms for batch to fill
  - If timeout, send partial batch
  
Result:
  - Normal case: 10 payments in 10ms (batch), P99 = 20ms ✓
  - Slow case: batch fills at 5ms, process in 15ms, P99 = 20ms ✓
  - Worst case: single payment arrives, timeout at 5ms, P99 = 20ms ✓
```

**Key insight:**
```
You can batch AND meet latency SLA if:
  1. Batch wait << latency budget (5ms << 50ms)
  2. You implement timeout (don't wait for full batch)
  3. You measure P99, not average
```

## Decision Framework: Which Lever First?

**Decision tree:**

```
Step 1: What's the latency constraint?
  - < 1ms? → LATENCY FIRST (trading)
  - 10-100ms? → BOTH (AWS)
  - > 100ms? → THROUGHPUT FIRST (AI Infra)

Step 2: What's the throughput requirement?
  - < 10k/sec? → Latency doesn't constrain you
  - 100k-1M/sec? → You MUST batch
  - 10M/sec? → You MUST batch AND shard

Step 3: Can you batch with a timeout?
  - Yes? → Batch (improve throughput, bounded latency)
  - No? → Don't batch (keep latency low and predictable)
```

## Real Interview Scenario

**Q: "Design a payment system for 100M users, 10M transactions/day. Optimize for cost."**

Wrong approach (latency-first thinking):
```
"Process each transaction immediately:
  - DB query: 10ms
  - Card charge: 20ms
  - Response: 30ms P99
  
Throughput: 1M TPS needed
Hardware: 1M / (1/0.03) = 30,000 payment servers"
Cost: $3M/month
```

Right approach (throughput-first with bounded latency):
```
"Batch 1000 transactions with 10ms max wait:
  - 1000 payments in parallel
  - DB query: 10ms (batch optimized)
  - Card charge: 5ms (async to provider)
  - Response: 20ms P99 (10ms wait + 10ms process)
  
Throughput: 1000 TPS per server
Hardware: 10M / 86400 / 1000 = 115 servers per DC"
Cost: $115K/month (100x cheaper)
```

**Why right approach wins:**
1. Bounded latency (10ms wait ≤ 50ms SLA)
2. Massive throughput improvement (100x)
3. Same response time (20ms vs 30ms)
4. Cost: $115K vs $3M

## Interview Pattern Recognition

**🚩 Red flags you're wrong:**

1. Batching in trading interview → Wrong firm, wrong constraint
2. "No batching" in AI infra interview → Under-utilizing hardware by 10x
3. "Process immediately for latency" when throughput is bottleneck → Cost explosion
4. No mention of batch timeout → P99.9 will spike unpredictably

**✅ Green flags you're right:**

1. Named the firm's latency constraint
2. Explained why you batch or don't batch
3. Showed math: P99 remains under SLA while throughput improved
4. Mentioned timeout mechanism (bounded waiting)

## Quick Checklist

Before answering "how do we optimize throughput":

- [ ] What's the P99 latency constraint?
- [ ] Is batching safe? (wait time << latency budget?)
- [ ] Do I have a batch timeout? (don't wait forever)
- [ ] Did I measure P99, not average? (measure variance)
- [ ] Did I name the firm's constraint? (why this choice?)

