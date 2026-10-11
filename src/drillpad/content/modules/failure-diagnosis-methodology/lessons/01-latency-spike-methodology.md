# Failure Diagnosis: Latency Spike Root Cause Methodology

## The Interview Scenario

```
Interviewer: "Your system's P99 latency just spiked from 50ms to 500ms.
You have 5 minutes to diagnose. What do you check?"

Bad approach:
  - Ramble about possibilities
  - Hope luck guides you
  - Miss the real issue

Good approach:
  - Systematic decision tree
  - Check most likely first
  - Eliminate by evidence
```

## The Decision Tree: 5-Minute Diagnosis

```
Start: Latency spike detected

1. Is it a code change?
   └─ When did spike start?
      - During deployment? → Check code change
      - 5 min ago, no deployment? → Skip code, check resource

2. Check: CPU utilization
   └─ High (>90%)?
      ├─ Yes → CPU-bound issue (GC? Lock contention? Slow algorithm?)
      └─ No → Not CPU-bound, check next

3. Check: Memory
   └─ Heap size >85%?
      ├─ Yes → Full GC starting, check GC logs
      ├─ No → Memory not issue, check next
      
4. Check: Network latency (ping to upstream)
   └─ Latency >50ms?
      ├─ Yes → Network partition or loss, check packet loss
      └─ No → Network not issue, check locks

5. Check: Lock contention (ThreadState in profiler)
   └─ Threads waiting on BLOCKED state >20%?
      ├─ Yes → Lock contention, check which lock
      └─ No → Something else

6. Check: Queue depth
   └─ Inbound queue > 1000 items?
      ├─ Yes → Cascading backpressure, check processing rate
      └─ No → Check disk I/O
```

## Common Root Causes & Diagnosis

### Root Cause 1: Garbage Collection (GC)

**Signal: CPU spike to 100%, latency 50ms → 500ms**

```
Diagnosis (check in order):
  1. GC log: "Full GC paused for 400ms"
  2. Heap utilization: 90%+
  3. Minor collections happening every 100ms
  4. No code change, no traffic spike
  
Confirmation: JVM stop-the-world pause correlates with latency spike

Cause: Heap full, running full GC every few seconds
       Each full GC stops world for 400ms
       
Fix options (in order):
  1. Increase heap size (immediate, 15min deploy)
  2. Reduce object allocation (code change, 1hr)
  3. Use low-latency GC (G1GC, ZGC, 2hr change + testing)
```

**Interview answer:**
```
Q: "P99 latency spiked, no code change. What is it?"

"First check: CPU at 100%?
  If yes: Likely GC

What I'd do:
  1. Check GC logs: grep 'Full GC' last 5 min (2 sec)
  2. If Full GC happening every 5 sec: Heap too small
  3. Increase heap (-Xmx) and redeploy (quick win)
  
Then debug deeper:
  - Is allocation rate high? (jstat -gccause)
  - Which objects are growing? (heap dump)
  - Long-lived objects leaking?
  
Mitigation: Set heap alert when >85%, page oncall"
```

### Root Cause 2: Lock Contention

**Signal: CPU 60%, high BLOCKED threads, latency spike with traffic spike**

```
Diagnosis:
  1. Check: threadcpu top command (Linux)
     - Thread 1: 20% CPU (not maxed, waiting for lock)
     - Thread 2: 20% CPU (not maxed, waiting for lock)
     - Thread 3: 20% CPU (not maxed, waiting for lock)
     - Result: CPU should be 60%+, but lots of waiting
     
  2. Profiler: jconsole or async-profiler
     - Method A (Lock holder): 60% of samples
     - BLOCKED (Lock waiters): 30% of samples (stuck waiting)
     
  3. Thread state: TState = BLOCKED for 50% of threads

Cause: Lock holder is slow, everyone waiting

Example (common):
  Lock: shared HashMap<String, Object>
  Holder: updating HashMap (slow, triggers resize)
  Waiters: 100 threads waiting for lock
  Result: Only 1 thread making progress, P99 = 100ms latency
```

**Interview answer:**
```
Q: "Latency spiked during traffic surge. High CPU, but not maxed out?"

"Sounds like lock contention.

Diagnosis:
  1. Async-profiler: see if threads are BLOCKED (waiting on lock)
  2. Check: Which lock? (Thread dump shows waiting on <class Monitor>)
  3. Example: ConcurrentHashMap under high contention
  
Fix options:
  1. Remove the lock (use lock-free data structure)
  2. Reduce lock scope (split into multiple locks, partition)
  3. Use read-write lock (if mostly reads)
  4. Use StampedLock (faster than ReentrantLock)
  
Quick fix: Partition the map (10 locks instead of 1)
  - hashcode % 10 determines which lock to acquire
  - 10x fewer waiters per lock
  - Deploy in 20 min"
```

