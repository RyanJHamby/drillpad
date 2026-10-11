# Production Inference: SLOs, Autoscaling, Cost vs Latency


## SLOs and Latency Targets

Define what "good" means for your inference service:

```
Service-level objectives (SLOs) for an answer-engine-style system:

1. Time to first token (TTFT): P50 < 300 ms, P99 < 1 s
   (user sees first response word within 300 ms)

2. Time between tokens (TBT): P50 < 50 ms, P99 < 100 ms
   (smooth generation, words appear regularly, not chunky)

3. Availability: 99.9% (< 43 minutes downtime per month)

4. Cost per request: < $0.01 (inference cost for a 4K context, 256 output tokens)
   (on H100 GPU at $3/hour, 1000 req/hour = $0.003/req, acceptable)

Trade-offs:
  - Higher TTFT SLO = less aggressive prefill batching = lower throughput = higher cost per request
  - Lower cost SLO = batch more aggressively = higher latency = miss TTFT targets
  - Higher availability = redundancy + backup GPUs = higher cost
```

**Real metrics from vLLM benchmarks:**
```
Config A: batch_size=128, prefill_batch_size=32
  TTFT: P50=250ms, P99=800ms
  TBT: P50=40ms, P99=80ms
  Throughput: 95 req/s
  Cost per request: $0.001 (efficient)

Config B: batch_size=32, prefill_batch_size=8
  TTFT: P50=150ms, P99=350ms
  TBT: P50=25ms, P99=50ms
  Throughput: 35 req/s
  Cost per request: $0.003 (less efficient)
```

Config A meets TTFT P99 < 1s, Config B is tighter but more expensive. Choice depends on your SLO and budget.

---

## Autoscaling Strategy

You can't run at peak capacity 24/7 (cost). Scale up when demand spikes, down when quiet.

```
Metric: request queue depth (requests waiting for inference)

Scaling policy:
  if queue_depth > 100 for 30 seconds:
    add 1 GPU
  if queue_depth < 10 for 5 minutes:
    remove 1 GPU (scale down slower than up, avoid flapping)
  max_gpus = 64 (hard limit, cost control)

Real scenario:
  t=0:    queue_depth = 5, 1 GPU allocated
  t=1hr:  morning spike, queue_depth = 500, add GPUs
          t=30s: add GPU 2
          t=60s: add GPU 3 (queue now 200, getting caught up)
          t=90s: add GPU 4 (queue 50, almost caught up)
          Settled at 4 GPUs

  t=8pm:  evening quiets down, queue < 5 for 5 min
          Remove GPU 4, down to 3
          5 min later: queue < 5 again
          Remove GPU 3, down to 2
          ...eventually back to 1 GPU

Cost impact:
  Peak: 4 GPUs * 1 hour = 4 GPU-hours
  Off-peak: 1 GPU * 8 hours = 8 GPU-hours
  Total: 12 GPU-hours per day
  If no autoscaling: 4 GPUs * 24 hours = 96 GPU-hours per day (8x cost)
```

---

## Queue Management and Rejection

