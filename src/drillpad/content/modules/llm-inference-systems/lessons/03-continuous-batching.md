# Continuous Batching: Request Overlap and Tail Latency

## The Batch Waiting Problem

In traditional inference servers, all requests in a batch must finish before the next batch starts.

```
Batch [A, B, C]:
  A generates 256 tokens (2560 ms at 100 tok/s)
  B generates 10 tokens (100 ms at 100 tok/s)
  C generates 100 tokens (1000 ms at 100 tok/s)
  
  Total batch time: max(2560, 100, 1000) = 2560 ms (wait for A)
  B finishes at 100 ms but waits 2460 ms for A
  C finishes at 1000 ms but waits 1560 ms for A
```

**Tail latency:** B and C see inflated latency just because they're batched with A.

---

## Continuous Batching Solution

Remove requests as they finish, immediately add waiting requests. Don't wait for the batch.

```
Algorithm (per step, 10 ms):
  decode_batch = [requests that are still decoding]
  prefill_batch = [new requests waiting for prefill] (up to max size)
  
  # Check for finished requests
  for req in decode_batch:
    if req.tokens_generated >= req.target_tokens:
      decode_batch.remove(req)
      push req to output_queue
  
  # Add new prefill requests (up to slot capacity)
  while prefill_queue not empty and len(decode_batch) < max_batch_size:
    req = prefill_queue.pop()
    run_prefill(req)  # 100-150 ms
    decode_batch.add(req)
  
  # Run decode step for all current requests
  if decode_batch:
    run_decode_step(decode_batch)  # 10 ms per step
```

**Timeline:**
```
t=0:    Request A arrives, prefill (100 ms)
        Request B arrives, prefill (150 ms)

t=100ms: A prefill done, add to decode batch
         B still prefilling
         Decode batch = [A]
         Run decode step A

t=110ms: Decode A, generate token 1
         Continue decode A

t=150ms: B prefill done, add to decode batch
         Decode batch = [A, B]
         Run decode step A, B

t=250ms: A generates 10 tokens (10 * 10ms), finishes
         Remove A from batch
         Decode batch = [B]

t=260ms: B decoding continues

t=400ms: B finishes
         Decode batch = []
```

**Benefit: B doesn't wait for A.** B's decode latency is 250 ms (150 ms prefill + 100 ms decode), not 250 + (A's wait time).

---

## Tail Latency: The Outlier Problem

Even with continuous batching, one slow request affects all others in the batch.

```
Scenario: Batch [A, B, C, D] all decoding
  A: generating normally, 10 ms per token
  B: generating normally, 10 ms per token
  C: generating normally, 10 ms per token
  D: token 5 cache misses (L3 miss = 40 ns added latency), takes 15 ms instead of 10 ms

At t=50ms:
  A, B, C have finished their 5th token step
  D is still computing its 5th token
  
  Decode step is: run all requests, then wait for the slowest
  Entire batch must wait for D
  B, C see 5ms of unexpected latency from D's cache miss
```

**In a batch of 128 requests, at least one has a 50% chance of hitting a cache miss or OS scheduler hiccup, adding 5–10 ms of tail latency to everyone.**

---

## Mitigation: Variable Batch Sizes

Instead of a fixed batch size (e.g., always 32), use a dynamic batch size based on request diversity.

```
Heuristic 1: Split by sequence length
  Long sequences (2K+ tokens) have larger KV cache, fragment GPU memory
  Short sequences (< 256 tokens) are fast
  
  Batch A: [short, short, short] (32 requests, each 100 tokens)
  Batch B: [long, long] (2 requests, each 4K tokens)
  
  Batch A's latency is not affected by Batch B's cache misses.

Heuristic 2: Early stopping
  If a decode step takes > threshold (15 ms for 10 ms expected):
    Finish the current batch step
    Don't add new requests until latency recovers
    
  Prevents cascading slowdown (one cache miss triggers a chain of misses).

Heuristic 3: Request-specific SLOs
  Some requests have tight SLOs (10 ms per token), others (100 ms per token)
  Don't batch tight + loose together
  
  Batch C: [tight SLO requests] → batch size 8, latency 10 ms per token
  Batch D: [loose SLO requests] → batch size 64, latency 50 ms per token
  Loose requests still get good throughput, tight get low latency.
```

---

## Real Numbers: vLLM Continuous Batching

From vLLM paper (NVIDIA A100, 7B model):

```
Batch size 64, decode step (token) latency:
  Fixed batching (all requests must finish together):
    Mean: 20 ms
    P99: 35 ms
  
  Continuous batching (remove requests as they finish):
    Mean: 12 ms
    P99: 18 ms

Throughput:
  Fixed: 52 req/s
  Continuous: 95 req/s (1.8x improvement)
```

The throughput gain comes from not wasting GPU cycles waiting for slow requests.

---

## Q&A

**Recall 1:** In continuous batching, what changes when a request finishes generating its tokens?

*Answer:* The request is removed from the decode batch immediately. Its KV cache blocks are returned to the pool. The next waiting request (in prefill) is added to the decode batch. The GPU doesn't pause or wait; it continues the decode step with the new batch composition.

**Probe 1:** You have 128 requests in a decode batch. One request's K/V is fragmented across 10 physical pages (due to block reuse). All other requests have 5-page K/V. Will that one request slow down the entire batch?

*Expected:* "Likely yes, slightly. The gather operation for that request requires more index lookups, more TLB misses. However, modern GPUs can hide ~30% latency via pipelining. The main risk is if fragmentation causes an L2 cache miss that other requests also hit (shared cache), cascading the stall."

**Numeric 1:** You have 100 GB/s GPU memory bandwidth. Decode step needs 1 GB of K/V reads per 64-request batch. How many decode steps/sec can you run?

*Working:* 100 GB/s / 1 GB per step = 100 steps/sec = 100 tokens/sec (at batch size 64). Matches reality (vLLM ~95 req/s with batch 64 on A100).

**Numeric 2:** Request A takes 2560 ms to generate (256 tokens), B takes 100 ms. In fixed batching, what's B's tail latency added?

*Working:* 2560 - 100 = 2460 ms added latency (waiting for A). Continuous batching drops this to near zero.

**Story:** Orca (earlier vLLM predecessor) used continuous batching for prefill but not decode. Each decode step waited for all requests in batch. vLLM v1.0 (2023) extended continuous batching to decode, removing requests as they finish. Resulted in 24x throughput gain over naive batching.

