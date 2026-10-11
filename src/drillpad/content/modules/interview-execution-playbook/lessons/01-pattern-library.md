# Pattern Library: 5 Patterns Solve 90% of Design Problems

## The Core Insight

Most system design problems follow patterns. Recognizing the pattern → applying the solution → saves 20+ minutes of thinking.

```
Problem:        Cache invalidation
Recognition:    "This is cache pattern #3: TTL + write-through"
Solution:       Apply pattern, adapt to constraints
Result:         Interview: efficient, confident, correct
```

## Pattern 1: Cache Invalidation (Consistency vs Freshness)

**When to use:** Data is expensive to compute, must balance freshness vs performance

```
Variants:
  1. TTL (Time-based): expire after N seconds
     - Use if: Stale data acceptable
     - Cost: Simple
     - Risk: Might be too stale
     
  2. Write-through: invalidate on every write
     - Use if: Strong consistency required
     - Cost: More writes to cache
     - Risk: Cache churn if updates frequent
     
  3. Event-driven: invalidate on specific events
     - Use if: Know what causes staleness
     - Cost: Complex event system
     - Risk: Miss some invalidation scenarios
     
  4. LRU + expiry: combine time + usage
     - Use if: Memory limited, freshness matters
     - Cost: Medium complexity
```

**Interview pattern:**
```
Q: "Cache hit rate dropped from 95% to 60%"

Pattern recognition:
  - This is cache invalidation problem
  - Likely: TTL too short OR write frequency too high
  
Answer:
  "Check if writes increased (invalidating cache more).
   If writes same: TTL might be too aggressive.
   Solution: Measure hit rate at different TTLs, pick sweet spot."
```

## Pattern 2: Replication (Availability vs Consistency)

**When to use:** Need data in multiple places (backup, geo-distributed, load sharing)

```
Variants:
  1. Master-slave: writes to master, reads from slave
     - Consistency: Strong (after replication lag)
     - Availability: Medium (if master fails, failover needed)
     
  2. Multi-master: writes to any replica
     - Consistency: Weak (conflicts possible)
     - Availability: High (any replica works)
     
  3. Quorum: write to majority, read from quorum
     - Consistency: Strong (if quorum overlaps)
     - Availability: Medium (must reach quorum)
```

**Interview pattern:**
```
Q: "Your database is in US-East. Add Europe support."

Pattern recognition:
  - This is replication problem
  - Geography → likely use eventual consistency
  
Answer:
  "Master in US-East (writes), read replica in EU (reads).
   Replication lag ~100ms (acceptable for read-heavy).
   If write latency critical: multi-master with conflict resolution.
   If strong consistency required: quorum (slower but safer)."
```

## Pattern 3: Partitioning (Scaling Bottleneck)

**When to use:** Data too large for one server, need to split

```
Variants:
  1. Range-based: shard by value range
     - User 1-1M: shard 1
     - User 1M-2M: shard 2
     - Pro: Easy to query ranges
     - Con: Uneven distribution (hot shards)
     
  2. Hash-based: shard by hash(key)
     - hash(user_id) % 10 = shard number
     - Pro: Even distribution
     - Con: Can't query ranges efficiently
     
  3. Directory-based: lookup table maps key → shard
     - Explicit mapping maintained
     - Pro: Full control, can rebalance
     - Con: Extra hop (slower), centralized
```

**Interview pattern:**
```
Q: "Scale to 1 billion users"

Pattern recognition:
  - This is partitioning problem
  - Need to choose shard key
  
Answer:
  "Shard by user_id (hash-based).
   10,000 shards, 100k users per shard.
   Rebalance yearly (add new shards, migrate keys).
   If user frequently queries their own data: good.
   If cross-user queries needed: might join across shards."
```

## Pattern 4: Load Shedding (Overload Protection)

**When to use:** Traffic spike or downstream slow, must drop requests gracefully