When the system is overloaded, you must reject requests (don't queue forever).

```
Policy options:

1. FIFO (first-in, first-out)
   Pro: fair, simple
   Con: high-priority requests get same latency as low-priority

2. Priority queue
   Pro: urgent requests (user is waiting) get lower latency
   Con: low-priority requests (batch jobs) might starve

3. Deadline-based
   if request.deadline < now + queue_wait_time:
     reject with "system overloaded" (user should retry later)
   else:
     queue
   
   Pro: avoids processing requests that user doesn't want anymore (timed out)
   Con: must estimate queue wait time accurately

Example implementation (illustrative):
  priority = "standard"  # or "premium" for paid users
  
  if priority == "premium":
    queue = premium_queue (batch_size 16, TTFT P99 < 300 ms)
  else:
    queue = standard_queue (batch_size 64, TTFT P99 < 1 s)
  
  if len(queue) > 500:
    return HTTP 429 "Too many requests" (user sees "service overloaded")
  else:
    add to queue
```

---

## Cost vs Latency Tradeoff

Real numbers (2026):
- H100 GPU: $3 per hour (on-demand), $2/hr (reserved, 1-year commitment)
- 4x H100 instance: $12/hr on-demand

**Inference cost breakdown:**
```
Request: 2K context, 256 output tokens

Compute cost:
  Prefill (2K tokens): 4M FLOPs at 1.5 TFLOPS (memory-bound) = 2.7 ms
  Decode (256 tokens): 100 tokens/s = 2560 ms
  Total compute time: 2560 ms = 2560 ms / 3600 s/hr = 0.0007 GPU-hours

At $3/GPU-hour:
  Compute cost = 0.0007 * $3 = $0.002 per request

Overhead:
  Memory pooling, KV cache: amortized ~$0.0005 per request
  Total: $0.0025 per request

If GPU is 50% utilized (requests queuing, not fully batched):
  Cost = $0.005 per request

If GPU is 80% utilized (good batching):
  Cost = $0.003 per request
```

**How to reduce cost:**
1. Use reserved instances (1-year commitment) → $2/hr instead of $3/hr → 33% savings
2. Use lower-cost GPUs (A100 instead of H100) → $1.5/hr → 50% savings
3. Increase utilization (batch more aggressively) → trade latency for throughput

---

## Failure Modes and Resilience

What breaks in production?

```
1. GPU out of memory (OOM)
   Cause: Large batch + long sequences exhaust GPU memory
   Fix: Overflow to CPU (slow but prevents crash), or reject request
   
2. GPU thermal throttling
   Cause: Sustained full-load inference, GPU heats up
   Throttle reduces clock speed → 10–20% latency increase
   Fix: Improve cooling, add heat sink, or reduce batch size

3. Network latency spike (VM ↔ scheduler communication)
   Cause: Scheduler on different host, network packet loss
   Fix: Local caching of frequent model weights, request batching in VM before sending

4. Cascading queue growth
   Cause: GPU saturated, queue backs up, new requests queue longer
   Effect: TTFT increases (older requests in queue), users timeout and retry
   Retries make queue worse
   Fix: Early rejection (drop new requests when queue > threshold), not queuing forever

5. Memory leak in agent code (Firecracker VM)
   Cause: Agent allocates memory and doesn't free it
   Fix: Resource limits enforce 512 MB cap, agent gets OOM killed
   Recovery: Restart VM (handled by orchestration)
```

---

## Real Interview: Production Decisions

**Q: Your P99 TTFT is 2 seconds, SLO is < 1 second. Your GPU is only 40% utilized. What's the bottleneck?**

*Expected:*
- If GPU is under-utilized, bottleneck is not compute, it's batching or queue management.
- Hypothesis: prefill queue is large (batches are formed slowly), new requests queue-wait.
- Data to check: histogram of queue wait time. If > 1 second, you're queuing too long.
- Fix: increase batch size or reduce batching frequency (form batches faster).

**Q: You decide to switch from on-demand H100s ($3/hr) to reserved A100s ($1/hr). How does this affect your inference service?**

*Expected:*
- A100 is slower per GPU (~2.5x less throughput than H100).
- Cost per request: unchanged (lower GPU cost, but need more GPUs to maintain throughput).
- Latency: slightly higher (fewer GPUs available, more queuing).
- Decision: depends on latency targets. If SLO is tight, H100 may be mandatory. If loose, A100 is cost-effective.

**Q: A customer uses the service at 3 AM (off-peak). You auto-scale down to 1 GPU. Their request arrives. TTFT = 3 seconds (SLO = 1 second). Can you meet SLO?**

*Expected:*
- No, not with 1 GPU at off-peak volume.
- Options:
  1. Scale up faster (reduce scale-down wait time)
  2. Accept SLO miss at off-peak (cheaper service tier for off-peak)
  3. Overprovision (keep 2 GPUs always, trade cost for consistency)
  4. Request deduplication (if two users ask the same thing, share result)

**Numeric 1:** You have 4 GPUs, each doing 100 requests/s. One GPU breaks. Queue builds up. How long until queue backs up to 1 minute wait?

*Working:*
- Throughput drops from 400 req/s to 300 req/s.
- If 400 req/s arrive, deficit = 100 req/s backlog.
- Queue grows 100 req/s.
- 1 minute wait = 60 sec * 100 req/s = 6000 requests in queue.
- Time to reach 6000 in queue: 6000 req / 100 req/s growth = 60 seconds = 1 minute.

**Numeric 2:** Cost per request is $0.003. You serve 1M requests/day. What's your daily GPU inference cost (not including ops, cooling, power)?

*Working:* 1M * $0.003 = $3000/day. At $3/hr per GPU, this is ~1000 GPU-hours/day = ~42 GPUs running 24/7 (on average).

---

## Illustrative Story: Scaling a Production Service

Imagine a service that launched with 8 H100 GPUs (fixed; all numbers here are hypothetical). User growth was exponential. Later it had auto-scaling up to 64 H100s at peak (8 PM–midnight). Cost went from ~$6K/month (fixed) to ~$20K/month (with peaks), but revenue/request doubled (premium tiers). Trade was worth it: latency stayed under SLO, retention improved.

Key decision: premium tier users got dedicated replicas (1 GPU per 10 premium users), standard tier shared batching. Segmentation allowed different SLOs for different customers without over-provisioning.

