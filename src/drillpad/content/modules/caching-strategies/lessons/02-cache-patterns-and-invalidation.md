# Cache Patterns: Aside, Write-Through, Write-Back & Invalidation

## The Problem

Your cache is stale. User submits order, payment succeeds, but the cache still shows old balance. How do you keep cache and database consistent?

```
Scenario: Shopping cart cache

User balance: $100 (in DB)
Cache says: $100 (1 hour old)

User buys item ($50):
  1. Update DB: balance = $50 ✓
  2. Cache still says $100 ✗
  3. User sees old balance, thinks they have more money

When cache expires (1 hour later):
  Cache refreshes from DB
  User finally sees correct $50
  But 1 hour of stale data
```

**Why this matters in interviews:** Most production bugs stem from cache-database divergence. Senior SWEs must know which pattern fits which use case, trade-offs, and failure modes.

---

## First Principles: Write Propagation

When data changes, cache must be updated. Three strategies:

**1. Cache-Aside (Lazy Loading)**
- Application checks cache
- If miss, fetch from DB, populate cache
- When DB changes: do nothing, wait for expiry

**2. Write-Through**
- On write: update DB AND cache atomically
- Cache is always consistent with DB
- Cost: extra latency on writes

**3. Write-Back (Write-Behind)**
- On write: update cache first, return to user
- Background job writes to DB asynchronously
- Risk: cache-only write is lost if cache fails before DB write

---

## Cache-Aside Pattern

Application logic:

```
GET user_balance(user_id):
  1. Check cache: balance = redis.GET(user_id)
  2. If hit: return balance
  3. If miss:
     balance = db.query("SELECT balance FROM users WHERE id = ?")
     redis.SET(user_id, balance, TTL=1hour)
     return balance

UPDATE user_balance(user_id, new_balance):
  1. db.UPDATE("balance = ? WHERE id = ?", new_balance, user_id)
  2. redis.DELETE(user_id)  // Invalidate cache
  3. Return success
```

**Diagram: Cache-Aside Lifecycle**

```
Write operation:
  App → DB (update balance)
  App → Cache (DELETE key to invalidate)
  Cache now empty

Next read operation:
  App checks cache (miss)
  App queries DB
  App populates cache
  Future reads hit cache
```

**Pros:**
- Simple to implement
- No write latency overhead
- DB and cache are loosely coupled
- Good for read-heavy workloads

**Cons:**
- Cache misses after invalidation (cold cache)
- Stale data before invalidation (if no explicit delete)
- Application must handle cache logic

**When to use:** Read-heavy systems (80% reads, 20% writes). Social feeds, product pages, user profiles.

**When NOT to use:** Write-heavy systems, financial systems (stale balance = big problem).

---

## Write-Through Pattern

```
UPDATE user_balance(user_id, new_balance):
  1. db.UPDATE(...)
  2. redis.SET(user_id, new_balance)  // Update cache too
  3. Return success to user
  
Problem: Both writes must succeed, or we're inconsistent
Solution: Two-phase commit or assume cache update always succeeds
```

**Diagram: Write-Through Transaction**

```
Request: Update balance to $50
  ↓
DB update succeeds ✓
  ↓
Cache update succeeds ✓
  ↓
Return success to user

If cache fails:
  DB has $50 ✓
  Cache has old value ✗
  Next read: app queries DB, gets $50, updates cache
  But brief inconsistency window
```

**Pros:**
- Cache always consistent with DB (after write completes)
- No stale data risk
- Simple transaction semantics

**Cons:**
- Write latency: must wait for both DB and cache
- If cache is slow, writes are slow
- Extra network round-trip for every write

**Latency calculation:**
```
DB write: 10ms
Cache write: 1ms
Total: 11ms (vs cache-aside: 10ms)
```

**When to use:** Consistency is critical (payments, orders, inventory). Write latency is acceptable.

**When NOT to use:** Real-time systems (high-frequency trading needs < 1ms latency).

---

## Write-Back (Async) Pattern

```
UPDATE user_balance(user_id, new_balance):
  1. redis.SET(user_id, new_balance)  // Fast!
  2. Return success immediately
  3. Background job: eventually write to DB
     queue.ADD({user_id, new_balance})
     
Background worker (async):
  4. batch = queue.GET_BATCH(1000)
  5. db.BATCH_UPDATE(batch)
  6. queue.ACK(batch)
```

**Diagram: Write-Back with Loss Risk**

```
Timeline:
  t=0: User writes balance=$50
  t=0: Redis updated ✓ (return immediately)
  t=0-100ms: Cache has $50, DB has old $100
  t=100ms: Background worker batches write
  t=110ms: DB finally updated to $50
  
Failure at t=50ms (cache server crashes):
  Redis: $50 lost ✗
  DB: still $100 ✗
  User's write is LOST
```

**Pros:**
- Write latency is near-zero (just cache write)
- Good for high-frequency updates (click counters, view counts)
- Batch writes reduce DB overhead

**Cons:**
- Data loss risk if cache crashes before DB write
- Inconsistency window (cache ahead of DB)
- Complexity: need reliable queue, retry logic

**When to use:** Eventually-consistent data (view counts, click counters). Acceptable data loss.

**When NOT to use:** Transactional data (orders, payments). Financial records.

---

## Cache Invalidation Strategies

### Strategy 1: TTL (Time-To-Live)

```
redis.SET(user_id, balance, EX=3600)  // Expire in 1 hour

Problem:
  - Stale for up to 1 hour
  - No explicit invalidation
  - But simple and resilient
```

**Best for:** Data that doesn't change often (user profiles, config).

### Strategy 2: Explicit Invalidation