```
Variants:
  1. Return error (429 Too Many Requests)
     - Client backs off
     - Pro: Transparent, simple
     - Con: Some requests lost
     
  2. Queue with limit (accept up to N, queue rest)
     - Process when capacity available
     - Pro: No requests lost (if client waits)
     - Con: Latency increases
     
  3. Priority-based (drop low-priority, keep critical)
     - analytics < business logic < payments
     - Pro: Optimize for what matters
     - Con: Need to classify requests
```

**Interview pattern:**
```
Q: "10x traffic spike, how do you handle it?"

Pattern recognition:
  - This is load shedding problem
  
Answer:
  "1. Enable backpressure: return 429 if queue > threshold
   2. Shed non-critical: drop metrics, queue analytics
   3. Scale: add servers (but takes 5-10 min)
   
   Result: System stays alive, some requests fail gracefully."
```

## Pattern 5: Rate Limiting (Quota Enforcement)

**When to use:** Control request rate per user, per IP, per service

```
Variants:
  1. Token bucket: allow N requests per second
     - Tokens refill at rate
     - Pro: Smooth, allows bursts
     - Con: Token bucket sync complexity
     
  2. Sliding window: count requests in last N seconds
     - Pro: Simple
     - Con: Boundary conditions tricky
     
  3. Leaky bucket: fixed rate, queue overflows
     - Pro: Strict rate limit
     - Con: User might timeout
```

**Interview pattern:**
```
Q: "API rate limit is 100 req/sec per user"

Pattern recognition:
  - This is rate limiting problem
  
Answer:
  "Use token bucket: 100 tokens/sec.
   Client can burst 100 requests at start.
   Then throttled to 100/sec.
   If over limit: return 429 with Retry-After header.
   
   Storage: Redis for rate limit state (fast, in-memory)."
```

## Meta-Pattern: How to Recognize Patterns

```
When you see a problem:

Step 1: Extract the constraint
  - "Too slow" → Performance problem (caching, partitioning, async)
  - "Too much data" → Partitioning problem
  - "Data in multiple places" → Replication problem
  - "Too many requests" → Load shedding or rate limiting
  - "Users getting wrong data" → Consistency problem (invalidation)

Step 2: Map to pattern
  - Slow read → Cache
  - Slow write → Async, queue, or batch
  - Data consistency → Replication variant
  - Overload → Load shedding + rate limiting

Step 3: Pick variant
  - Consistency vs availability tradeoff
  - Simplicity vs performance tradeoff
  - Cost vs correctness tradeoff
```

## Interview Execution

**Bad approach (no pattern recognition):**
```
Q: Design cache for 1B users
A: "Uh... use Redis? With... LRU eviction?"
(Vague, no structure, 70 points)
```

**Good approach (pattern recognition):**
```
Q: Design cache for 1B users
A: "This is cache invalidation pattern.
   Two sub-problems:
   1. Data consistency (TTL vs write-through)
   2. Memory limit (LRU eviction)
   
   I'd use: TTL + LRU
   - TTL for stale tolerance (5 min acceptable)
   - LRU for memory constraint (1TB available)
   - Write-through for critical data
   
   Trade-off: 95% hit rate vs 100% correctness"
(Structured, pattern-based, 85 points)
```

## Practice: Pattern Recognition

**Exercise:** For each problem, name the pattern + variant

1. "Design YouTube recommendations cache"
   → Pattern: Cache invalidation + caching strategy
   
2. "Stripe payment system multi-region"
   → Pattern: Replication + consistency
   
3. "Twitter scale to 1B tweets/day"
   → Pattern: Partitioning + replication
   
4. "Service under DDoS, how to protect?"
   → Pattern: Load shedding + rate limiting
   
5. "Database slow during peak hours"
   → Pattern: Caching + async + partitioning (choose one or combo)

**Speed metric:** Can you name pattern + variant in <30 seconds?
If yes → interview ready
If no → practice pattern recognition more