### Root Cause 3: Network Latency

**Signal: Latency spike, no CPU spike, no memory issue**

```
Diagnosis:
  1. Check: Ping to upstream service
     - Normal: 5ms
     - Spiked: 50ms+
     
  2. Check: Packet loss
     - tcpdump: packets being retransmitted?
     - netstat -s: packet loss rate > 0.1%?
     
  3. Check: Network path
     - Traceroute: which hop is slow?
     - Switch congestion? ISP issue? Firewall?

Cause: Network degradation (temporary)

Example:
  - 50ms spike: 10x network latency increase
  - Other services affected? (yes → network problem)
  - Only one service affected? (no → service issue)
```

**Interview answer:**
```
Q: "P99 latency spiked to 500ms, no code change, CPU low. What?"

"Network degradation suspected.

Checks:
  1. Are OTHER services slow? (yes → network, no → our code)
  2. Ping upstream: 5ms → 50ms? (yes → network)
  3. Packet loss? (tcpdump | grep retrans)
  
If confirmed network:
  - Transient (will recover): Monitor
  - Persistent: Escalate to network team
  
If not network:
  - Check DNS resolution (DNS TTL expired? Cache miss?)
  - Check connection pool (running out of sockets?)
  - Check timeout settings (hanging requests?)"
```

### Root Cause 4: Slow Query / Database Bottleneck

**Signal: Latency spike, but latency is in downstream (DB latency increases)**

```
Diagnosis:
  1. Check: Slow query log
     - SELECT * FROM users WHERE status = 'active' (no index!)
     - Was 5ms (cached result), now 500ms (full scan)
     
  2. What changed?
     - Table grew from 1M rows to 100M rows
     - Old cache entries expired
     - Query plan changed (optimizer chose different index)
     
  3. Check: Index fragmentation
     - EXPLAIN PLAN: full table scan vs index scan

Cause: Data growth, cache miss, missing index

Example:
  - 1 week ago: 1M users, query hits index, 5ms
  - 1 day ago: 100M users, query full scan, 500ms
  - No one noticed until traffic spiked and overwhelmed connection pool
```

**Interview answer:**
```
Q: "P99 latency 50ms → 500ms. DB response times increased. Why?"

"DB bottleneck is likely.

Checks:
  1. Slow query log: Any new slow queries?
  2. Has data size changed? (1M rows → 10M rows)
  3. Index stats: EXPLAIN PLAN shows full scan?
  4. Connection pool: Are we exhausting connections?
  
If data size grew:
  - Old index insufficient
  - Need to add index on WHERE clause
  - Or partition table (shard by user_id)
  
If query plan changed:
  - Collect stats: ANALYZE TABLE (PostgreSQL)
  - Revert optimizer change
  - Add hint to force index
  
Immediate fix: Restart DB (clears cache)
Long-term fix: Add index or shard table"
```

## Template: 5-Min Diagnosis Checklist

**When latency spikes:**

```
Time 0:00-0:30 — Gather Facts
- [ ] When did it spike? (deployment? traffic spike?)
- [ ] What's the scope? (one service? all services? one user?)
- [ ] CPU, memory, network status

Time 0:30-1:30 — CPU-bound or I/O-bound?
- [ ] CPU: Is it pegged at 100%? Or waiting?
      100% → GC or CPU-bound algorithm
      <80% → Likely waiting (lock, I/O, network)

Time 1:30-2:30 — If CPU Bound
- [ ] GC logs: Full GC happening?
- [ ] Profiler: Where is CPU going? (which method?)
- [ ] Algorithm: Is code slow, or load high?

Time 2:30-3:30 — If I/O Bound
- [ ] Locks: Threads BLOCKED on Monitor?
- [ ] Network: Ping to upstream service
- [ ] Disk: I/O latency high?
- [ ] DB: Slow queries in log?

Time 3:30-4:00 — Prioritize Fixes
- [ ] Quick win: Restart service, clear cache?
- [ ] Immediate: Scale horizontally (add servers)?
- [ ] Long-term: Code change (1hr-1day)?
```

## Interview Red Flags vs Green Flags

**🚩 Red flags (you're guessing):**
1. "It could be X or Y or Z" (no systematic approach)
2. No mention of where CPU/memory is (didn't check)
3. Assuming network without checking ping
4. Only checking logs, not running profiler

**✅ Green flags (you're systematic):**
1. "CPU at 100%, I check GC logs immediately"
2. Named specific tools (jconsole, async-profiler, tcpdump)
3. Showed decision tree (if X then check Y)
4. Prioritized common causes (GC, lock contention, network)
5. Named mitigation (restart, scale, code fix)

