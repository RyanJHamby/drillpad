# General SWE: Caching, Sharding, Replication (Scaling & Consistency)

## Firm Archetype: Meta, Google, Amazon, Microsoft

**Problem:** Scale database from 1M to 1B users while maintaining consistency and latency.

**Trade-offs:**
- Consistency vs latency (strong consistency = slow)
- Consistency vs availability (high availability = eventual consistency)
- Sharding vs replication (both needed, different purposes)

---

## Caching (Speed Up Reads)

```
Single database:
  User 1M: read from DB (100ms latency, database sees 1M queries/sec)
  
With cache:
  User 1M: read from cache (5ms latency, DB sees 10K queries/sec)
  Throughput: 100x better
  
Pattern:
  GET user:123:
    1. Check cache (Redis)
    2. If miss: query DB, store in cache (TTL 1 hour)
    3. Return
    
Invalidation:
  UPDATE user:123:
    1. Update DB
    2. Delete cache entry user:123
    3. Return
    
Gotcha: Stale reads during lag
  Write to DB (5ms), async cache delete (10ms)
  Reader hits cache before delete → sees stale data
  Solution: version numbers or timestamps
```

---

## Sharding (Horizontal Scaling)

```
Single database:
  1B users, 1 database = too slow

Sharding by user_id:
  Shard 0: users 0-249M (database A)
  Shard 1: users 250M-499M (database B)
  Shard 2: users 500M-749M (database C)
  Shard 3: users 750M-999M (database D)
  
Get user:750M:
  shard = 750M % 4 = 3 (database D)
  query database D
  
Benefit: each DB handles 250M users (1/4 load)
Problem: rebalancing (if add shard 5, remap all keys)
```

---

## Replication (Fault Tolerance)

```
Master-slave:
  Master (primary):
    - accepts writes
    - replicates to slave
    
  Slave (secondary):
    - read-only
    - lag: 100ms (eventual consistency)

Failover:
  Master dies → promote slave to master
  Detect: heartbeat timeout
  Promote: slave stops replicating, accepts writes
  Sync: other slaves sync from new master
  
Gotcha: replication lag
  Write to master (master.users[5] = "Alice")
  Client reads from slave (reads from cache, stale)
  Answer: "user 5 not found" (wrong!)
```

---

## Consistency Models

```
Strong:
  Read always sees latest write
  Write blocks until replicas confirm
  Cost: slow (wait for replication)
  
Eventual:
  Read might see stale write (lag seconds)
  Write returns immediately
  Cost: fast, but temporary inconsistency
  
Causal:
  If A writes X, then B writes Y (depending on X)
  All readers see X before Y
  Cost: medium (track causality)
```

---

## Real Example: Facebook (hypothetical)

```
Problem: 3B users, 1T messages/day

Solution:
  Shard by user_id
    - User 0 → Shard A
    - User 1B → Shard B
    - User 2B → Shard C
  
  Each shard:
    - Master in US-East
    - Replica in US-West
    - Replica in EU
  
  Cache (Redis):
    - User profiles (TTL 1 hour)
    - Message feed (TTL 5 min)
  
  Write path:
    POST /messages
    → Master (US-East) writes message
    → Replicas async sync (lag 100ms)
    → Cache invalidated
    → Return (not waiting for replicas)
  
  Read path:
    GET /feed
    → Check cache (5ms)
    → If miss: query slave (100ms, read-only)
    → Return
```

**Scaling:** 1B → 2B users
- Add shards 4-8
- Remap users (half of shard A → shard 4)
- Rebalance traffic
- Downtime: minutes to hours (during rebalancing)

---

## Design Decisions

**Why shard by user_id?**
- Distribution: users evenly distributed across shards
- Locality: user's data stays together
- Alternative: shard by region (less efficient)

**Why master-slave replication?**
- Read scalability: slaves handle reads
- Fault tolerance: slave can promote if master dies
- Alternative: peer-to-peer (more complex, multi-master conflicts)

**Why eventual consistency?**
- Speed: clients don't wait for replication
- Trade-off: stale reads (acceptable for most apps)
- If need strong: use distributed locks or version numbers

---

## Q&A

**Recall 1:** What's the difference between sharding and replication?**

*Must-say:*
- Sharding: horizontal scaling (split data across DBs)
- Replication: fault tolerance + read scaling (copy data)
- Both needed: shard for throughput, replicate for availability

**Probe 1:** You have 3 shards. User 1B hashes to shard 1. Shard 1 dies. What happens?**

*Expected:*
- Replica of shard 1 promoted to master
- Traffic rerouted to new master
- Downtime: ~1 minute (detect failure, promote, route)

**Numeric 1:** Database: 100ms latency. Cache: 5ms. Hit rate 95%. Avg latency?**

*Working:*
- 95% hit cache: 5ms
- 5% miss cache: 100ms
- Avg: 0.95 * 5 + 0.05 * 100 = 4.75 + 5 = 9.75ms
- Cache improves latency 10x (from 100ms to 10ms)

---

## Questions for the Interviewer

- How do you handle shard rebalancing? (online, offline?)
- What's your target consistency model? (strong, eventual?)
- How do you prevent data loss on replica failure? (backup, quorum?)
- What's your max shard size? (when do you split?)
