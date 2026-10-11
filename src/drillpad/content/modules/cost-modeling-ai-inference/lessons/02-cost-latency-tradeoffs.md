# Cost-Latency Tradeoffs - Smaller Models, Quantization, Batching

## The Core Tradeoff

Slower = cheaper. Faster = more expensive.

Your job: Pick the operating point that meets latency SLA at lowest cost.

## Lever 1: Model Size

```
Llama models (cost per 1M tokens):
  - Llama 7B: $0.10
  - Llama 13B: $0.20
  - Llama 70B: $1.00
  - Llama 405B: $3.00

Task: Summarize documents. Accuracy required: 80%.

Smaller model (7B) accuracy: 75% (misses nuance, too small)
Medium model (13B) accuracy: 92% (overkill, unnecessarily expensive)
Large model (70B) accuracy: 97% (gold standard, but expensive)

Decision:
  - If cost-constrained: Use 13B
  - If latency-constrained: Use 70B
  - If balanced: Use 13B with output validation (catch errors)
```

**Real numbers:**
```
1M requests/day, 200 output tokens each = 200M tokens/day

Using 70B: $1.00/1M * 200M = $200/day
Using 13B: $0.20/1M * 200M = $40/day (5x cheaper)

80% of the time, 13B is "good enough"
20% of the time, re-run on 70B (fallback)

Cost: $40 * 0.8 + $200 * 0.2 = $32 + $40 = $72/day
vs. pure 70B: $200/day

Savings: 64% while maintaining quality
```

## Lever 2: Quantization

```
FP16 (full precision): 70B params * 2 bytes = 140GB
INT8 (8-bit): 70B params * 1 byte = 70GB (2x smaller)
INT4 (4-bit): 70B params * 0.5 byte = 35GB (4x smaller)

Effect on latency:
  - FP16: 100 tokens/sec (baseline)
  - INT8: 120 tokens/sec (20% faster, weights fit in cache)
  - INT4: 150 tokens/sec (50% faster, but accuracy loss)

Effect on accuracy (on benchmark):
  - FP16: 95% accuracy
  - INT8: 94.5% (minimal loss)
  - INT4: 92% (noticeable loss)

Decision:
  - INT8: Usually worth it (faster + minimal accuracy loss)
  - INT4: Trade accuracy for speed (do if latency is critical)
```

## Lever 3: Batching

Problem: Each request has idle GPU time.

```
Single request:
  Input: 500 tokens → prefill takes 4s
  Output: 200 tokens → decode takes 10s
  Total: 14s per request
  GPU utilization: ~30% (waiting for I/O)

Batched (100 requests together):
  Input: 100 * 500 = 50K tokens → prefill takes 400s total
  Output: 100 * 200 = 20K tokens → decode takes 1000s total
  Total: 1400s for 100 requests = 14s per request (same latency!)
  GPU utilization: 95% (packed)

Cost benefit:
  100 requests in 1400s on 1 GPU = $0.58 cost
  vs. 100 requests, serial = $5.80 cost (10x worse)
```

**But:** Batching increases latency variance

```
Request 1 (early in batch): arrives at T=0, waits 14s (worst case)
Request 100 (late in batch): arrives at T=13.9s, returns at T=14s (best case)

SLA: P99 latency < 5s

With batching, P99 latency can be >20s (some requests wait in queue)

Solution: Adaptive batching
  - Small batch (10 requests): 2s latency, 20% GPU util
  - Medium batch (50 requests): 8s latency, 70% GPU util
  - Large batch (100 requests): 14s latency, 95% GPU util
  
  If queue depth < threshold: Use small batch (fast)
  If queue depth > threshold: Use large batch (cheap)
```

## Lever 4: Caching & KV-Cache Optimization

```
Same prompt asked 100 times (different completions):

Without caching:
  Prefill "prompt" 100 times: 100 * 4s = 400s
  Total cost: $400 for compute

With prompt caching:
  Prefill "prompt" once: 4s
  Reuse KV-cache for 99 subsequent requests: ~0.1s each
  Total cost: 4 + 9.9 = $14 (28x cheaper!)
```

## Decision Framework: When to Use Each Lever

```
Latency SLA: < 100ms
  → Use: Smaller model (7B) + INT8 + batching
  → Cost: $0.05/1M tokens
  
Latency SLA: 1-5s
  → Use: Medium model (13B) + FP16 + batching
  → Cost: $0.20/1M tokens
  
Latency SLA: > 10s
  → Use: Large model (70B) + FP16 + heavy batching
  → Cost: $1.00/1M tokens
  
Cost-constrained (< $100/day):
  → Use: Small model (7B) + INT8 + aggressive batching
  → Latency: Accept 5-10s P99
  
Quality-constrained (>95% accuracy):
  → Use: Large model (70B) + FP16 + small batches
  → Cost: Accept $1000+/day
```

## Interview Pattern: Cost-Latency Tradeoff

```
Q: "You have $1000/day budget for inference. Need P99 <1s latency.
   How do you design the system?"

Weak answer:
  "Use smaller models"
  (❌ No math, no strategy)

Strong answer:
  "Need to work backward from constraints:
  
  1. Latency requirement: P99 < 1s
     This rules out heavy batching (batches can wait 5-10s)
     → Must use small batches (5-10 requests)
  
  2. Budget: $1000/day
     Assume avg 200 output tokens per request
     $1000/day ÷ 200 tokens = 5M requests/day capacity
     = 57 requests/sec
  
  3. Model selection:
     Latency <1s + accuracy >90%?
     Llama 13B in INT8: 150 tokens/sec, ~92% accuracy
     Matches both constraints
  
  4. Throughput calculation:
     57 requests/sec * 200 tokens output = 11.4K tokens/sec needed
     Llama 13B: 150 tokens/sec per GPU
     GPUs needed: 11.4K ÷ 150 = 76 GPUs
     
  5. Cost check:
     76 GPUs * $1.50/hour * 24h = $2736/day
     Exceeds budget!
     
  6. Optimization:
     Need to cut cost in half. Options:
     
     a) Smaller model (7B instead of 13B)
        Cost: 76 * 0.7 = $1363/day (still over)
     
     b) Lower accuracy requirement (use 7B, accept 80%)
        Cost: 76 * 0.1 = $1064/day (still over)
     
     c) Relax latency (P99 < 2s instead of 1s)
        Allow batching of 20 requests
        Reduces GPU utilization need by 2x
        Cost: 76 * 0.5 = $912/day ✓ Under budget
     
  7. Final design:
     - Model: Llama 7B INT8
     - Batch size: 20 requests
     - Latency: P50 = 200ms, P99 = 1.8s
     - Cost: $900/day
     - Accuracy: 78% (falls to 85% with retrieval augmentation)
     
  8. Monitoring:
     - Track actual latency percentiles (not average)
     - Monitor GPU utilization (should be 80%+)
     - Alert if cost per token exceeds $0.18
     - A/B test INT8 vs INT4 (INT4 could save 30% cost)"

Why this signals good judgment:
  - You worked backward from constraints
  - You did the math (GPUs, cost, throughput)
  - You found the bottleneck (over budget)
  - You optimized the right lever (latency, not model size)
  - You validated the final design
```

## What This Signals

- You understand latency/cost isn't binary
- You know which levers to pull (model size, quantization, batching)
- You think about utilization and queue management
- You can work backward from constraints
