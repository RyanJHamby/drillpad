# Sharding Patterns: How to Split a Database

## Overview

When a single database is too slow/big, you shard (split) it. This lesson covers:
1. Why sharding is necessary (scale limits)
2. Sharding strategies (range, hash, directory-based)
3. Hot shards and rebalancing
4. Sharding trade-offs

---

## The Problem: Single Database Limit

One database server can handle:
- ~10,000 QPS (queries per second)
- ~1-2 TB of data (reasonable working set)

Beyond that, you need multiple databases.

```
Users table: 100M users
Size: 10 GB (100 bytes per user)
Traffic: 50,000 QPS

Single DB: Timeout (can't handle 50k QPS)
Solution: Split into multiple DBs
```

---

## Strategy 1: Range-Based Sharding

Divide by a range (e.g., user_id).

```
Shard 0: user_id 0 - 1,000,000
Shard 1: user_id 1,000,001 - 2,000,000
Shard 2: user_id 2,000,001 - 3,000,000
...

Query: Find user 1,500,000
  shard_id = 1 (in range 1M-2M)
  Query shard_1
  Cost: 1 database lookup
```

**Advantages:**
- Simple (obvious how to split)
- Supports range queries

**Disadvantages:**
- Range boundaries might not match real data (user 0-1M might be 90% of traffic)
- Rebalancing is hard (moving data between shards)

---

## Strategy 2: Hash-Based Sharding

Use a hash function to assign to shards.

```
Shard ID = hash(user_id) % num_shards

Query: Find user 12345
  shard_id = hash(12345) % 3 = 1
  Query shard_1
  Cost: 1 database lookup

Insert: user_id = 999999
  shard_id = hash(999999) % 3 = 0
  Insert into shard_0
```

**Advantages:**
- Data distributed evenly (hash function randomizes)
- Predictable (same key always goes to same shard)

**Disadvantages:**
- Range queries impossible (hash(100) and hash(101) are unrelated)
- Rebalancing requires rehashing everything (add a shard, rehash 1/4 of data)

---

## Strategy 3: Directory-Based Sharding

Keep a lookup table (directory) that maps keys to shards.

```
Directory:
  user_id → shard_id
  
  1 → shard_0
  2 → shard_3
  3 → shard_1
  ...

Query: Find user 1
  Look up in directory: user 1 → shard_0
  Query shard_0
  Cost: 2 lookups (directory + shard)
```

**Advantages:**
- Flexible (directory can be arbitrary)
- Rebalancing is easy (change directory entry)

**Disadvantages:**
- Directory is a single point of failure (cache it)
- Extra lookup adds latency

---

## The Hot Shard Problem

If one shard gets more traffic, it becomes a bottleneck:

```
100M users, 3 shards
  Shard 0: 1-33M (10k QPS)
  Shard 1: 33-66M (10k QPS)
  Shard 2: 66-100M (30k QPS) ← HOT SHARD

Shard 2 is 3x overloaded → timeouts
```

**Solution 1: Reshard (split shard 2)**

```
  Shard 2a: 66-83M (15k QPS)
  Shard 2b: 83-100M (15k QPS)
```

Cost: Downtime, data migration, client changes.

**Solution 2: Replica shard (read replicas)**

```
  Shard 2 (primary): writes
  Shard 2-replica: reads
  
Distribute reads across replicas.
Cost: Higher latency for writes (replicate), complexity.
```

**Solution 3: Caching (memcached, Redis)**

```
Client → Cache → Shard

Hot users are cached, shard only handles misses.
Cost: Cache invalidation complexity, stale reads.
```

---

## Rebalancing: The Hard Part

When you shard, eventually you need to rebalance (move data between shards).

```
Current: 3 shards
Future: 5 shards (add 2 more)

Hash-based: hash(key) % 5 changes mapping
  Old: user 1 → hash(1) % 3 = 2
  New: user 1 → hash(1) % 5 = 1
  Result: Must move user 1 from shard 2 to shard 1

Consistent hashing (workaround):
  Instead of % num_shards, use a hash ring
  Adding a shard only requires moving ~1/(num_shards) of data
  Trade-off: Complex to implement, not all databases support it
```

---

## Shard Key Selection

Choose carefully — you can't change this easily later.

**Good shard keys:**
- User ID (mostly unique, evenly distributed)
- Company ID (business entity, good for multi-tenancy)

**Bad shard keys:**
- Country (uneven: USA 50%, others 50%)
- Gender (only 2-3 values, impossible to scale)
- Status enum (most are "active", few are "archived")

---

## Real Example: Scaling a Payment System

```
Phase 1: Single database
  Traffic: 1000 QPS → all on 1 DB

Phase 2: Replication
  Traffic: 5000 QPS → reads on replicas, writes on primary

Phase 3: Sharding by user_id
  Traffic: 50,000 QPS → 10 shards, 5k QPS each
  
Phase 4: Geo sharding
  Traffic: 500,000 QPS → shard by user_id × region
  USA: 10 shards
  EU: 10 shards
  APAC: 10 shards
  Total: 30 shards
```

---

## Key Takeaways

1. **Shard = partition database by key**
2. **Hash sharding** = even distribution, but no range queries
3. **Range sharding** = range queries, but uneven distribution
4. **Directory sharding** = flexible, but adds lookup latency
5. **Hot shards** = monitor per-shard traffic, rebalance or cache
6. **Choose shard key carefully** (can't change easily)

---

## Q&A

**Q: When should I shard?**

When single DB can't handle:
- Traffic (>10k QPS)
- Storage (>1TB working set)

**Q: Can I change the shard key?**

Technically yes, but requires full rebalance (downtime). Choose wisely first time.

**Q: What about transactions across shards?**

Distributed transactions are hard. If you need them, reconsider your shard key.
