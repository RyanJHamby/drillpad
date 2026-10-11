# Design Judgment: Scaling Decision Tree (Vertical vs Horizontal)

## The Core Question

**When you hit a bottleneck:**
- **Vertical scaling:** Bigger server (more CPU/RAM)
- **Horizontal scaling:** More servers (sharding, replication)

One is cheap & simple. The other is mandatory at scale. But which *first*?

```
Server cost: $1000/month (dual-socket, 256GB RAM)
vs
Engineering: 2 weeks to implement sharding

Wrong choice early = waste $100k on servers
Wrong choice late = crisis refactoring at 3am
```

## Decision Framework: The Scaling Curve

```
Load (QPS)
  |                    /--- Horizontal (many servers)
  |                   /
  |                  /
  |     ___________/
  |    /            
  |   /--- Vertical (bigger server)
  |  /
  |_/________________
  0   10  100  1000  QPS
  
Key insight: Vertical works until it doesn't. Then only horizontal works.
```

## When Vertical Scaling Works (Cheap)

### Single-Machine Bottlenecks (Latency-Bound)

**Trading order book (10k orders/sec):**
```
Server specs: 
  - 32 cores, 256GB RAM
  - Throughput: 10k orders/sec
  - Latency: 50µs P99.9

Is it maxed?
  - CPU: 40% (lock-free, not contention-bound)
  - Memory: 30% (order book fits)
  - Network: 20% (not IO-bound)

Option 1 (Vertical): Upgrade to 64 cores, 512GB
  - Same latency (code doesn't change)
  - 1.5-2x throughput (more parallelism)
  - Cost: $500/month more
  - Time: 1 hour to upgrade
  
Option 2 (Horizontal): Shard orders by symbol
  - Rewrite matching engine logic (2 weeks)
  - Add sharding router (1 week)
  - Coordinate across shards (1 week, hard)
  - Total: 1 month engineering
  
Decision: VERTICAL (latency critical, can get 2x throughput for $500)
```

**Why vertical works:**
- Lock-free code scales well to more cores
- No network latency added
- P99.9 doesn't change

### Cache-Bound Workloads

**LRU cache (1M requests/sec):**
```
Server: 256GB RAM, 80% used
Cache hit rate: 95%
Bottleneck: Cache memory

Option 1 (Vertical): Upgrade to 512GB RAM ($1000/month)
  - Hit rate: 98% (bigger cache)
  - Memory: 85% used
  - Throughput: 1.5M requests/sec (more hits)
  - Time: 1 day
  
Option 2 (Horizontal): Shard cache by key
  - Each server: 256GB, different key ranges
  - Hit rate: 95% per server (distributed)
  - Complexity: cache coordination, invalidation
  - Time: 3 weeks
  
Decision: VERTICAL (cheaper, simpler, faster)
```

**Why vertical works:**
- Bigger cache = better hit rate (no added latency)
- No network latency for hot data
- No coordination overhead

## When Vertical Scaling Breaks (Must Go Horizontal)

### Compute-Bound Bottlenecks

**Inference (batch size tuning):**
```
GPU: H100 (141 TFLOPS)
Current throughput: 100 QPS
Batch size: 4 (memory-limited)

Can we increase batch?
  - Batch 8: 160GB KV-cache (H100 has 141GB, doesn't fit)
  
Option 1 (Vertical): H100 → Grace H200 (980GB)
  - Cost: $50k per GPU (vs $40k H100)
  - Only 1.2x faster (memory-bandwidth limited now)
  - ROI: Terrible
  
Option 2 (Horizontal): Add 2 more H100s
  - Batch 4 on each GPU = 3 GPUs × 100 QPS = 300 QPS
  - Cost: $120k for 3 GPUs vs $150k for H200
  - Faster, cheaper, same latency
  
Decision: HORIZONTAL (vertical doesn't scale well here)
```

