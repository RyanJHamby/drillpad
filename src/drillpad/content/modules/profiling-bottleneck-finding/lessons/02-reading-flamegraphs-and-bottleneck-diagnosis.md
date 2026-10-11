# Reading Flamegraphs & Diagnosing Bottlenecks

## Flamegraph Basics

Interactive visualization of where CPU time goes.

```
                            [main() - 100% of wall time]
                    /              |              \
            [function_a]      [function_b]    [function_c]
            (40% of time)      (35% of time)   (25% of time)
            /         \          |      \
    [lock_acquire] [compute]  [io_wait] [serialize]
    (20%)          (20%)        (30%)     (5%)
    |                           |
  [spin]                    [network_wait]
  (20%)                       (30%)
```

**How to read:**
- **Width** = % of total time
- **Height** = call depth (stack frames)
- **Color** = typically by function name (just for visual distinction)

## Pattern 1: Wide Flat Base (CPU-Bound)

```
[main() - 100%]
    |
[loop() --------- 90%]
    |
[compute() ------- 90%]
```

**Diagnosis:** CPU is the bottleneck.

**Fixes:**
- Optimize algorithm (reduce Big-O)
- Use SIMD (vectorization)
- Parallelize (multi-threaded)
- Use faster library

## Pattern 2: Thin Tall Stack (Call Overhead)

```
[main]
  |
  [function_a] (1%)
    |
    [function_b] (1%)
      |
      [function_c] (1%)
        |
        [function_d] (1%)
```

**Diagnosis:** Deep call chains, each function small.

**Fixes:**
- Inline functions
- Reduce function calls
- Use virtual calls only when needed

## Pattern 3: Wide at Multiple Levels (Multiple Bottlenecks)

```
[main - 100%]
   /           \
[lock_acquire] [io_wait]
(30%)          (40%)
   |               |
[spin]         [network]
(30%)          (40%)
```

**Diagnosis:** Multiple bottlenecks (can't optimize just one)

**Fixes:**
- Fix the widest first (lock_acquire - 30%)
- Then fix the next (io_wait - 40%)
- Both contribute, need both fixes

## Pattern 4: I/O Wait (Kernel Time)

```
[main - 100%]
  |
  [read() or syscall] - 70% of time
      |
      [kernel: page_fault, disk_io]
```

**Diagnosis:** Thread is waiting on I/O (kernel, not your code).

**Fixes:**
- Async I/O (don't block on read)
- Batching (read multiple at once)
- Caching (avoid repeated reads)
- Prefetching (read before needed)

## Pattern 5: Lock Contention (Spinning)

```
[main - 100%]
  |
  [function_with_lock] - 50%
      |
      [mutex::lock] - 40%
           |
           [spin] - 40%
```

**Diagnosis:** Threads fighting over same lock.

**Fixes:**
- Use lock-free data structure
- Reduce lock scope (hold it less time)
- Shard the lock (one per CPU core)
- Use reader-writer lock (if mostly reads)

## Real Example: Database Query Gone Slow

### Before (Good Performance)

```
[process_request - 100ms]
  |
  [database_query - 50ms]
      |
      [network - 40ms]
      [parsing - 10ms]
  |
  [json_serialize - 30ms]
  |
  [http_response - 20ms]
```

Bottleneck: Database (50%) + Network (40%)
Acceptable.

### After (Regression)

```
[process_request - 1000ms]
  |
  [database_query - 800ms]
      |
      [network - 700ms]
      [query_execution - 100ms]
  |
  [json_serialize - 50ms]
  |
  [http_response - 150ms]
```

Bottleneck: Network (700ms) - Query is waiting on network, not executing.

**Root cause:** Query result size grew (more rows selected).
**Fix:** Add WHERE clause to filter rows, or use pagination.

## Common Bottleneck Patterns

### Pattern: Lock at Top Level

```
[main] → [lock] → [work]
```

All time spent waiting for lock.

**Fix:** Use lock-free or read-write lock.

### Pattern: GC Pause

```
[main] → [gc_pause] → [mark] → [sweep]
```

Time spent in garbage collection.

**Fix:** Tune GC (JVM), or reduce allocations (C++).

### Pattern: System Calls

```
[main] → [syscall] → [kernel]
```

Many small system calls.

**Fix:** Batch them (mmap instead of read), use async I/O.

## Reading Flamegraph in Production

### Step 1: Load the SVG

```
perf script | flamegraph.pl | > graph.svg
# Open in browser, zoomable and clickable
```

### Step 2: Find the Widest Function

Mouse over: Shows time, % of total.

```
hover over "database_query" 
→ "1.2s (35% of 3.4s total)"
```

Widest = most time.

### Step 3: Zoom In

Click on function to zoom.

See what calls it (parent) and what it calls (children).

### Step 4: Inspect the Call Stack

Look at the path from main() to the bottleneck.

```
main() → process_request() → database_query() → network_wait()
```

This is the actual call chain where time is spent.

### Step 5: Compare to Baseline

Keep a baseline flamegraph (when system was fast).

Compare new vs baseline:
- Did any function grow wider? (that's what regressed)
- Did new function appear? (that's the culprit)

## Interview Pattern: Flamegraph Diagnosis

```
Q: "Here's a flamegraph of your system at P99 latency (1000ms).
   What's wrong?"

[handed a flamegraph showing]:
  main (1000ms)
    |
    serialize_json (600ms)
      |
      base64_encode (500ms)
      |
      memory_copy (100ms)

Weak answer:
  "The system is slow, need to optimize"
  (❌ Vague, not specific)

Strong answer:
  "The bottleneck is base64_encode (500ms, 50% of total).
  
  1. Read the flamegraph:
     - serialize_json is 600ms total
     - base64_encode is 500ms of those 600ms
     - Other encoding is 100ms
     → base64 is the bottleneck
  
  2. Why is base64 slow?
     Possible causes:
     - Algorithm is O(N) where N = response size?
     - Implementation is naive (per-character encode)?
     - Copying memory unnecessarily?
  
  3. Quick fixes:
     - Use faster base64 library (SIMD, SSE4, AVX2)
     - Avoid intermediate copies (in-place encoding)
     - Reduce output size (compress before encode)
  
  4. Expected improvement:
     If switch to SIMD base64: ~3x faster (500ms → 170ms)
     Result: P99 latency 1000ms → 670ms
  
  5. Monitoring:
     - Re-profile after fix
     - Verify base64_encode drops to <170ms
     - Check P99 latency (should drop)
     - Alert if latency regresses
  
  6. Did not fix (wrong):
     - Optimize serialize_json (was only 100ms overhead)
     - Optimize memory_copy (was only 100ms overhead)
     → Wrong targets, would save only 100ms"

Why this signals good judgment:
  - You read the flamegraph correctly (found widest function)
  - You didn't optimize the wrong thing
  - You estimated improvement (3x from SIMD)
  - You'd validate with re-profiling
```

## Checklist: Diagnosing with Flamegraphs

- [ ] Find widest function (most time)
- [ ] Look at parents (why is this function called?)
- [ ] Look at children (where does it spend time?)
- [ ] Compare to baseline (what changed?)
- [ ] Fix the widest first (most impact)
- [ ] Re-profile after fix (validate improvement)
- [ ] Don't optimize the small stuff (wrong target)

## What This Signals

- You've read flamegraphs in practice
- You know which function to optimize (not guessing)
- You understand call chains and why things are slow
- You'd validate before and after (not just code review)
