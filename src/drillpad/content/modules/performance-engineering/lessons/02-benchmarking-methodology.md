# Benchmarking Methodology: Statistical Rigor, Avoiding Pitfalls

## Firm Archetype: Stripe, AWS, Google, Anthropic

**Problem:** I claim my code is 2x faster. But is it really? Or is it just variance?

- **No warmup:** first run has cold cache, appears 3x slower
- **Single run:** variance could be ±50%, conclusion is noise
- **Ignoring GC:** Java pauses hide true performance
- **Single thread vs multi-thread:** threading overhead changes behavior
- **Different hardware:** benchmark on target hardware or result is meaningless

**Why hard:** Most benchmarks are wrong. You must be rigorous.

---

## Benchmark Design Principles

```
Bad benchmark:
  $ time python my_function.py
  real 0m0.500s
  "It's fast!"
  (but: could be 0.400-0.600s due to variance)
  
Good benchmark:
  1. Warmup run (not counted)
  2. Repeat 10+ times
  3. Record all samples (not just average)
  4. Calculate mean, median, stddev, percentiles
  5. State confidence interval
  6. Report hardware (CPU, RAM, OS)
```

---

## Statistical Rigor

```
Sample runs:
  Run 1: 100ms
  Run 2: 105ms
  Run 3: 98ms
  Run 4: 102ms
  Run 5: 101ms
  
Mean: 101.2ms
Stddev: 2.2ms
Confidence interval (95%): 101.2 ± 2.2ms

Claim: "My algorithm is 100ms ± 2.2ms (95% CI)"
Better than: "My algorithm is 100ms"
```

---

## Pitfall 1: Cold Cache

```
First run (cold):
  CPU cache empty
  RAM latency: 100ns
  Time: 500ms

Second run (warm):
  Data in L3 cache
  Cache latency: 50ns
  Time: 100ms

Naive benchmark: first run only → 500ms (WRONG!)
Correct: discard first run, use second → 100ms
```

---

## Pitfall 2: System Jitter

```
Process running on shared CPU:
  Run 1: 100ms (no interference)
  Run 2: 150ms (garbage collection on another process)
  Run 3: 105ms (OS scheduler interrupt)
  Run 4: 180ms (heavy disk I/O)
  Run 5: 102ms (quiet)
  
Average: 127ms (misleading!)
Median: 105ms (more robust)

Fix: disable background processes, pin to CPU, run multiple times
```

---

## Pitfall 3: GC Pauses (Java/C#/Python)

```
Java benchmark without GC awareness:
  Iteration 1: 100ms (no GC)
  Iteration 2: 110ms (no GC)
  Iteration 3: 1200ms (FULL GC pause!)
  Iteration 4: 95ms (no GC)
  
Average: 376ms (one GC pause ruined it!)

Correct approach:
  1. Force GC before measurement: System.gc()
  2. Discard iterations with GC pauses
  3. Or: use low-GC language (C++, Rust)
```

---

## Pitfall 4: Lack of Warmup

```
JIT compilation (Java, JavaScript):
  First call: interpreted, 10ms
  Calls 2-100: compiled to native, 1ms each
  
Naive benchmark:
  Run once: 10ms (measuring interpreter, not compiled code!)
  
Correct:
  1. Run 1000 iterations (to trigger JIT)
  2. Discard them (not measured)
  3. Run measurement on JIT-compiled code
  
Result: 1ms (real performance)
```

---

## Pitfall 5: Compiler Optimization Removal

```
C++ without optimization:
  ```cpp
  int sum = 0;
  for (int i = 0; i < 1000000; i++) {
    sum += i * i;
  }
  result = sum;
  ```
  Time: 10ms (actual loop executed)
  
C++ with optimization (O3):
  Compiler sees: result = sum of 1 to 1000000 (unused!)
  Compiler optimizes: entire loop removed!
  Time: 0.001ms (loop never executes!)
  
Correct: use result (printf it, or return it, make compiler keep it)
```

---

## Benchmark Template: Python

```python
import time
import statistics
import gc

def benchmark(func, *args, iterations=100, warmup=10, **kwargs):
    """Benchmark a function with statistical rigor."""
    
    # Warmup (not measured)
    for _ in range(warmup):
        func(*args, **kwargs)
    
    # Measure
    times = []
    for _ in range(iterations):
        gc.collect()  # Force GC before measurement
        
        start = time.perf_counter()
        func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        
        times.append(elapsed * 1000)  # convert to ms
    
    # Statistics
    mean = statistics.mean(times)
    median = statistics.median(times)
    stddev = statistics.stdev(times) if len(times) > 1 else 0
    p99 = sorted(times)[int(len(times) * 0.99)]
    
    print(f"Benchmark results ({iterations} iterations):")
    print(f"  Mean:   {mean:.3f}ms")
    print(f"  Median: {median:.3f}ms")
    print(f"  StdDev: {stddev:.3f}ms")
    print(f"  P99:    {p99:.3f}ms")
    print(f"  CI 95%: {mean:.3f} ± {1.96 * stddev / (len(times)**0.5):.3f}ms")

# Usage
def my_function():
    total = sum(i * i for i in range(1000))
    return total

benchmark(my_function, iterations=100, warmup=10)
# Output:
# Benchmark results (100 iterations):
#   Mean:   0.050ms
#   Median: 0.048ms
#   StdDev: 0.005ms
#   P99:    0.065ms
#   CI 95%: 0.050 ± 0.001ms
```

