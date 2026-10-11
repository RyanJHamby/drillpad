# Failure Diagnosis: Resource Contention Triage (CPU vs Memory vs I/O)

## The Diagnostic Framework

**When system is slow and "something" is maxed out:**

```
Observation: System latency 500ms (normal 50ms)

What's saturated?
├─ CPU at 100% → CPU-bound (compute intensive)
├─ Memory at 95% → Memory-bound (large working set)
├─ Disk I/O 100% → I/O-bound (disk thrashing)
├─ Network 95% → Network-bound (bandwidth limit)
└─ Nothing maxed? → Waiting on lock/network request (not visible)

Treatment depends on diagnosis.
```

## CPU Contention: The Diagnosis

**Symptoms:**
- CPU utilization 90-100%
- Load average > core count
- Context switch rate high (thousands/sec)

**Diagnosis steps:**

```
1. Is it a single process or system-wide?
   - Per-process: top -p PID, see %CPU
   - System-wide: Load average / core count ratio
   
2. Which threads are burning CPU?
   - jconsole: thread list, see which threads running
   - perf: perf top (Linux) show hot functions
   - async-profiler: show call stacks of hot threads
   
3. Is it GC?
   - jstat -gccause: Full GC pauses?
   - If Full GC happening every 5 sec: HEAP FULL
   - If minor GC every 100ms: ALLOCATION RATE HIGH
   
4. Is it lock contention?
   - Thread state: Are threads BLOCKED or RUNNABLE?
   - If BLOCKED: Waiting on lock (not CPU problem, lock problem)
   - If RUNNABLE: Actually running (CPU problem)
```

**Common cases:**

```
Case 1: CPU 100%, GC every 5 sec
  → Heap full, increase -Xmx
  
Case 2: CPU 100%, high allocation rate
  → Reduce object creation (object pooling)
  
Case 3: CPU 60%, threads BLOCKED
  → Lock contention (not CPU problem, lock problem)
  
Case 4: CPU 50%, high context switches
  → Too many threads (reduce thread count)
```

## Memory Contention: The Diagnosis

**Symptoms:**
- Heap 95%+ utilized
- Frequent full GC pauses (>100ms)
- OOM errors appearing

**Diagnosis steps:**

```
1. Is it a memory leak?
   - Heap dump: Compare before/after
   - Object histogram: Which class is large?
   - Check: Are old objects being retained?
   
2. Is working set just large?
   - Heap dump analysis: What's in memory?
   - Cache size: Is cache too big?
   - Query results: Are we caching 1M objects?
   
3. Can we reduce memory per request?
   - Stream instead of load all (memory optimization)
   - Cache cleanup: Remove expired entries
   - Object pooling: Reuse objects instead of creating
```

**Quick decision tree:**

```
Heap usage 95%?
├─ Growing over time? → Memory leak
│  └─ Heap dump: What object is growing?
├─ Stable at 95%? → Working set is just large
│  └─ Is it necessary? (cache size, config)
└─ Spikes to 95% then drops? → GC pressure
   └─ Increase heap size
```

**Interview answer:**

```
Q: "System memory is at 95%, GC pausing for 200ms every 30 sec. Fix?"

"Quick checks:
  1. Is it a memory leak?
     - Heap dump after running for 1 hour
     - Object histogram: What's retained?
     - If objects aren't being freed: Leak confirmed
     
  2. Is it working set just large?
     - 95% heap utilization with stable growth: Expected
     - Cache size: Do we need 256GB cache?
     
Fix options (priority order):
  1. Increase heap (-Xmx): +30min deploy, +50% throughput
     Cost: More memory per server
     
  2. Fix memory leak: +1 day development
     But permanent fix
     
  3. Use G1GC/ZGC: Lower pause times
     Cost: 2 hours tuning + testing
     
I'd do #1 immediately (buy time), then #2 (root cause)"
```

## I/O Contention: The Diagnosis

