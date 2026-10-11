# Prefill vs Decode: Scheduling and Latency


## The Scheduling Problem

Prefill and decode have opposite resource profiles:

```
Prefill (processing user prompt):
  Input: 2048 tokens (user's message)
  Output: 0 (generating first token takes time)
  GPU utilization: 100% (matmul is huge, fully parallelizable)
  Latency: 500–1000 ms (wall-clock time to generate first token)
  Throughput: 1 token/GPU/500ms = 2 tokens/sec (sustained)

Decode (generating output):
  Input: 1 token
  Output: 1 token
  GPU utilization: 10% (tiny matmul, memory-bound)
  Latency: 10 ms per token (wall-clock time per output token)
  Throughput: 1 token/(10ms) = 100 tokens/sec (if batched)

Batch 100 decode requests:
  Prefill 100 different prompts (100 * 2048 = 200K tokens):
    Compute time: 200K / (2K tokens/sec) = 100 ms
    GPU utilization: 100%
  
  Then decode 100 requests for 256 output tokens each:
    Compute time: 100 * 256 * 10ms = 256 sec = 4+ minutes
    GPU utilization: 10%
```

**The problem:** Prefill and decode can't share a GPU efficiently. If you do prefill first, GPUs are underutilized during decode. If you interleave, you fragment KV cache and reduce throughput.

---

## Naive Scheduling: Strict Batching

```
Time 0:   Prefill requests 0–31 (batch of 32, 2K tokens each)
Time 100ms: Finish prefill, start decode for requests 0–31
Time 100ms: New prefill requests 32–63 arrive, queue them
Time 100ms + 256*10ms = 2.7s: Finish decode, start prefill for 32–63
```

**Problem:** Requests 32–63 wait 2.6 seconds in a prefill queue while GPUs decode. New users see queued prefill latency.

**Metrics (bad):**
- Time to first token (TTFT) for request 32: 2.6 seconds (queued)
- Time between tokens (TBT) during decode: 10 ms

---

## Better: Interleaved Prefill/Decode

Mix prefill and decode in the same batch (but not the same matmul):

```
Time 0:   Batch A: prefill 4 requests (8K tokens)
          Batch B: decode 32 requests (32 tokens)
          Total: 8K + 32 = 8032 tokens
          GPU utilization: high (8K tokens is heavy prefill work)

Time 50ms: Finish first Batch A, Batch B
          Start Batch A': prefill 4 requests (next batch)
          Start Batch B': decode 32 requests (next step)
          
Scheduling rule: prefill += new_requests; decode = existing_requests; batch both
```

**Benefit:** New requests see short prefill latency (50 ms) while existing requests keep decoding.

**Trade-off:** Each request's decode latency increases slightly (KV cache is more fragmented, slightly less optimal memory access).

---

## Continuous Batching (SOTA)

Requests finish at different times; don't wait for the batch to fully complete.

```
Timeline (seconds):
t=0:    Req A prefill (2K tokens, takes 100 ms)
        Req B prefill (3K tokens, takes 150 ms)

t=100ms: Req A finishes prefill, starts decode
         Req B still prefilling
         Req C arrives, starts prefill

t=150ms: Req B finishes prefill, starts decode
         Req A has generated 5 tokens (50ms * 100 tok/s)
         Req C still prefilling

t=200ms: Req A finishes decoding (generated 10 tokens)
         Batches: [Req B decode, Req C decode, Req D prefill + decode]
         Req A's resources freed immediately
```

**Key insight:** Don't wait for the batch. When a request finishes, immediately remove it and add waiting requests. This is "continuous batching."

```
Algorithm:
  while requests_queue:
    prefill_batch = pop prefill_requests (up to max_prefill_batch_size)
    decode_batch = current_decoding_requests (remove any that finished)
    
    # Run both simultaneously on different compute streams
    run_prefill(prefill_batch)   # stream 0
    run_decode(decode_batch)     # stream 1
    
    # Overlap: while prefill is computing, decode can read its own cached KV
    # Both use different GPU resources (matmul unit vs memory controller)
```

**Measured impact (vLLM):**
- Naive batching: 52 req/s (requests queue for prefill)
- Interleaved: 65 req/s (less queueing)
- Continuous batching: 95 req/s (requests move to decode as soon as prefill done)

---

## Scheduling Decision: When to Prefill?

You have a prefill queue and a decode batch. Prefill is expensive but necessary. When do you switch?