---

## Pitfall 6: Microbenchmark vs Realistic Workload

```
Microbenchmark: measure one function in isolation
  Example: benchmark hash_map::insert() in a loop
  Time: 1 µs per insert
  
Real workload: hash map under actual conditions
  - Concurrent access (lock contention)
  - Mixed insert/lookup (cache behavior changes)
  - Larger data (L1 cache no longer sufficient)
  - Real time: 5 µs per insert (5x slower!)
  
Lesson: microbenchmarks are useful but can be misleading
Fix: benchmark end-to-end scenarios, not just components
```

---

## Benchmark vs Profile vs Load Test

```
Benchmark:
  - Measure one operation (hash insert, JSON parse)
  - Conditions: isolated, controlled
  - Goal: know raw performance
  
Profile:
  - Measure real program running
  - Conditions: realistic load
  - Goal: find bottlenecks
  
Load test:
  - Measure at scale (1000 concurrent users)
  - Conditions: realistic
  - Goal: verify SLA (P99 < 200ms)
  
All three are needed for different insights
```

---

## Real Example: Comparing Data Structures

**Problem:** Should I use array or linked list?

```python
# Bad benchmark (microbenchmark):
# Measure: insert at front
# Array: O(n), 100 µs
# Linked list: O(1), 1 µs
# Conclusion: linked list is 100x faster!

# Good benchmark (realistic):
# Measure: insert + random access
# Array: O(n) insert, O(1) access
# Linked list: O(1) insert, O(n) access
# Real workload: 50% inserts, 50% access
# Array: 50 µs insert + 1 µs access = 51 µs total
# Linked list: 1 µs insert + 100 µs access = 101 µs total
# Conclusion: array is faster for this workload!
```

---

## Benchmarking Hardware Consistency

```
Benchmark on laptop:
  MacBook Pro 2021
  Result: 100ms
  
Benchmark on production server:
  AMD EPYC 7742
  Result: 15ms
  
Are they comparable? NO!
  └─ Different CPU, cache, memory
  └─ Different OS scheduling
  └─ Different thermal conditions

Report:
  "100ms on MacBook Pro 2021"
  "15ms on AMD EPYC 7742 (production hardware)"
  
Interviews want: "What's the absolute performance on real hardware?"
```

---

## Confidence: How Many Samples Do I Need?

```
Sample size for 95% confidence:
  σ (stddev) = 1ms
  Error margin = 0.1ms
  n = (1.96 * σ / margin)^2 = (1.96 * 1 / 0.1)^2 = 384 samples
  
If stddev is high (10ms):
  n = (1.96 * 10 / 0.1)^2 = 38,416 samples (too many!)
  Fix: reduce variance (pin CPU, disable jitter)

If stddev is low (0.1ms):
  n = (1.96 * 0.1 / 0.1)^2 = 3.8 ≈ 4 samples
  
Generally: use at least 30 samples (rules of statistics)
          use at least 100 samples (industry practice)
```

---

## Benchmark Report Template

```
Algorithm Performance Comparison
================================

Hardware: AMD EPYC 7742, 256GB RAM, Ubuntu 22.04
Compiled: g++ -O3 -march=native
Warmup: 10 iterations
Measurement: 100 iterations, mean of 5 runs

Results:
  Hash Map Insert (1M items):
    Std map:     15.2 ± 0.8ms (p99: 17.5ms)
    Dense hash:   8.3 ± 0.3ms (p99: 9.1ms)
    Speedup: 1.83x
    
  Binary Tree Insert (1M items):
    Std map:     15.2 ± 0.8ms
    Skip List:   12.1 ± 0.5ms
    Speedup: 1.25x

Conclusion:
  Dense hash map is fastest, but memory overhead is 3x.
  Skip list is good balance of speed (1.25x) and memory (1.1x).
  For this workload, recommend dense hash map.
```

---

## Q&A

**Recall 1:** You run benchmark 10 times. Results: 100, 101, 99, 102, 105, 98, 100, 150, 101, 100ms. What do you report?

*Must-say:*
- One run is 150ms (outlier, GC pause?)
- Median: 100.5ms (robust to outliers)
- Mean: 105.6ms (skewed by 150ms)
- Report: "100ms median, 105ms mean (1 outlier of 150ms, likely GC pause)"
- Better: discard 150ms, report: "100.4ms median, 100.6ms mean (n=9)"

**Probe 1:** Microbenchmark says hash map insert is 1 µs. Real benchmark says 10 µs. Why?

*Expected:*
- Microbenchmark: isolated insert, no contention, data in cache
- Real: concurrent inserts, lock contention, cache misses
- Lesson: always benchmark real conditions, not isolated components

**Numeric 1:** Stddev = 2ms, want error margin < 1ms, confidence 95%. How many samples?

*Working:*
- n = (z * σ / margin)^2
- z = 1.96 (for 95% confidence)
- n = (1.96 * 2 / 1)^2 = (3.92)^2 ≈ 15 samples

---

## Questions for the Interviewer

- How do you benchmark performance-sensitive code?
- What's your sample size? (10, 100, 1000 runs?)
- Do you control for system jitter? (pin CPU, disable turbo?)
- Have you found microbenchmarks misleading? (example?)
- How do you report results? (mean, median, percentiles?)
- What hardware do you benchmark on? (actual production?)

