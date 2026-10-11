# Token Economics - Cost Per Inference

## The Cost Equation

```
Cost per token = (GPU cost + memory + bandwidth) / tokens processed
```

Not just compute. Everything matters.

## Component 1: GPU Cost

```
A100 GPU: $1.50/hour on cloud (AWS, GCP)
Llama 2 70B: 70B parameters

Tokens per second per A100:
  - Prefill (first token): 100-200 tokens/sec
  - Decode (subsequent tokens): 10-30 tokens/sec

Typical mix: 1 prefill request (100 tokens input) + 50 decode tokens (output)
  Prefill: 100 tokens / 150 tokens/sec = 0.67s
  Decode: 50 tokens / 20 tokens/sec = 2.5s
  Total: 3.17s per request

Cost per request = ($1.50 / 3600s) * 3.17s = $0.0013

Cost per output token = $0.0013 / 50 = $0.000026/token (2.6 cents per 1M tokens)
```

## Component 2: Memory & Bandwidth

```
Llama 70B weights: 70B * 2 bytes (FP16) = 140GB
HBM bandwidth (A100): 2TB/s

Loading weights into GPU once:
  Time = 140GB / 2TB/s = 0.07s
  
For 100 requests (100*150 tokens input + 100*50 output = 20K tokens):
  Memory overhead: 0.07s / 100 requests = 0.0007s per request (negligible)
```

## Component 3: Where Cost Actually Goes

Real-world breakdown (Llama 70B on A100):

```
GPU utilization: 60% (not fully packed)
Cost per 1M tokens:
  - Compute (GPU hours): $0.80
  - Memory bandwidth: $0.05
  - Network (ingress/egress): $0.10
  - Cooling/power loss: $0.05
  
  Total: ~$1.00 per 1M tokens
```

Smaller model (Llama 7B):
```
Same A100, 10x faster inference:
  Cost per 1M tokens: ~$0.10
```

Larger model (Llama 405B, multi-GPU):
```
Requires 4 A100s ($6/hour):
  Cost per 1M tokens: ~$3.00
```

## Real Numbers (AWS Bedrock)

```
Claude 3 Opus: $15 per 1M input tokens
Claude 3.5 Sonnet: $3 per 1M input tokens
Llama 3.1 8B: $0.30 per 1M input tokens
```

Why the spread?
- Larger models cost more (more compute)
- More capable models priced higher (value-based)
- Self-served cheaper than managed

## Cost Accounting: Full Picture

### Don't Forget

```
Infrastructure beyond GPU:
  - CPU for request routing: $0.02/1M tokens
  - Storage (model weights on disk): $0.01/1M tokens
  - Networking (egress): $0.10/1M tokens
  - Observability/logging: $0.05/1M tokens
  
Subtotal infrastructure overhead: ~$0.20/1M tokens (20% of compute cost)
```

### Common Mistake: Idle Time

```
A100 rental: $1.50/hour

If GPU is idle 50% of the time (no requests):
  Effective cost doubles: $3.00/hour

Utilization matters more than hardware cost!
```

## Interview Pattern: Cost Estimation

```
Q: "Estimate the cost to serve 1M requests/day of Llama 70B inference."

Weak answer:
  "A100 costs $1.50/hour, multiply by 24..."
  (❌ Ignores utilization, batch effects, full cost)

Strong answer:
  "Need to know request characteristics:
  
  1. Request size:
     - Input tokens: 500 (prompt)
     - Output tokens: 200 (generation)
     - Total: 700 tokens per request
  
  2. Daily volume:
     1M requests/day * 700 tokens = 700M tokens/day
     = 29.2M tokens/hour
  
  3. A100 throughput:
     - Prefill: 150 tokens/sec × 3600 = 540K tokens/hour
     - Decode: 20 tokens/sec × 3600 = 72K tokens/hour
     - Mixed workload: ~100K tokens/hour (conservative)
  
  4. GPUs needed:
     29.2M tokens/hour / 100K tokens/hour = 292 A100s
  
  5. Cost calculation:
     292 GPUs × $1.50/hour × 24 hours = $10,512/day
     Plus overhead (10%): ~$11,500/day
     
     Per request: $11,500 / 1M = $0.0115/request
     Per output token: $0.0115 / 200 = $0.0000575/token
  
  6. Sanity check:
     Public pricing (Claude Opus): $15/1M input
     Our model (Llama 70B): ~$8/1M input (cheaper, makes sense)
     
  7. Optimization levers:
     - Reduce output tokens: would decrease cost ~5x
     - Smaller model (Llama 13B): would reduce cost ~7x
     - Higher utilization: would reduce cost ~20%
  
  8. Monitor:
     - Track actual tokens/sec
     - Compare to projections
     - Watch for idle time (queue management needed)
     - Alert if cost exceeds budget"

Why this signals good judgment:
  - You thought through utilization (not just hardware cost)
  - You calculated tokens per hour (not just wall time)
  - You included overhead (realistic)
  - You had optimization levers (how to reduce cost)
  - You validated against public pricing (sanity check)
```

## Checklist: Cost Modeling

- [ ] Calculate GPU utilization (not just time)
- [ ] Account for prefill + decode separately (different throughput)
- [ ] Include infrastructure overhead (routing, storage, networking)
- [ ] Monitor actual vs projected (costs drift)
- [ ] Know your public pricing baseline (Claude, Bedrock)
- [ ] Have optimization levers (smaller model, quantization, batching)
- [ ] Alert on cost anomalies (runaway inference)

## What This Signals

- You've calculated real infrastructure costs
- You understand utilization matters more than hardware cost
- You think about prefill/decode efficiency
- You validate against public pricing (grounded thinking)
