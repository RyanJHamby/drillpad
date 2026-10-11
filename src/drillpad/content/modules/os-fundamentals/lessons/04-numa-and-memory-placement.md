# NUMA & Memory Placement: Locality, Pinning, Cache Coherence Costs

## The Problem

Your machine has 2 CPU sockets, 256 GB RAM. You spawn a thread that allocates 50 GB in a loop. It's **10x slower than expected**. Why?

```
Machine layout:

CPU0 (Socket 0)    CPU1 (Socket 1)
├─ Cores 0-15     ├─ Cores 16-31
├─ L3 cache       ├─ L3 cache
└─ RAM 0-128GB    └─ RAM 128-256GB
     (local)           (local)

Thread spawned on CPU0:
  1. Allocates memory (no explicit placement)
  2. Memory comes from CPU1's side (farther)
  3. Every access: Cross QPI (inter-socket link)
  4. Latency: 40ns local → 200ns remote
  5. Throughput: 100 GB/s local → 10 GB/s remote

Result: 10x slower! Not because of algorithm, but memory locality
```

**Why this matters:** At scale, NUMA effects dominate. Algorithms that ignore NUMA are 10-100x slower than locality-aware versions. Senior SWEs on trading platforms and ML systems must understand this.

---

## First Principles: NUMA (Non-Uniform Memory Access)

Old model (Uniform Memory Access):
- Single CPU, single memory bus
- All memory accessed at same speed

Modern machine (NUMA):
- Multiple CPU sockets
- Each socket has local memory
- Accessing remote memory is expensive

**Cost breakdown:**

```
Access local memory (same socket):
  L1 hit: 4ns
  L2 hit: 12ns
  L3 hit: 40ns
  Main memory (local): 40ns

Access remote memory (different socket):
  Must go across QPI/Infinity Fabric
  Round trip: 200ns
  
Bandwidth:
  Local DDR5: 100 GB/s
  Remote (QPI): 10-20 GB/s

Rule of thumb: Remote is 5-10x slower
```

---

## NUMA Topology

```
Diagram: Dual-socket server (2 NUMA nodes)

        Socket 0                  Socket 1
      (NUMA node 0)              (NUMA node 1)
       
       ┌─────────┐               ┌─────────┐
       │ CPU0-15 │               │CPU16-31 │
       └─────────┘               └─────────┘
             │                         │
           L3$                       L3$
      (40MB)                     (40MB)
             │                         │
             └────────┬───────────────┘
                      │
              Intel QPI / AMD Infinity Fabric
              (Interconnect, 8 GB/s each direction)
                      │
      ┌───────────────┴───────────────┐
      │                               │
  ┌────────┐  0-128GB            ┌────────┐  128-256GB
  │ Local  │  (local to CPU0)    │ Local  │  (local to CPU1)
  │ RAM 0  │                      │ RAM 1  │
  └────────┘                      └────────┘
```

**Challenge:** When thread on CPU0 allocates memory, where does it come from?

- **First-touch allocation** (default): Memory allocated from the NUMA node where the thread first touches it
- **Explicit placement** (numactl): Pin memory to specific node
- **Interleaved**: Stripe memory across all nodes (uniform access but slower)

---

## First-Touch Placement

By default, memory is allocated from the NUMA node where the thread **first accesses** it:

```c
int *data = malloc(1000000 * sizeof(int));  // Just allocates, no pages mapped

for (int i = 0; i < 1000000; i++) {
    data[i] = i;  // <-- FIRST TOUCH HERE
}
```

**Timeline:**

```
malloc(): Just reserves virtual address space
  Physical memory: NOT allocated yet (lazy allocation)
  
Loop iteration 0 (touch data[0]):
  1. Thread on CPU0 accesses data[0]
  2. Page fault (page not allocated)
  3. Kernel allocates page from local memory (Socket 0)
  
Loop iterations 1-15999 (same page):
  1. Pages already allocated (local)
  2. Access is fast
  
If thread somehow migrates to CPU1:
  All subsequent accesses go remote (200ns)
```

**Diagram: First-Touch Placement**

```
Thread on CPU0:
  malloc() → virtual address range
  
  Write to offset 0 → page fault
    Kernel allocates page from NUMA 0 (local)
  
  Write to offset 4096 → different page, page fault
    Kernel allocates from NUMA 0 (local)
  
Result: All memory is local, fast

Thread migrates to CPU1 (kernel load balancing):
  Read from offset 0 → still in NUMA 0 (remote, slow)
  Read from offset 4096 → still in NUMA 0 (remote, slow)
  
  Now accessing local memory is remote!
```

---

## Memory Pinning & Affinity

Control which NUMA node thread accesses:

```c
#define _GNU_SOURCE
#include <sched.h>
#include <numa.h>

int main() {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(0, &set);  // Pin to CPU 0
    sched_setaffinity(0, sizeof(set), &set);
    
    int *data = malloc(1000000 * sizeof(int));
    
    for (int i = 0; i < 1000000; i++) {
        data[i] = i;  // Allocates from NUMA 0 (local)
    }
}
```

**Or using numactl command-line:**

```bash
# Pin to socket 0
numactl --cpunodebind=0 --localalloc ./program

# Stripe across all nodes
numactl --interleave=all ./program

# Explicit memory binding
numactl --membind=0,1 ./program
```

---

## Cache Coherence & Ping-Pong

What happens when CPU0 and CPU1 access the same memory location?

```
Scenario: Two threads updating a shared counter

Thread 0 (CPU0):        Thread 1 (CPU1):
counter++               counter++
counter++               counter++
counter++               counter++
```

**Cache coherence protocol (e.g., MESIF):**

