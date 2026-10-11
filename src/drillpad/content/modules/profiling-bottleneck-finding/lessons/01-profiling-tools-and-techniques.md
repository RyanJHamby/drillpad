# Profiling Tools & Techniques - perf, vtune, py-spy, Flamegraph

## The Profiling Problem

Your system takes 1000ms to respond. Where does it go?

- 500ms in database?
- 400ms in CPU?
- 100ms in network?

Guessing = wasted time. Profiling = measurable.

## Tool 1: Linux `perf` (C++, Go, Rust)

CPU profiling with stack sampling.

```bash
# Profile for 10 seconds
perf record -F 99 -g -p <pid> sleep 10
perf report

# Output shows:
#    50.0% function_a()
#    30.0% function_b()
#    20.0% function_c()
```

**How it works:**
- Samples call stack every 10ms (at 99Hz)
- Shows which functions are burning CPU time
- Overhead: ~2-3% (low, can run in production)

**Cost:**
- Free (built-in Linux)

**When to use:**
- C++, Go, Rust code
- CPU bottleneck suspected
- "Why is latency high?"

**Pitfall:** Doesn't show I/O wait time (disk, network)

## Tool 2: Intel VTune (C++, Rust)

More detailed CPU profiling + memory + I/O.

```bash
vtune -collect hotspots -data-limit=500M -app ./my_app
vtune -report hotspots -r <result_dir>

# Output:
# Function                 % CPU Time   LLC Misses
# lock_free_queue::push()  35%          40%
# database_query()         25%          10%
```

Shows:
- CPU time per function
- Cache misses (L1, L2, L3, LLC)
- Memory bandwidth used
- Instruction count

**Cost:**
- Paid Intel product (~$500/year)
- Or free: limited version

**When to use:**
- Cache misses suspected
- Hardware counter analysis needed
- "Why is my CPU efficient but slow?"

**Better for:** Trading, latency-critical systems

## Tool 3: Python `py-spy` & flamegraph

Lightweight Python profiler.

```bash
# Record Python program
py-spy record -o profile.svg -- python my_script.py

# Output: flamegraph.svg (visual, zoomable)
```

Shows:
- Which functions call which
- Time spent in each
- Zooms in on bottleneck

**Cost:**
- Free, open source

**When to use:**
- Python code
- Want visual output
- "Where are the hot spots?"

**Advantage:** Very low overhead, can run on production

## Tool 4: Flamegraph (Universal)

Output format (not a tool), works with perf, vtune, py-spy.

```
Layout:
  [main()                                           ] 100%
    [function_a()          ] [function_b()    ] [c()] 
      [lock_acquire()...] [computation()...]
```

Reading:
- Width = % time spent
- Taller stack = deeper call chain
- Look for wide functions (these are bottlenecks)

**Interaction:**
- Click to zoom in
- See what calls what

## Production Profiling: Safety First

### Issue 1: Overhead

```
Sampling-based (perf, py-spy): 2-3% overhead (safe)
Instrumentation (VTune full mode): 10-50% overhead (risky, slow system)

In production: Use sampling only
```

### Issue 2: Statistical Significance

```
Single 10-second sample might miss infrequent slow paths

Better:
  - Profile for 60 seconds (or 10M samples)
  - Profile multiple times (same code, different data?)
  - Watch for variance (is bottleneck consistent?)
```

### Issue 3: Load Dependency

```
Bottleneck at 100 req/sec might be different at 10,000 req/sec

Better:
  - Profile at realistic load
  - Note the load when profiling (req/sec, QPS, etc.)
```

## Example: Finding the Bottleneck

### Problem: API latency P99 = 1000ms

```bash
# Profile under load
perf record -F 99 -g -p <pid> sleep 60
perf report

Output:
  55% database_query()
  20% json_serialization()
  15% lock_acquire()
  10% network_wait()
```

**Diagnosis:**
- Database is 55% → This is the bottleneck
- json_serialization adds 20%
- Locking contention adds 15%

**Fix priority:**
1. Optimize database (most impact)
2. Then optimize JSON
3. Then reduce lock contention

## Comparison Table

| Tool | Language | Cost | Overhead | Best For |
|---|---|---|---|---|
| **perf** | C++/Go/Rust | Free | 2% | CPU bottleneck |
| **VTune** | C++/Rust | Paid | 5-50% | Cache/memory analysis |
| **py-spy** | Python | Free | 2% | Python bottleneck |
| **Java Flight Recorder** | Java | Free (JDK11+) | 2% | Java bottleneck |
| **go pprof** | Go | Free | 2% | Go profiling |

## Interview Pattern: Profiling Under Pressure

```
Q: "Your P99 latency went from 100ms to 500ms overnight.
   How do you debug?"

Weak answer:
  "Check CPU and memory metrics"
  (❌ Metrics don't show which function is slow)

Strong answer:
  "Use profiling to find bottleneck:
  
  1. Immediate (next 5 minutes):
     - Is it a regression? (Compare perf profiles: now vs last week)
     - Is it load-dependent? (Check QPS, then profile at same load)
  
  2. Profiling approach:
     - Deploy perf recording to production
     - Sample for 60 seconds at realistic load
     - Analyze: which function changed?
  
  3. Read the flamegraph:
     - Which function is widest? (uses most time)
     - Did it grow? (was 10%, now 30%)
     - Why?
  
  4. Examples and fixes:
     Example 1: Database query now 80% (was 40%)
       Cause: Schema change, index dropped?
       Fix: Restore index, re-run perf to verify
     
     Example 2: JSON serialization now 40% (was 10%)
       Cause: Response got bigger? Added fields?
       Fix: Compress, or filter fields
     
     Example 3: Lock contention now 50% (was 5%)
       Cause: Burst traffic, lock bottleneck exposed
       Fix: Use lock-free structure or reduce lock scope
  
  5. Validation:
     - Perf profile after fix (should return to baseline)
     - Monitor latency (P99 should drop)
     - Set alert: 'If P99 > 200ms for 5min, investigate'
  
  6. Prevention:
     - Add continuous profiling (weekly baseline)
     - Alert if function's time increases 2x
     - Include perf in deployment checklist"

Why this signals good judgment:
  - You used profiling, not guessing
  - You understood load matters (profile at realistic load)
  - You read the flamegraph (found the bottleneck)
  - You validated the fix (re-profiled)
  - You'd set up monitoring to catch it next time
```

## Checklist: Profiling in Production

- [ ] Use sampling-based profiling (overhead < 5%)
- [ ] Profile for 60+ seconds (statistical significance)
- [ ] Profile at realistic load (note req/sec)
- [ ] Save baseline profile (compare before/after)
- [ ] Look for changed functions (what grew?)
- [ ] Validate fix with re-profiling
- [ ] Set monitoring alert for regression

## What This Signals

- You've debugged production latency
- You know the tools (perf, VTune, py-spy)
- You understand overhead matters
- You validate with re-profiling (not just code review)
