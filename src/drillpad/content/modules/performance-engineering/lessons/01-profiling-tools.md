# Profiling Tools: Finding Bottlenecks (perf, flamegraph, TSAN, NVIDIA Profiler)

## Typical Contexts: trading systems, AI infrastructure, and cloud platforms

**Problem:** Your system is slow. Where is the time being spent?

- CPU? Memory? I/O? Lock contention?
- Which functions are hot?
- Are there cache misses?
- Thread races?
- GPU bottleneck or CPU bottleneck?

**Why hard:** Can't optimize what you can't measure. Guessing is worse than useless.

---

## Profiling Types

```
Sampling profiler (perf, flamegraph):
  ├─ Interrupt at 1000Hz (every 1ms)
  ├─ Record stack trace
  ├─ Build histogram of time spent
  ├─ Pro: low overhead, tells you what CPU is doing
  └─ Con: misses fast functions
  
Instrumentation profiler (TSAN, Valgrind):
  ├─ Insert code to track every operation
  ├─ Pro: exact measurements
  └─ Con: 10-100x slowdown (only for debugging)
  
Hardware counters (perf stat):
  ├─ Read CPU counters (cache misses, branch mispredicts, etc.)
  ├─ Pro: tells you WHY code is slow
  └─ Con: only available on some systems
  
GPU profiler (NVIDIA):
  ├─ Track GPU kernel execution, memory transfers
  ├─ Pro: see GPU bottleneck (compute vs memory)
  └─ Con: NVIDIA-specific
```

---

## Profiling in Action: Linux perf

```bash
# Record CPU profile (1000 samples/sec)
$ perf record -F 1000 ./my_program

# Report top functions by time
$ perf report

# Output:
#    %   Samples  Function
#   30%   15000  _order_book_insert
#   25%   12500  _hash_lookup
#   20%   10000  _memory_allocate
#   15%    7500  _lock_acquire
#   10%    5000  other

# Flamegraph (visual: wider = more time)
$ perf script | stackcollapse-perf.pl | flamegraph.pl > output.svg
```

**Reading flamegraph:**
- Y-axis: call stack (bottom = main, top = leaf function)
- X-axis: wall-clock time spent
- Width: proportional to CPU time
- Color: random (just for visualization)

---

## Hardware Counter Profiling (perf stat)

```bash
$ perf stat ./my_program
Performance counter stats for './my_program':
      1,234,567,890  cycles
      2,000,000,000  instructions
        100,000,000  cache-references
         10,000,000  cache-misses          # 10% miss rate

     0.5 seconds time elapsed

Analysis:
  IPC = instructions / cycles = 2B / 1.2B = 1.67
  (Good: 1+ is reasonable, 3+ is great)
  
  Cache miss rate = 10%
  (Bad: >2% is concerning, >5% is serious)
  
  Branch mispredict:
    $ perf stat -e branch-misses,branches ./my_program
    Prediction accuracy = (branches - branch-misses) / branches = 99%
    (Good: >98% is reasonable)
```

---

## Real Example: GPU Flight Recorder

**Your resume claim:** "GPU Flight Recorder: distributed inference profiling with sub-microsecond precision, straggler detection via clock-skew-free block-median"

**Problem:** 8 GPUs in parallel, but one straggler makes all wait.

**Profiling approach:**
1. Record GPU kernel execution time on each GPU
2. Synchronize clocks (account for clock skew between GPUs)
3. Detect outliers (which GPU is slow?)
4. Identify which kernel is slow

```python
# Simplified GPU Flight Recorder
import time
import numpy as np
from nvidia import NVML

class GPUProfiler:
    def __init__(self, num_gpus=8):
        self.num_gpus = num_gpus
        self.traces = [[] for _ in range(num_gpus)]  # per GPU
    
    def profile_kernel(self, gpu_id, kernel_name, duration_us):
        """Record kernel execution time."""
        self.traces[gpu_id].append({
            'kernel': kernel_name,
            'duration_us': duration_us,
            'timestamp': time.time_ns() / 1000  # microseconds
        })
    
    def detect_straggler(self):
        """Find which GPU is slow using block-median."""
        # Collect all kernel durations per GPU
        durations_per_gpu = [
            [t['duration_us'] for t in trace]
            for trace in self.traces
        ]
        
        # Median duration per GPU
        medians = [np.median(d) if d else 0 for d in durations_per_gpu]
        
        # Block-median: normalize across GPUs
        global_median = np.median(medians)
        
        # Find straggler
        straggler_id = None
        max_deviation = 0
        for gpu_id, median in enumerate(medians):
            deviation = (median - global_median) / global_median
            if deviation > max_deviation:
                max_deviation = deviation
                straggler_id = gpu_id
        
        if max_deviation > 0.1:  # >10% slower
            return straggler_id, max_deviation
        return None, 0
    
    def clock_skew_correct(self):
        """Adjust for clock skew between GPUs."""
        # Reference: GPU 0 clock
        ref_clock = self.traces[0][0]['timestamp']
        
        for gpu_id in range(1, self.num_gpus):
            if not self.traces[gpu_id]:
                continue
            
            # Estimate skew: difference in first timestamp
            skew = self.traces[gpu_id][0]['timestamp'] - ref_clock
            
            # Correct all timestamps on this GPU
            for trace in self.traces[gpu_id]:
                trace['timestamp'] -= skew
```

---

## TSAN: Thread Sanitizer (Data Race Detection)