**Symptoms:**
- Disk utilization 100%
- Disk queue depth > 4 (per disk)
- `iostat` shows high %iowait

**Diagnosis steps:**

```
1. What's causing I/O?
   - strace -p PID: Which file is being accessed?
   - lsof -p PID: Open file handles
   - iotop: Which process is doing I/O?
   
2. Is it sequential or random?
   - iostat -x 1: Sequential I/O? (large reads)
   - Random I/O? (many small seeks)
   - Sequential: Streaming access (better)
   - Random: Database queries (worse)
   
3. Can we reduce I/O?
   - Add page cache (mmap file)
   - Database index (random → index lookup)
   - Caching layer (Redis for hot data)
```

**Common cases:**

```
Case 1: Large sequential I/O (database bulk load)
  - Acceptable (streaming speed)
  - Solution: Wait or parallelize reads
  
Case 2: Random I/O (database queries, no index)
  - Not acceptable (expensive)
  - Solution: Add index or cache
  
Case 3: Disk full (OOM from disk perspective)
  - Immediate: Delete files
  - Long-term: Add storage or cleanup
```

## Combined: CPU + Memory + I/O Contention

**Real example: Trading system load spike**

```
Symptom: Latency 50ms → 500ms during market open

Checks (order of likelihood):
  1. CPU: 100%, load = 2x cores → Compute bottleneck
     Check: GC every 3 sec (Full GC pause 200ms)
     Root cause: Heap at 95%, Java allocating heavily
     Fix: Increase heap -Xmx from 128GB to 256GB (+5 min)
     
  2. Memory: Still 95% even after step 1?
     Check: Heap dump, find what's allocated
     Root cause: Order book growing (1M orders in memory)
     Fix: Archive old orders to DB (1 day)
     
  3. I/O: Disk queue building up?
     Check: Database is now bottleneck (queries slow)
     Root cause: Too many order lookups hitting disk
     Fix: Add index on (symbol, price) (2 hours)
     
Results:
  - Immediate: Increase heap (50% improvement)
  - 1 day: Archive orders (another 30% improvement)
  - 2 days: Add index (another 10% improvement)
  - Total: 100ms → 50ms latency restored
```

## Interview Pattern: Triage Under Pressure

**Q: "Multiple things are maxed out: CPU 90%, Disk 100%, Memory 85%. Where do you start?"**

Weak answer:
```
"Uh, optimize everything? Fix the GC? Add more disk space?"
(❌ Scattered, no prioritization, no diagnosis)
```

Strong answer:
```
"Prioritize by impact:

1. CPU 90% + Disk 100% = likely CPU waiting on I/O
   Check: iostat, see if disk queue > 4
   If yes: I/O is bottleneck (CPU waiting for disk)
   
2. What's causing disk I/O?
   - iotop: Process consuming disk?
   - strace: Which file operations?
   
3. Fix I/O first:
   - Add index to slow query?
   - Increase page cache?
   - Add more disks (parallel I/O)?
   
4. Then recheck CPU:
   - Once I/O improves, CPU will be less busy
   - Memory 85% is acceptable (no action needed)

Root cause: I/O bottleneck masked by CPU waiting.
Fix I/O → CPU naturally drops.
"
```

## Triage Checklist

**When resource maxed out:**

```
CPU 100%:
- [ ] Is it GC? (check GC logs)
- [ ] Is it algorithm? (async-profiler)
- [ ] Is it lock contention? (thread state)

Memory 95%:
- [ ] Memory leak? (heap dump trend)
- [ ] Working set just large? (acceptable)
- [ ] Can we reduce? (pooling, cleanup)

Disk 100%:
- [ ] What process? (iotop)
- [ ] Sequential or random? (iostat)
- [ ] Can we cache? (add Redis)

Network 95%:
- [ ] Is it latency or bandwidth?
- [ ] Packet loss? (tcpdump)
- [ ] Can we compress? (reduce payload)
```

