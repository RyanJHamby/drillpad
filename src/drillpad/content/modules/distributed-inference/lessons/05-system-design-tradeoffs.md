# Scaling Decisions: Topology, Latency, Throughput, Cost Per Token

## TP vs PP vs DP: When to Use Each

```
Tensor Parallelism (TP):
  Split weights horizontally, all GPUs do matmul together
  Pros: low latency (AllGather in parallel with compute), simple
  Cons: AllGather bandwidth bottleneck, doesn't scale past ~8 GPUs
  Use: small clusters (< 16 GPUs), low-latency inference

Pipeline Parallelism (PP):
  Split layers vertically, GPUs process sequentially
  Pros: no AllGather, fits large models, scales to 100+ GPUs
  Cons: bubble overhead, activation memory, complexity
  Use: large-scale training, long-sequence inference

Data Parallelism (DP):
  Replicate model, process different batches, average gradients
  Pros: scales linearly, simple, no model sharding
  Cons: gradient AllReduce per batch, not for inference (redundant compute)
  Use: training at scale, multi-machine setups
```

---

## Cost Per Token Analysis

```
Setup: 70B model, fp16, 2K context, 256 output tokens

Cost = (GPU-hours used) * (price/GPU-hour) / (total tokens generated)

Config A: 8 H100s, TP=4
  Prefill: 2K tokens at 50 TFLOPS = (2K * 70B FLOPs) / 50 TFLOPS ≈ 2.8 s
  Decode: 256 tokens at 5 TFLOPS = (256 * 70B FLOPs) / 5 TFLOPS ≈ 3.6 s
  Total: 6.4 s per request
  GPU utilization: 70% (some time waiting for AllGather)
  Effective: 6.4 s / 0.7 = 9.1 s equivalent compute
  Cost: 9.1 s * (8 GPUs * $3/hr) / 3600 s/hr = $0.0604
  Per token: $0.0604 / (2K + 256) ≈ $0.000027 per token

Config B: 16 A100s, TP=8
  Same model, but A100 is 2.5x slower, half the cost ($1.5/hr)
  Compute time: 6.4 s * 2.5 = 16 s
  GPU utilization: 60% (more AllGather overhead with TP=8)
  Effective: 16 s / 0.6 ≈ 26.7 s
  Cost: 26.7 s * (16 GPUs * $1.5/hr) / 3600 s/hr = $0.178
  Per token: $0.178 / 2256 ≈ $0.000079 per token

Config A is 3x cheaper per token (despite H100 cost).
```

**Key:** Maximize utilization, not just GPU count.

---

## Latency SLOs

```
Latency budget for user-facing inference:
  Total time to response: < 1000 ms (user tolerance)
  
  Breakdown:
    Network latency (user→server): 50 ms
    Queuing: 100–300 ms (depends on load)
    Model inference (prefill + 1st decode): 300–500 ms
    Network latency (response→user): 50 ms
    
  Sum: 500–950 ms (tight budget)

With 8-GPU TP:
  Prefill 2K: 2.8 s (over budget already!)
  
  Solution: reduce prefill batch size (process one request at a time)
  or switch to streaming prefill (return first token early, continue prefilling in background)
```

---

## Scaling Laws

For a fixed model size, scaling GPUs from N to 2N:

```
Ideal (no communication overhead):
  Latency: halved (2x compute, same wall-clock)
  Throughput: doubled (2x parallel)
  Cost per token: flat (2x GPU cost, 2x throughput)

Reality:
  AllGather overhead increases with N (more links, more contention)
  Communication: ~O(log N) hops in tree, ~O(N) steps in ring
  Utilization: might drop from 70% to 60%
  
  Actual speedup: 1.8x (not 2x) at N=8→16
  Cost per token: +20% (worse, due to lower utilization)
```

**Implication:** Scaling beyond 16–32 GPUs requires careful design (better networks, pipeline PP, or accepting cost increase).

---

## Real Interview: Production Decisions

**Q: You're serving a 70B model. P99 latency is 3 seconds, SLO is 1 second. Do you add more GPUs?**

*Expected:* "Not necessarily. Adding GPUs helps if you're compute-bound (queuing delays). Check: what's the GPU utilization? If 80%+ utilized, queueing is small, latency is from computation. Adding GPUs helps. If 30% utilized, GPUs are idle; your bottleneck is somewhere else (network, disk I/O)."

**Q: Cost per token is too high. How do you reduce it?**

*Expected:* 
1. Increase batch size (amortize prefill across more tokens)
2. Reduce model size (quantization, pruning)
3. Switch to reserved instances (lower $/hr)
4. Use cheaper GPUs (A100 vs H100)
5. Accept slightly higher latency (use smaller GPU cluster, more queuing)

**Numeric 1:** You have 1M requests/day, each 2256 tokens. At $0.000027/token, what's your daily inference cost?

*Working:* 1M * 2256 * $0.000027 ≈ $61/day (reasonable).

**Numeric 2:** You reduce to 4 H100s (half capacity). Throughput drops 40% (some requests queue). Cost per token goes up or down?

*Working:* Half GPUs, 40% throughput reduction = 60% of original throughput. Cost per GPU-hour is same. Cost per token = (GPU cost) / (tokens processed). If throughput is 60%, cost per token goes up 67% (worse).