```
UPDATE user_balance(user_id, new_balance):
  1. db.UPDATE(...)
  2. redis.DELETE(user_id)  // Explicit delete
  3. Return success
```

**Failure case:**
```
t=0: DB updated
t=1: Redis DELETE fails (network error)
t=2: Next read hits cache (stale $100)
t=3: Retry DELETE succeeds
```

**Problem:** Dual-write problem (see exactly-once-semantics module). Delete can fail, cache stays stale.

**Solution:** Idempotent deletes + monitoring.

### Strategy 3: Versioning

```
User balance:
  Version 1: $100
  Version 2: $50 (after transaction)

Cache keys:
  balance:user_123:v1 = $100
  balance:user_123:v2 = $50

Code queries current version:
  current_version = metadata.GET(user_id)  // returns 2
  balance = redis.GET(f"balance:{user_id}:v{current_version}")
```

**Pros:**
- No delete operation needed
- Can keep old versions (A/B testing)
- Consistent reads

**Cons:**
- More complex
- Metadata tracking needed

**Best for:** Canary deployments, feature flags, A/B tests.

### Strategy 4: Event-Driven Invalidation

```
Database publishes event:
  "USER_BALANCE_UPDATED user_123 new_balance=$50"

Cache subscriber listens:
  On event: redis.DELETE(user_123)

Advantage: Decoupled, works across services
Problem: Event delivery failures (see message-queues module)
```

---

## Failure Scenario: The Dual-Write Trap

```
UPDATE balance from $100 to $50:

Code:
  db.UPDATE("balance = 50 WHERE user_id = ?")
  redis.SET(user_id, 50)

Failure at step 2 (Redis fails):
  DB has $50 ✓
  Cache has $100 ✗ (old value)
  
Next read:
  App checks cache: $100 (WRONG!)
  User sees old balance
  
How to detect:
  - Monitoring: compare cache vs DB periodically
  - Audit logs: find missing updates
  - User complaints: "My balance is wrong"

How to fix:
  - Retry Redis SET
  - If persists, invalidate and let cache rebuild
  - Trigger consistency check: full reload from DB
```

**Prevention:**
- Use write-through only if both writes succeed
- Use TTL + explicit invalidation (belt and suspenders)
- Monitor staleness: compare sample of cache vs DB
- Alerting: if divergence > threshold, page on-call

---

## When to Use Which Pattern

| Pattern | Consistency | Write Latency | Data Loss Risk | Best For |
|---------|-------------|---------------|----------------|----------|
| **Cache-Aside** | Eventually | None | None (DB is source) | Read-heavy, non-critical |
| **Write-Through** | Strong | Higher | Low (both succeed or both fail) | Payments, inventory |
| **Write-Back** | Eventual | Minimal | High (cache loss = lost write) | Counters, analytics, logs |

---

## Interview Pattern: Cache Invalidation

```
Q: "Your e-commerce site caches user balance.
   Transactions happen 100x/sec.
   After checkout, cache still shows old balance for 30 seconds.
   User sees wrong balance, panics.
   How do you fix it?"

Weak answer:
  "Lower the TTL to 5 seconds"
  (❌ Still stale, and more cache misses)
  
  Or: "Use write-through"
  (❌ Adds 5ms latency to every checkout, high volume)

Strong answer:
  "Root cause: we're using cache-aside with TTL.
  Problem: stale data for 30 seconds is unacceptable for balances.
  
  1. Evaluate the options:
     - Lower TTL: reduces staleness but increases misses
     - Write-through: consistent but slower
     - Invalidation: explicit delete after transaction
  
  2. Decision: Explicit invalidation (cache-aside + immediate delete)
     - After checkout success, redis.DELETE(user_id)
     - Next read rebuilds cache from DB
     - Stale window: ~10ms (time to rebuild)
  
  3. Handle failures:
     - If DELETE fails: retry with exponential backoff
     - If DELETE still fails: accept eventual consistency
     - Monitor: alert if user balance cache > 1 min stale
  
  4. A/B test (if budget allows):
     - Control: cache-aside (status quo)
     - Treatment: cache-aside + immediate invalidation
     - Measure: staleness, user complaints, miss rate
     - Rollout if treatment wins
  
  Why this works:
  - Strong consistency for critical data (balance)
  - Minimal performance impact (no write latency)
  - Handles failures gracefully"

Why this signals good judgment:
  - You understand cache-database consistency models
  - You recognize consistency vs latency tradeoffs
  - You have a concrete, testable solution
  - You consider failure modes (DELETE failure)
  - You measure impact before rollout
```

---

## Checklist: Cache Invalidation

- [ ] Chosen pattern matches use case (read-heavy vs write-heavy)
- [ ] Invalidation strategy defined (TTL / explicit / versioning / events)
- [ ] Failure modes identified (what if DELETE fails?)
- [ ] Monitoring in place (compare cache vs DB samples)
- [ ] Alerting for staleness (if cache > threshold, page on-call)
- [ ] A/B tested or canary rolled (measure real impact)

## Common Wrong Answers

1. **"Just use a longer TTL"**
   - Makes staleness worse, not better
   - Confuses symptom with cause

2. **"Delete from cache on write"**
   - Good idea, but what if delete fails?
   - No monitoring = silent data divergence

3. **"Use write-back for all data"**
   - Unacceptable for financial/transactional data
   - Data loss risk

4. **"Cache and DB will stay in sync automatically"**
   - No, you must explicitly keep them consistent
   - Murphy's law: they will diverge

5. **"Consistency doesn't matter"**
   - Sometimes true (view counts), but not for balances/orders
   - Know the difference