**Why vertical breaks:**
- GPU memory is the constraint (can't add more to one GPU)
- Vertical scaling: 980GB (1.2x speed, 10x cost)
- Horizontal scaling: 3 × 141GB (3x speed, 3x cost)

### Throughput-Bound Bottlenecks

**Payment processing (DB-bound):**
```
DB: PostgreSQL on 256GB server
Current: 10k TPS, 95% CPU
Bottleneck: CPU (processing SQL, not data)

Option 1 (Vertical): 256GB → 512GB server
  - CPU: Still 95% (same workload per core)
  - RAM helped nothing (data already in buffer pool)
  - TPS: Still 10k
  - Wasted $1000/month
  
Option 2 (Horizontal): Shard by user_id
  - 5 servers, each 2k TPS
  - Each server: 50% CPU (headroom)
  - Total: 10k TPS with scaling capacity
  - Cost: Same as 1 server, but 5x capacity
  
Decision: HORIZONTAL (vertical doesn't help, horizontal gives 5x headroom)
```

**Why vertical breaks:**
- More RAM doesn't add CPU cores
- Hitting single-core limits (Amdahl's law)
- Bottleneck isn't memory, it's CPU

## The Real-World Decision Tree

```
Step 1: What's saturated?
  ├─ CPU: 95%
  │  └─ Is it lock contention (threads fighting)?
  │     ├─ Yes → Fix the lock (code change)
  │     └─ No → Check if job is parallelizable
  │           ├─ Yes (SIMD, vectorization) → Vertical
  │           └─ No (single-threaded algorithm) → Horizontal + recode
  │
  ├─ Memory: 95%
  │  ├─ Is it caching/working set?
  │  │  ├─ Yes → Vertical (bigger RAM improves hit rate)
  │  │  └─ No → Horizontal (shard the data)
  │  │
  │  └─ Can you reduce memory per request?
  │     ├─ Yes → Optimize (code change)
  │     └─ No → Horizontal
  │
  └─ Network: 95%
     ├─ Outbound bandwidth? → Horizontal (more servers = more total BW)
     └─ Latency? → Vertical (move closer, can't scale latency)

Step 2: Can your code scale to more cores?
  ├─ Lock-free? → Vertical (add cores)
  ├─ Mutexes? → Horizontal (avoid contention)
  └─ Single-threaded? → Horizontal (can't use vertical cores)

Step 3: Do you need strong consistency?
  ├─ Yes → Vertical preferred (single machine = easier consistency)
  └─ No → Horizontal (easier to scale)
```

## Firm-Specific Scaling Approaches

### Trading: Vertical Then Horizontal (Rarely)

**Reason: Latency is sacred**

```
Phase 1: Vertical scaling (up to 64 cores, 512GB)
  - Keep single-server consistency (no network latency)
  - Latency: 50µs (unchanged)
  
Phase 2: If still not enough, shard by symbol
  - Symbols routed to dedicated servers
  - Trade complexity for capacity
  - Latency: 50µs (same, local matching engine)
```

**Interview answer:**
```
Q: "You need to support 100k orders/sec, but current system does 10k. How?"

"Current system is single-server, lock-free, 64 cores, 512GB.
 At 100k/sec, we'd hit ~90% CPU.

Step 1: Vertical (32→64 cores, if available): +50% throughput
Step 2: Code optimization (lock-free queue → array): +30% throughput
Step 3: CPU affinity + NUMA awareness: +20% throughput

If still short: Shard by symbol (100 symbols = 100 servers)
  Each server: 1k orders/sec, latency unchanged"
```

### AI Infra: Horizontal (Always)

**Reason: Can't buy a single GPU that's fast enough**

```
Inference: 1000 concurrent requests

Option 1: 1 GPU
  - Can't fit all requests (OOM)
  - Forced to horizontal
  
Option 2: Many GPUs
  - Each takes batch of requests
  - Parallel processing
  - Natural horizontal scaling
```

**Interview answer:**
```
Q: "How do you scale inference from 100 to 1000 concurrent requests?"

"100 requests: Batch 32, 3 batches in parallel = 96 requests
 1000 requests: Need ~10 GPUs

Design:
  1. Load balancer routes request to least-loaded GPU
  2. Each GPU batches 32 requests
  3. Throughput: 10 GPUs × 100 QPS = 1000 concurrent
  
 Cost per request: $0.01 (shared GPU cost)"
```

### AWS: Horizontal from the Start

**Reason: Elasticity is the feature**

```
Payment processing:

Day 1: 1k TPS → 1 server
Day 30: 10k TPS → 10 servers
Day 90: 100k TPS → 100 servers

No vertical scaling bottleneck (auto-shard as you grow)
```

**Interview answer:**
```
Q: "How does your system handle 10x growth in traffic?"

"Stateless payment processor (can replicate infinitely).
 
 Design:
  1. Payment request → Queue (SQS, Kafka)
  2. Auto-scaling: Add processor when queue > threshold
  3. Each processor: independent (no coordination)
  
 Scaling: Linear (1 server = 1k TPS, N servers = N×1k TPS)
 Cost: Predictable, proportional to traffic"
```

## Quick Decision Checklist

**Before scaling, ask:**

- [ ] What's actually saturated? (CPU? Memory? Network? Latency?)
- [ ] Can vertical help? (more CPU, more RAM, bigger server?)
- [ ] Is the code parallelizable? (lock-free? thread-safe? SIMD?)
- [ ] How much capacity do I need? (1.5x or 10x?)
- [ ] What's the consistency requirement? (single-machine or distributed?)

**Red flags vertical won't help:**
- Network latency is bottleneck (add more servers)
- CPU is 100% and code is single-threaded (rewrite or shard)
- Memory is full and you can't reduce working set (shard the data)

**Green flags horizontal is needed:**
- Latency needs to stay low (can't go cross-datacenter)
- Consistency is soft (can eventually replicate)
- Throughput needs to scale 10x+ (one server never enough)

