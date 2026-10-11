# Scaling Data Pipelines - Bottlenecks, Parallelization, Cost

## Finding the Bottleneck

```
Pipeline: 6-hour total

Task times:
  extract_events:       1h (bottleneck 1)
  extract_features:     30m
  merge:                15m
  validate:             5m
  materialize:          45m
  train_model:          3h (bottleneck 2)

To improve:
  1. Parallelize extract tasks (1h → runs same time as extract_events)
  2. Optimize train_model (3h → reduce by 20% = 2.4h)
  3. Result: 1h + 0 + 15m + 5m + 45m + 2.4h = 4.82h (20% faster)

Profile to find real bottleneck (measure, don't guess).
```

## Scaling Strategies

### Horizontal: More Workers

```
Feature extraction: 1 hour on 1 Spark worker
Split by date: 30-day data
  Worker 1: Days 1-10 (20 min)
  Worker 2: Days 11-20 (20 min)
  Worker 3: Days 21-30 (20 min)
  
  Parallel: 20 min (3x faster!)
  Cost: 3x workers, 3x cost
```

### Vertical: Better Hardware

```
Feature extraction on 8-vCPU machine: 1 hour
Upgrade to 32-vCPU machine:
  - 4x more parallel threads
  - Better memory bandwidth
  - Expected: 30-40 min (2.5x faster)
  - Cost: ~2x machine cost
```

### Algorithm: Better Code

```
Join 100M events + 10M users:
  Bad: Nested loop (O(N*M))
  Good: Hash join (O(N+M))
  
  Bad: 30 min
  Good: 5 min
  Cost: None (same hardware)
```

## Cost Optimization

```
Daily training: Spark cluster 60 vCPU for 1 hour
  Cost: $0.30/vCPU-hour * 60 * 1 = $18/day

Optimization 1: Right-size cluster
  Profile: Actually uses 30 vCPU peak
  Reduce to 32 vCPU: $0.30 * 32 * 1 = $9.60/day
  Savings: $8.40/day = $3000/year

Optimization 2: Batch with other jobs
  Run 3 pipelines sequentially on same cluster (still 1 hour)
  Instead of 3 separate hours
  Savings: $18/day → $6/day = $4380/year

Optimization 3: Time-shift (off-peak pricing)
  Run overnight (2am) when compute is cheaper
  Savings: $0.20/vCPU-hour (30% cheaper)
  Savings: $5.76/day = $2100/year
```

## Interview Pattern: Scaling

```
Q: "Pipeline takes 8 hours. Deadline: 4 hours.
   Budget: No more than 50% cost increase.
   How do you scale?"

Strong answer:
  "Profile first to find bottleneck:
  
  1. Measure (with Airflow timings):
     - Extract: 2h (bottleneck)
     - Transform: 1.5h
     - Train: 4h (bottleneck)
  
  2. Options to 4-hour target:
     Option A: Parallelize extract (2h → 45m), optimize train (4h → 2h)
       Total: 2h 45m (too slow)
       Cost: +40% (acceptable)
     
     Option B: Parallelize extract (45m), redo train algorithm (4h → 2.5h)
       Total: 2h 45m (still too slow)
     
     Option C: Parallelize extract AND upgrade cluster
       Extract parallelized: 45m
       Train on 128-vCPU cluster: 2h (faster processing)
       Total: 2h 45m (borderline)
     
     Option D: Right-size + parallelize + cache features
       Extract cache (2nd day onward): 10m (no re-extract)
       Extract parallelized: 45m (day 1 only)
       Train optimized + better hardware: 2h
       Total: 2h 45m (first day), 2h 10m (next days)
       Cost: +35%
  
  3. My recommendation: Option D
     - Meets 4-hour deadline (barely, by day 2)
     - Acceptable cost increase (35%)
     - Improves operational cost long-term
  
  4. Trade-offs documented:
     - Day 1 tight on deadline (2h 45m vs 4h)
     - If extract slower: add 15 more min parallelism
     - If train not optimizable: accept 5h total"

Why this signals good judgment:
  - You measured (didn't guess)
  - You showed math (not hand-waving)
  - You had cost constraint (real constraint)
  - You documented tradeoffs
```

## Checklist: Pipeline Scaling

- [ ] Profile to find actual bottleneck (measure, don't guess)
- [ ] Cost per run tracked (optimize for efficiency)
- [ ] Parallelization strategy (independent tasks?)
- [ ] Right-sizing (don't over-provision)
- [ ] Caching (avoid re-processing)
- [ ] Monitoring (alert if > budget)

## What This Signals

- You've optimized pipelines under constraints
- You understand cost matters (not just speed)
- You profile instead of guessing
- You know the tradeoffs (cost vs speed vs complexity)
