# Design Judgment: Hardware Selection (A100 vs H100, Cost-Per-FLOP)

## The Core Decision Framework

```
GPU choice determines:
  - Performance ceiling (TFLOPS)
  - Memory bandwidth (GB/s)
  - Cost per unit compute ($k per TFLOP)
  - Power efficiency (W per TFLOP)

Wrong choice: Overpay 2-3x for unused headroom
Right choice: Fit workload exactly, minimize cost
```

## Hardware Comparison Matrix

```
GPU        | Memory | TFLOPS | Cost    | Cost/TFLOP | Memory BW | Power
-----------|--------|--------|---------|------------|-----------|-------
A100 40GB  | 40GB   | 312    | $12k    | $38.5/TF   | 2.0 TB/s  | 250W
H100 80GB  | 80GB   | 989    | $40k    | $40.4/TF   | 3.3 TB/s  | 350W
H200       | 141GB  | 1457   | $50k    | $34.3/TF   | 4.8 TB/s  | 450W
L40S (CPU) | 48GB   | 568    | $10k    | $17.6/TF   | 2.4 TB/s  | 250W
```

**Key insight:** Cost per TFLOP is similar, but *memory bandwidth* and *memory capacity* differ.

## Decision Tree: Which GPU?

### Question 1: Memory Capacity

**"Does my workload fit?"**

```
LLM 70B parameters:
  - Model weights: 70B × 2 bytes (FP16) = 140GB
  - KV-cache per 100 concurrent users: 100 × 4K × 100 × 2 = 80GB
  - Total: 220GB minimum
  
GPU options:
  - A100 40GB: Doesn't fit (can't shard 70B model on one GPU)
  - H100 80GB: Doesn't fit (need 2 GPUs, tensor parallelism)
  - H200 141GB: Barely fits (model + some KV-cache)
  
Decision: H200 (only option that fits)
```

**This is not a choice—it's a constraint.**

### Question 2: Memory Bandwidth (If Capacity Allows)

**"Is the workload memory-bound or compute-bound?"**

Use roofline model:

```
Roofline = min(compute_ceiling, memory_ceiling)
  Compute ceiling: TFLOPS
  Memory ceiling: (memory_BW in GB/s) × (FLOPS per byte)

For inference (prefill = compute-bound, decode = memory-bound):

Prefill 32 tokens (compute-bound):
  - A100: Compute ceiling 312 TF/s (roofline)
  - H100: Compute ceiling 989 TF/s (roofline)
  - H100 is 3.2x faster ✓

Decode 1 token (memory-bound):
  - A100: Memory ceiling = 2.0 TB/s × 156 FLOPS/byte = 312 TF/s
  - H100: Memory ceiling = 3.3 TB/s × 156 FLOPS/byte = 514 TF/s
  - H100 is 1.6x faster (not 3.2x, bandwidth limited)
```

**If workload is memory-bound:** Memory bandwidth matters more than TFLOPS.
**If workload is compute-bound:** TFLOPS matters more.

### Question 3: Cost ROI

**"Does the performance gain justify the cost?"**

```
Scenario: Training 70B model, 8 H100s vs 16 A100s

Option 1: 8 × H100 (80GB)
  - Cost: 8 × $40k = $320k
  - Training time: 40 hours
  - Total: $320k + (40 hrs × $100/hour GPU cost) = $324k

Option 2: 16 × A100 (40GB)
  - Cost: 16 × $12k = $192k
  - Training time: 64 hours (2.5x slower)
  - Total: $192k + (64 hrs × $25/hour GPU cost) = $193.6k
  
Winner: A100 (save $130k)
Cost per hour of compute: $100 (H100) vs $25 (A100)
But total cost: A100 wins because training time matters less than GPU cost
```

## Firm-Specific Hardware Choices

### Trading: Unlikely to Use GPU

```
Why? Latency critical (network >> GPU latency)
  - GPU initialization: 5ms+
  - Network latency: 1ms
  - Ordering: Network latency dominates, GPU adds nothing

If needed: Embedded GPU (FPGA for specific algorithm)
  - Lower power than H100
  - Fixed latency (no variance)
  - Cost: $1-5k (not $40k)
```

### AI Infra: Careful Cost Optimization

**Anthropic inference service:**

```
Requirements:
  - 1000 concurrent users
  - P99 latency: 200ms
  - Batch size: 32 (fits memory)

Calculation:
  - H100 80GB batch 32: throughput = 31 QPS (100 users per H100)
  - Need: 1000 users / 100 = 10 H100s
  - Cost: 10 × $40k = $400k
  - Cost per user per month: $40 (assuming 3-year lifetime)

Could we use A100?
  - A100 40GB batch 16 (half the memory): throughput = 15 QPS
  - Need: 1000 users / 15 = 67 A100s
  - Cost: 67 × $12k = $804k
  - Cost per user per month: $80 (2x more expensive)
  
Decision: H100 (memory capacity forces it)
```

