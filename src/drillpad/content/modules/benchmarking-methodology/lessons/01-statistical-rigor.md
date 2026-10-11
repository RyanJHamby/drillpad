# Benchmarking with Statistical Rigor

## Why Rigor Matters

Wrong: Run once, report the number
Right: Run 20 times, report percentiles, confidence intervals

```
OrderBook bench: "P50 latency is 0.21µs"
Question: Is it 0.21µs ± 0.01µs or ± 0.1µs?
Answer: Run 20 times, compute stdev
```

## Methodology

**1. Warmup runs (discard first 2-3)**
- Cold caches, JIT not warmed up
- Discard, don't include in stats

**2. Run N times (20-100 typical)**
```
for i in 1..20:
  result[i] = run_benchmark()

stats = {
  min: min(result),
  p50: percentile(result, 0.50),
  p99: percentile(result, 0.99),
  max: max(result),
  stdev: std(result),
  mean: mean(result)
}
```

**3. Report percentiles, not averages**
```
WRONG: "Average latency: 0.21µs"
RIGHT: "P50: 0.208µs, P99: 2.1µs, P99.9: 3.2µs"

Why? Averages hide outliers. One 100µs spike in 20 runs = invisible in average, visible in P99.9
```

**4. Confidence intervals**
```
"P50 latency is 0.21µs ± 0.02µs (95% CI)"
= 95% chance true value is between 0.19-0.23µs

Wider CI = less certain (need more runs)
```

**5. Avoid measurement artifacts**
- CPU scaling: pin to core, fix clock frequency
- Cache pollution: start fresh, flush caches
- Noise: run on quiet machine (no other processes)
- Outlier runs: note any spikes, don't discard (they're real)

## Red Flags

- Report only "average" (hiding variance)
- Single run reported as truth
- No warmup runs
- Report "best case" (cherry-picking)
- Compare across different hardware without noting it

## Real Example

```
OrderBook: P50 0.21µs on EC2 c6i.large, 3 runs, warmup 2

❌ WRONG: "0.21µs" (single number, no variance)
✅ RIGHT: "P50: 0.208-0.214µs, P99.9: 3.09-3.23µs (ranges across 3 runs)"

The variance tells you:
- Tight P50 (0.208-0.214) = stable algorithm
- Wide P99.9 (3.09-3.23) = rare stalls (map rebalancing)
```
