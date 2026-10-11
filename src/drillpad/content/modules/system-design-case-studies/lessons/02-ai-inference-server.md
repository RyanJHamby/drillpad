# AI Infrastructure: Inference Server (Batching, SLO, Cost Optimization)

## Typical Contexts: AI infrastructure and inference platforms

**Problem:** Serve LLM inference at 1000 concurrent requests with:
- P50 latency < 200 ms
- Cost per token < $0.0001
- 90%+ GPU utilization

**Why hard:** GPU is expensive ($20/hr), so utilization matters. But latency SLA also matters (users wait < 200ms).

---

## Trade-off Matrix

```
Strategy 1: Small batch (8), quick latency
  Batch time: 5 ms (wait for 8 requests)
  Compute time: 100 ms (inference)
  Total P50: 105 ms ✓
  GPU util: 20% (most of GPU unused) ✗
  Cost: $0.0005/token ✗
  
Strategy 2: Large batch (128), high throughput
  Batch time: 500 ms (wait for 128 requests)
  Compute time: 100 ms (inference, amortized)
  Total P50: 600 ms ✗ (miss SLA)
  GPU util: 95% ✓
  Cost: $0.00001/token ✓
  
Strategy 3: Continuous batching (sweet spot)
  Batch time: 50 ms (token budget, not request count)
  Compute time: 100 ms
  Total P50: 150 ms ✓
  GPU util: 85% ✓
  Cost: $0.00005/token ✓
```

---

## Architecture (vLLM Inspired)

```
Incoming requests:
  Request 1: prompt "Hello" (100 tokens)
  Request 2: prompt "What is..." (50 tokens)
  Request 3: prompt "How do..." (75 tokens)

Batching logic:
  Collect requests for 50 ms (token budget)
  Batch: [req1, req2, req3]
  Total tokens: 100 + 50 + 75 = 225 tokens
  
Prefill (all tokens):
  Compute attention for 225 tokens
  KV-cache: store (K, V) for each token
  Time: 225 * 0.4ms/token = 90 ms (compute-bound)
  GPU util: 100%
  
Decode (generate next token):
  For each request:
    req1: query 1 new token against 100 KV tokens → output 1 token
    req2: query 1 new token against 50 KV tokens → output 1 token
    req3: query 1 new token against 75 KV tokens → output 1 token
  Compute: 1 * 3 = 3 tokens
  Time: 10 ms (memory-bound, low compute)
  GPU util: 10%
  
  Trick: interleave prefill of request 4 with decode of requests 1-3
  Continuous batching: always have mix of prefill (compute-bound) + decode (memory-bound)
  Net GPU util: (100% * 90ms + 10% * 10ms) = 91 ms per 100ms = 91% utilization
```

---

## Design Decisions

**Why continuous batching instead of static batch size?**
- Static: must wait for batch to fill (high latency) or waste GPU (low util)
- Continuous: prefill new requests while decoding old ones (both ✓)

**Why token budget instead of request count?**
- Request count: fixed (32 requests)
- Token budget: flexible (32 requests * avg 100 tokens = 3200 tokens max)
- Allows adaptive batching (many short requests = larger batch, many long requests = smaller batch)

**Why separate prefill/decode schedules?**
- Prefill: compute-bound, benefits from large batch
- Decode: memory-bound, small batch is fine (GFlops don't matter, bandwidth does)
- Schedule: prefill-first (fill GPU fully), then interleave decode

---

## Cost Optimization

```
Option A: 1 H100 ($20/hr), 90% util, 100 tokens/sec
  Cost: $20 / 360K tokens/hour = $0.000056/token

Option B: 4 A100s ($3/hr each), 70% util, 80 tokens/sec per GPU = 320 total
  Cost: $12 / 1.15M tokens/hour = $0.0000104/token
  
Option B is 5x cheaper!
  Trade-off: latency worse (4 A100s slower than 1 H100)
  
Decision: Use A100s if latency SLA permits, H100s if SLA is strict.
```

---

## Q&A

**Recall 1:** Why is decode memory-bound but prefill compute-bound?

*Must-say:*
- Prefill: read 100 tokens, compute 100 attention scores (100 FLOPs, 400 bytes) = high AI
- Decode: read 4K KV tokens, compute 1 attention score (4K FLOPs, 8KB) = low AI
- Arithmetic intensity determines bottleneck

**Probe 1:** Batch size 32. Token budget 3200. Average 100 tokens/request. How many requests per batch?

*Expected:*
- 32 requests * 100 tokens = 3200 tokens
- If requests are smaller (50 tokens): can fit 64 requests
- If requests are larger (200 tokens): can fit 16 requests

**Numeric 1:** H100 $20/hr. Prefill 100 tokens in 50ms. Decode 100 tokens in 50ms. Cost per token?

*Working:*
- Total: 100ms per 200 tokens
- Throughput: 200 / 0.1s = 2000 tokens/sec
- Cost: $20 / 3600s / 2000 tokens/s = $0.0000028/token

---

## Questions for the Interviewer

- What's your token budget per batch? (how do you tune it?)
- How do you prioritize requests? (first-come-first-served, priority queues?)
- What's your GPU utilization target? (80%, 90%, 95%?)
- Have you had to choose between latency SLA and cost? (which won?)