```
State: counter = 0 in memory

t=1: CPU0 reads counter
  Load into L1 cache (CPU0)
  State: E (exclusive)
  
t=2: CPU1 reads counter
  CPU0's cache sends value to CPU1
  CPU0 state: S (shared)
  CPU1 state: S (shared)
  
t=3: CPU0 writes counter (counter++)
  Write into L1 cache (CPU0)
  CPU0 must invalidate CPU1's copy
  Sends invalidation over QPI
  CPU0 state: M (modified/exclusive)
  CPU1 state: I (invalid)
  
t=4: CPU1 reads counter
  Miss in L1
  Fetch from CPU0's L3 cache (across QPI)
  
REPEAT: This is "cache line ping-pong"
```

**Ping-Pong Cost:**

```
Counter per socket, no sharing:
  CPU0: counter_0++  (local, 40ns)
  CPU1: counter_1++  (local, 40ns)
  No synchronization
  
Shared counter (both CPUs increment):
  Each write must invalidate other's cache
  Cross-socket QPI latency: 200ns per write
  Effective bandwidth: 1 write / 200ns = 5M writes/sec
  
Single counter with lock:
  CPU0 acquires lock, increments
  CPU1 waits, acquires lock, increments
  Lock acquisition itself crosses sockets
  Latency: 200ns per acquisition
  Worst case: completely serialized
```

**Rule:** Avoid sharing memory across NUMA nodes if possible.

---

## Failure Scenario: Unexpected NUMA Effects

```
System: 2-socket, 256GB total

Developer writes algorithm:
  1. Thread 0 allocates 50GB array
  2. Spawned on CPU0
  3. First-touch: all allocated from NUMA 0
  4. Runs fast (100 GB/s local)

Developer measures: 500 seconds

Production deployment:
  Kernel load balancer migrates Thread 0 to CPU1 (30 min in)
  Suddenly all memory accesses are remote (200ns, 10 GB/s)
  Algorithm slows to 5000 seconds (10x worse!)

Detection:
  - Sudden latency spikes (CPU seems to pause)
  - Profiler shows cache misses (but CPU is not overloaded)
  - System monitor: numastat shows remote accesses

Diagnosis:
  $ numastat -c
  Shows memory allocated on NUMA 0, but accessed from NUMA 1
  
Fix:
  Option A: Pin thread to socket (sched_setaffinity)
  Option B: Replicate data on both sockets (2x memory)
  Option C: Use interleaved memory (slower but more robust)
```

---

## Interview Pattern: Performance Regression in Production

```
Q: "Your ML model inference is 10x slower in production than on your dev machine.
   Both use same hardware (dual-socket, 256GB).
   The algorithm didn't change.
   Where's the bottleneck?"

Weak answer:
  "The database is slow"
  (❌ If DB was slow, we'd see query latency spikes)
  
  Or: "Cache thrashing"
  (❌ Too vague, which cache?)

Strong answer:
  "This smells like NUMA.
  
  Hypothesis:
    Dev machine: I run single-threaded
      → Thread pinned to CPU0
      → Memory allocated locally
      → 100 GB/s throughput
    
    Production: Kernel load-balances across sockets
      → Thread starts on CPU0, allocates locally
      → Later migrates to CPU1 (kernel rebalancing)
      → All memory now remote (200ns latency, 10 GB/s)
      → 10x slowdown observed
  
  Verification:
    1. Profile: numastat -c (check memory allocation vs access)
    2. CPU affinity: taskset -c 0 ./model_inference (pin to socket 0)
    3. If pins to socket 0 and becomes fast → confirmed NUMA issue
  
  Solutions:
    A. Thread pinning: Use sched_setaffinity to pin to socket
    B. Explicit allocation: numactl --cpunodebind=0 --localalloc
    C. Replicate data: Build separate copies for each socket
    D. Interleave: Trade latency for robustness (10-20% slower but stable)
  
  I'd choose A (pinning) first:
    - Simplest
    - Lowest memory overhead
    - Keeps latency optimal
    - Document: 'Why threads are pinned'
  
  Then test: Verify latency is back to baseline after pinning"

Why this signals good judgment:
  - You understand NUMA (not just "cache is slow")
  - You have hypothesis + verification steps
  - You know multiple solutions with tradeoffs
  - You pick the right one (pinning > replication)
  - You test to confirm fix
```

---

## Checklist: NUMA-Aware Systems

- [ ] Understanding of system topology (lscpu, numactl -H)
- [ ] Explicit thread pinning for latency-critical work
- [ ] First-touch allocation verified (allocate where you use it)
- [ ] Avoid cache-line ping-pong (separate counters per socket)
- [ ] Memory bandwidth profiled (numactl --hardware)
- [ ] Latency traced (perf stat -e cache-references)
- [ ] Data replication considered if sharing unavoidable
- [ ] Documentation: why threads are pinned/allocated where

## Common Wrong Answers

1. **"NUMA only matters for huge data (TB scale)"**
   - 50 GB misaligned: 10x slowdown
   - Even modest misalignment is expensive

2. **"Just use numactl --interleave=all"**
   - Uniform access but slower (30% overhead)
   - Better: pin threads + local allocation

3. **"Kernel load balancing handles NUMA automatically"**
   - Kernel tries, but doesn't know app needs
   - Better: explicit pinning

4. **"Remote memory access is just 2-3x slower"**
   - Actually 5-10x slower (latency + bandwidth)
   - Can be 100x worse with cache coherence storms

5. **"This is only a problem at hyperscale"**
   - True at scale, but also hurts single-box performance
   - Even 2-socket systems see impact