```
Option 1: Prefill-First
  if prefill_queue > 0:
    run_prefill(prefill_queue.pop(batch_size))
    skip decode this step
  else:
    run_decode(current_batch)
    
  Problem: decode requests stall while prefill runs. High TTFT for new requests, but smooth TBT.

Option 2: Decode-First
  run_decode(current_batch)
  if GPU has spare capacity:
    run_prefill(prefill_queue.pop(small_batch))
    
  Problem: prefill is small, slow. Requests queue. Lower TTFT, higher latency to first token.

Option 3: SLO-Driven (best)
  prefill_slo = 500 ms (time to first token target)
  decode_slo = 50 ms per token (per-token latency target)
  
  if oldest_prefill_request.wait_time > prefill_slo / 2:
    # Prefill is falling behind, prioritize it
    allocate 50% GPU to prefill, 50% to decode
  else:
    # Prefill is fine, maximize decode throughput
    allocate 30% GPU to prefill, 70% to decode
    
  Adaptive scheduling based on queue depth and SLO targets.
```

---

## Interview-Style Depth: Agent Inference Scheduling

**Q: You have sandboxed agents running in Firecracker VMs. Each VM can only send one request at a time (no batching within VM). How do you schedule prefill/decode?**

*Expected answer:*
- A central inference scheduler (outside the VMs) owns batching.
- Multiple VM agents submit requests to the scheduler.
- Scheduler batches prefill for agents A, B, C together.
- Returns prefilled token to each agent, they each run their decode step.
- Agents don't see latency; they see "request completes in N ms" but that includes prefill + decode.
- Key: scheduler owns the batch, agents own the request lifecycle.

**Q: Two requests arrive simultaneously. Request A: 100 tokens, needs 50 output tokens. Request B: 5000 tokens, needs 500 output tokens. You have 40 GB GPU. How do you schedule them?**

*Expected:*
- Rough math: A = 100 * 0.5 MB = 50 MB KV cache growth. B = 5000 * 0.5 MB = 2.5 GB.
- Both can decode concurrently (2.5 GB + 50 MB < 40 GB), but not optimal.
- Better: prefill A first (small, 100 ms), then decode both. B still queues its prefill. Or interleave: prefill A, decode B, prefill B at next step.
- Answer: "Prefill A (fast), then run A + B decode together. B's prefill was waiting anyway. At next batch, A is done, add new request C's prefill."

**Q: You measure TTFT = 2 seconds and TBT = 50 ms for a typical request. Your SLO is TTFT < 500 ms. What's the bottleneck?**

*Expected:*
- TTFT = time in prefill queue + prefill compute time + first decode step.
- 2 seconds is probably queue waiting (prefill batch is large, or you're running decode-heavy).
- Fix: allocate more GPU to prefill, or increase prefill batch size (trades TBT for TTFT).
- Measurement: histogram of queue wait time. If > 1 second, increase prefill parallelism.

---

## Q&A

**Recall 1:** Why is prefill compute-bound and decode memory-bound? What changes between them?

*Answer:* Prefill processes N input tokens once, generating 1 output. The matmul is N * d^2 (N is large, ~2K). Decode processes 1 input token repeatedly for 256 steps, each reading all N prior tokens' K/V. The ratio is K/V bytes read (64 GB) vs. compute (matmul is tiny). Prefill compute >> memory, decode memory >> compute.

**Numeric 1:** Prefill 1000 tokens takes 100 ms (compute time). Decode 256 tokens at 100 tokens/sec takes 2560 ms. Ratio?

*Working:* 2560 ms / 100 ms = 25.6x longer for decode (same request). Decode is the tail.

**Numeric 2:** You have 100 GB/s memory bandwidth (typical GPU). Decode reads 4K sequence * 4K hidden * 2 matrices * 2 bytes / 100 tokens = 6.4 KB per token. How many tokens/sec can you sustain?

*Working:* 100 GB/s / 6.4 KB = 15.6M tokens/sec. Wait, that's too high. Let me recalc: 100 GB/s means 100 billion bytes per second. 6.4 KB = 6400 bytes. 100 billion / 6400 ≈ 15.6M tokens/sec. Hmm, that's not matching real numbers. Let me reconsider.

Actually, the issue is that decode reads K and V for *all previous tokens in the sequence*, not just the current token. If sequence is 4K tokens and each KV read is 8 bytes (for one dimension), then reading all K and V is 4K * 8 bytes * 2 (K, V) = 64 KB per decode step per head. With 32 heads, 2 MB per decode step. At 100 GB/s, that's 100 GB / 2 MB = 50,000 tokens/sec. More realistic, but still optimistic because of other ops.

**Story:** vLLM's scheduling breakthrough (2023) was recognizing that prefill and decode should run on different batches but the *same GPU*, in an interleaved fashion. Before, systems ran prefill → decode sequentially. Continuous batching dropped latency by 40% and throughput increased 24x on some benchmarks.

