# Cost-Latency Frontier - Pareto & Decision Framework

## The Pareto Frontier

You can't have it all: unlimited speed + unlimited cost savings.

But you can pick the best operating point.

```
Operating points (Llama family on A100):

      Latency (P99, seconds)
        ^
        |     7B (INT4)
        | 0.5 •
        |     | 7B (INT8)
        |     | 0.7 •
        | 1.0 |     | 13B (INT8)
        |     |     | 1.5 •
        | 1.5 |     |     |  70B (INT8)
        |     |     |     |  4.0 •
        | 2.0 |     |     |     |
        |     |     |     |     | 405B (FP16)
        | 5.0 |     |     |     |    8.0 •
        |_____|_____|_____|_____|______> Cost ($/1M tokens)
             0.10  0.20  1.00   3.00
        
        Frontier (can't improve one without worsening other):
          7B INT4 → 7B INT8 → 13B INT8 → 70B INT8 → 405B FP16
        
        Off-frontier (dominated):
          7B FP16: slower than INT8, same cost (skip it)
          13B INT4: not enough accuracy gain over 7B INT4
```

## Reading Your Frontier

```
If you're here →  7B INT8 (latency 0.7s, cost $0.10)
- Move left: Get 405B FP16 (latency 8s, cost $3.00) - worse
- Move up: Get 7B INT4 (latency 0.5s, cost $0.08) - marginal gain
- Move right: Get 13B INT8 (latency 1.5s, cost $0.20) - worse both

→ You're near Pareto optimal for your constraints.
```

## Hardware Dimension: A100 vs H100 vs TPU

```
Same model, different hardware:

Llama 70B:
  - A100 (80GB): 20 tokens/sec, $1.50/hour → $1.00/1M tokens
  - H100 (80GB): 50 tokens/sec, $2.00/hour → $0.40/1M tokens
  - TPU v4 (128GB): 100 tokens/sec, $1.50/hour → $0.15/1M tokens

Decision:
  If cost-optimizing: TPU (cheaper)
  If latency-optimizing: TPU (faster)
  If flexibility: A100 (widely available, multi-cloud)
```

## Complete Framework: Choosing Operating Point

```
Step 1: Define constraints
  - Latency SLA (P99, milliseconds)
  - Cost budget ($/day or $/request)
  - Accuracy requirement (% correct)
  - Availability requirement (uptime %)

Step 2: Map to points on frontier
  For each (model, quantization, batching):
    - Measure latency
    - Calculate cost
    - Benchmark accuracy
  → Plot on frontier

Step 3: Filter by constraints
  Remove points that violate:
    - Latency > SLA → too slow
    - Cost > budget → too expensive
    - Accuracy < requirement → not good enough
  
Step 4: Pick from remaining
  Usually, pick the cheapest that meets latency
  (Cost is most constrained; latency is fixed by SLA)

Example:
  SLA: P99 < 2s
  Budget: $500/day
  Accuracy: > 85%
  
  Candidates:
    ✓ 7B INT8: $0.10/1M, P99=0.7s, 80% acc → Fails accuracy
    ✓ 13B INT8: $0.20/1M, P99=1.5s, 90% acc → Passes all
    ✓ 70B INT8: $1.00/1M, P99=3.5s, 96% acc → Violates latency
  
  → Pick 13B INT8
```

## Real-World Example: Product Decision

```
Search relevance system (10M queries/day)

Current:
  Model: 70B Llama
  Cost: $1000/day
  Latency P99: 300ms (good)
  Relevance: 94% (users satisfied)

Problem: Budget cut to $400/day

Analysis:
  1. Can we use smaller model?
     13B: 88% relevance (6% worse, unacceptable)
     
  2. Can we offload some?
     Heavy queries (10%): 70B ($100/day)
     Light queries (90%): 7B ($90/day)
     Mixed: $190/day (save 81%)
     Relevance: 89% overall (acceptable trade)
  
  3. Can we cache?
     Top 20% queries account for 80% volume
     Cache answers for 3 days
     → Reduces compute 60%
     Cost: $400/day → $160/day ✓
     
  4. Final decision:
     - Cache popular queries (3-day TTL)
     - Use 13B for non-cached (90% accuracy)
     - A/B test caching vs non-cached
     - Monitor relevance metrics
     
  Cost/accuracy frontier:
    Pure 70B: $1000/day, 94% relevance
    13B+cache: $160/day, 91% relevance
    → 84% cost savings, 3% relevance loss
```

## Monitoring the Frontier

```
Track continuously:
  - Actual tokens/sec per GPU (is it matching benchmarks?)
  - Actual cost per token (watch for overhead)
  - Actual latency P50, P99, P99.9 (not average)
  - Accuracy on real data (benchmarks ≠ production)

Alert thresholds:
  - Cost per token > 1.2x baseline → investigate
  - Latency P99 > SLA → scale or optimize
  - Accuracy drift > 2% → retraining needed
  - GPU utilization < 60% → reconfigure batching
```

## Interview Pattern: Operating Point Selection

```
Q: "You have 3 candidate architectures. How do you choose?"

Weak answer:
  "Pick the fastest one"
  (❌ No budget awareness, no tradeoffs)

Strong answer:
  "Need to define the frontier and constraints:
  
  1. Candidate points:
     A) Model: 405B, Quantization: FP16, Batch: 1
        Latency: 8s, Cost: $3/1M tokens, Accuracy: 98%
     
     B) Model: 70B, Quantization: INT8, Batch: 10
        Latency: 2s, Cost: $0.5/1M tokens, Accuracy: 95%
     
     C) Model: 13B, Quantization: INT8, Batch: 50
        Latency: 1.5s, Cost: $0.15/1M tokens, Accuracy: 88%
  
  2. Plot on frontier:
     A is dominated by B (slower + more expensive)
     B and C are on frontier
  
  3. Constraints:
     - Budget: $100/day
     - Latency SLA: < 3s
     - Accuracy: > 85%
  
  4. Filter:
     A: Violates cost (too expensive)
     B: Passes cost, latency, accuracy ✓
     C: Passes cost, latency, accuracy ✓
  
  5. Choose B:
     Why? Same accuracy as C (95% > 85%)
     C trades 7% accuracy for 3x cost savings
     If accuracy matters: Pick B
     If cost matters: Pick C
  
  6. Validation:
     - Benchmark B on production data (not synthetic)
     - Test with real query distribution
     - A/B test (B vs C) on 1% traffic
     - Monitor accuracy drift over time"

Why this signals good judgment:
  - You built the frontier (not arbitrary)
  - You understood dominated points
  - You validated constraints are real
  - You'd A/B test before committing
```

## What This Signals

- You understand Pareto thinking (can't optimize everything)
- You build decision frameworks (not gut-feel choices)
- You validate before deploying (benchmarks vs production)
- You monitor over time (frontier shifts as loads change)