**Interview answer:**
```
Q: "How would you scale inference to 1000 concurrent users?"

"Requirements:
  - 1000 concurrent users, P99 < 200ms
  - Need batch size 32 for throughput
  - Model 70B: 140GB weights + KV-cache

GPU choice:
  - A100 40GB: Can't fit 70B + batch 32 KV-cache
  - H100 80GB: Fits, batch 32, 31 QPS per GPU
  - Total: 1000 users / 31 QPS = 32 H100s
  
Cost: 32 × $40k = $1.28M capex
  + 32 × 350W × 24h × 365 × $0.10/kWh = $310k opex/year
  
Cost per user: $40/month (over 3 years)
If demand dropped 50%: Scale to 16 H100s, save $20M/year"
```

## Hardware Upgrade Decisions

**When should you upgrade GPU?**

```
Decision tree:

1. Is current GPU memory insufficient?
   → YES: Must upgrade (no choice)
   → NO: Continue to next question

2. Is performance bottleneck memory bandwidth?
   → YES: Upgrade to higher BW GPU (H100 > A100)
   → NO: Continue to next question

3. Is performance bottleneck compute (TFLOPS)?
   → YES: Upgrade to faster GPU (H100 > A100)
   → NO: No upgrade needed

4. ROI calculation:
   Cost of upgrade > savings from performance?
   → If yes: Don't upgrade (current GPU is optimal)
   → If no: Upgrade
```

**Real example: When NOT to upgrade**

```
Using A100 for batch inference:
  - Current: 1000 QPS (P99 = 50ms)
  - User demand: 1000 QPS
  
Upgrade to H100?
  - Would get: 3200 QPS (P99 = 50ms, same batching)
  - Cost: $40k vs $12k (1 extra GPU equivalent)
  - Benefit: Headroom for 2x traffic spike
  
ROI: $40k > benefit of headroom (might not happen)
Decision: Don't upgrade (A100 is optimal)

Alternative: Keep A100, add A100 when traffic increases
  - Scales incrementally with demand
  - No wasted capacity
```

## Production Interview Scenario

**Q: "Describe your inference fleet hardware. How do you decide what to buy?"**

Weak answer:
```
"We use H100s because they're the fastest."
(❌ Doesn't address cost, doesn't address if they fit workload,
    doesn't address ROI)
```

Strong answer:
```
"Inference workload analysis:
  - Model: 70B LLM (140GB weights)
  - Batch size: 32 (32 concurrent users per GPU)
  - QPS target: 100
  - P99 latency: 150ms
  
GPU requirements:
  - Memory: Need ≥ 140GB + KV-cache
    A100 40GB insufficient (can't fit model + large batch)
    H100 80GB fits (model + batch 32 KV-cache)
    
  - Bandwidth: Decode is memory-bound
    H100 3.3 TB/s > A100 2.0 TB/s (20% faster decode)
    
Cost analysis:
  - 100 QPS needs: 100 / 31 QPS per GPU = 3.2 H100s
  - Use 4 H100s: $160k capex
  - Total cost per user: ~$10/month
  
Hardware refresh schedule:
  - H100 expected 3-5 year lifetime
  - Watch for H200/H300 (higher memory, lower cost/FLOP)
  - If H300 has 180GB at $35k: Upgrade (better density, lower power)
  
Metrics we track:
  - Cost per QPS
  - Cost per inference token
  - Power per inference
  - GPU utilization (want 70-80%, not 100%)
"
```

Why this works:
- Rooted the choice in requirements (memory, bandwidth)
- Showed cost calculation (not just "H100 is faster")
- Explained the tradeoff (more expensive GPU vs multiple cheap ones)
- Mentioned refresh strategy (shows operational thinking)
- Named metrics (shows you know what to measure)

## Quick Checklist

**Before choosing hardware:**

- [ ] Does it fit? (memory capacity constraint?)
- [ ] What's the bottleneck? (memory BW? compute? network?)
- [ ] Cost-per-FLOP comparison (all GPUs similar, choice is subtle)
- [ ] Total cost calculation (capex + opex + training time)
- [ ] Utilization target (70-80% sweet spot)
- [ ] Refresh strategy (3-5 year cycle, plan for next generation)

**Red flags:**
- "H100 is fastest, so we use it" (no cost analysis)
- "A100 is cheapest" (if model doesn't fit, doesn't matter)
- "We max out GPUs at 100%" (thermal/reliability risk)

**Green flags:**
- Named the constraint (memory, bandwidth, compute)
- Calculated cost-per-QPS
- Mentioned utilization headroom
- Discussed refresh strategy