```bash
# Compile with TSAN
$ g++ -fsanitize=thread -g my_program.cpp

# Run
$ ./a.out
WARNING: ThreadSanitizer: data race
  Write of size 8 at 0x7f1234 by thread T1:
    #0 increment() my_program.cpp:15
    #1 worker() my_program.cpp:25
  
  Previous write of size 8 at 0x7f1234 by thread T2:
    #0 increment() my_program.cpp:15
    #1 worker() my_program.cpp:28

Root cause: two threads writing to same variable without lock
Fix: use mutex or atomic
```

**When to use TSAN:**
- Multithreaded code with subtle bugs
- Testing, not production (10x slowdown)
- Catches races that are hard to reproduce

---

## NVIDIA GPU Profiler

```bash
# Profile GPU kernels
$ nsys profile -o output ./my_ai_program

# View results (timeline):
#   GPU 0: |compute 10ms |memory 5ms |compute 15ms |
#   GPU 1: |compute 8ms  |memory 6ms |compute 14ms | <- straggler (8+6 < 10+5)

# Identify bottleneck:
#   If compute time >> memory time: compute-bound (use more threads)
#   If memory time >> compute time: memory-bound (can't improve without better algorithm)
```

---

## Common Profiling Pitfalls

```
Mistake 1: Profiling with optimizations off
  └─ O0: code is 10x slower, profiling is wrong
  Fix: always profile release builds (O3)

Mistake 2: Profiling single run
  └─ Cold cache, page faults make first run 2-3x slower
  Fix: warm up (run twice), report second run

Mistake 3: Sampling rate too low
  └─ 100Hz sampling might miss fast functions
  Fix: use 1000Hz or higher

Mistake 4: Profiling with printf/logging
  └─ Printf adds microseconds, distorts profile
  Fix: disable logging, use internal counters

Mistake 5: Not accounting for system noise
  └─ OS jitter (context switch, interrupt) adds variance
  Fix: pin to CPU, disable turbo, use real-time priority
```

---

## Profiling Strategy (Step by Step)

```
Step 1: Baseline measurement
  Time: how long does it take?
  Throughput: requests/second?
  Latency: P50, P99?

Step 2: CPU profiling (perf)
  Which functions use most CPU?
  Top 3 are usually 80% of time

Step 3: Hardware counters (perf stat)
  Cache misses? Branch mispredicts?
  IPC (instructions per cycle)?
  
Step 4: Deep dive on hot function
  Is it algorithmic (O(n^2))?
  Memory layout (cache misses)?
  Lock contention?

Step 5: Fix and re-measure
  Confirm improvement (not guessing)
  Verify no regression in other areas
```

---

## Implementation: Python Profiler Wrapper

```python
import cProfile
import pstats
import time
from functools import wraps

def profile_function(func):
    """Decorator to profile a single function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        profiler = cProfile.Profile()
        profiler.enable()
        
        result = func(*args, **kwargs)
        
        profiler.disable()
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        stats.print_stats(10)  # top 10 functions
        
        return result
    return wrapper

@profile_function
def expensive_operation():
    """Example function to profile."""
    total = 0
    for i in range(1_000_000):
        total += i * i
    return total

# Real usage
expensive_operation()
# Output:
#   ncalls  tottime  cumtime  module:lineno(function)
#   1       0.050    0.050    expensive_operation
```

---

## Design Decisions

**Why perf over other profilers?**
- Linux-native (no overhead)
- Hardware counter support
- Flamegraph integration
- Standard tool industry-wide

**Why flamegraph visualization?**
- Easier than reading text reports
- Can quickly spot hot paths
- Shows call stacks (context)

**Why hardware counters matter?**
- Tells you WHY code is slow
- Cache miss: algorithm problem
- Branch mispredicts: CPU prediction problem
- Can guide optimization strategy

**Why TSAN for multithreaded code?**
- Data races are hard to debug (Heisenbug)
- TSAN catches them reliably
- Better to catch in testing than production

---

## Q&A

**Recall 1:** You profile your program. Top function uses 30% of CPU time. You optimize it by 50% (make it 15 faster). What's the overall speedup?

*Must-say:*
- Original: 100% time, top function is 30%
- Optimized: 70% (unchanged) + 15% (optimized) = 85%
- Speedup: 100/85 = 1.18x (only 18% faster)
- Lesson: optimize top 3 functions, not random functions

**Probe 1:** Flamegraph shows main → worker → hash_lookup is 40% of time. What does this mean?

*Expected:*
- main calls worker, worker calls hash_lookup
- 40% of total time is in hash_lookup (called from worker)
- If you optimize hash_lookup by 50%, total is 80% + 20% = 100% → 90% = 1.11x speedup

**Numeric 1:** Sample rate = 100 Hz, program runs 1 second. A function runs for 5 ms. What's the probability it's captured in profile?

*Working:*
- 100 Hz = 100 samples per second
- Function duration: 5 ms = 0.005 sec
- Probability: 5 ms * 100 samples/sec = 0.5 samples
- Only ~50% chance of being captured
- Should use 1000 Hz sampling: then 50 samples, guaranteed

---

## Questions for the Interviewer

- How do you measure latency in production? (sampling? instrumentation?)
- Have you found surprising bottlenecks? (what was it?)
- Do you use hardware counters? (how often?)
- How do you profile multi-threaded code? (TSAN? lock profiler?)
- What's your profiling overhead tolerance? (1%? 10%?)
- Do you automate profiling regression tests?

