# Cache Stampedes & Cache Warming: Thundering Herds & Cold Starts

## The Problem

It's 2 AM. A cached item expires. Suddenly, 10,000 requests hit your database for the same missing key. Database melts. Website goes down.

This is a **cache stampede** (aka thundering herd problem).

```
Timeline:

t=0: Cache has hot_products with TTL=1hour
     10,000 requests/sec hit cache (all hits)

t=3600s: Cache expires
     
t=3600.001s: Request 1 checks cache, gets miss
     Queries DB for hot_products
     DB is now busy
     
t=3600.002s: Request 2 also gets miss, queries DB
             Request 3 also misses, queries DB
             ...Request 10,000 all miss
             
Database sees:
  Expected: ~10 queries/sec (from misses)
  Actual: 10,000 queries/sec (all requests became misses)
  
Result: DB overloaded, all requests timeout
```

**Why this matters:** Stampedes happen when you scale. A small cache miss becomes a cascade when serving millions of users.

---

## First Principles: Why Stampedes Happen

Cache works because of **locality of reference**: requests cluster around a few hot keys. One cache miss = all requests miss = database sees full load.

```
Normal (cache hit): 
  Request 1 → Cache (1μs) ✓
  Request 2 → Cache (1μs) ✓
  ...
  Request 10K → Cache (1μs) ✓
  Database: 0 queries

Cache stampede (miss):
  Request 1 → Cache (miss) → DB (10ms)
  Request 2 → Cache (miss) → DB (10ms)
  Request 3 → Cache (miss) → DB (10ms)
  ...
  Request 10K → Cache (miss) → DB (10ms)
  
  Database: 10,000 queries @ 10ms each = 100 seconds of processing
  But they all arrive at once = queue backs up, requests timeout
```

**Key insight:** Cache miss is expensive because all requests become synchronous DB queries.

---

## Strategy 1: Probabilistic Expiration (Xfetch)

Instead of hard TTL expiration, expire probabilistically:

```python
def get_with_xfetch(key):
    value, age = cache.GET_WITH_TIME(key)
    
    if value is None:
        # Cache miss, fetch and cache
        value = db.query(key)
        cache.SET(key, value, TTL=1hour)
        return value
    
    # Check if should refresh
    beta = 1.0  # tuning parameter
    time_until_expiry = TTL - age
    
    # Probability of refresh increases as cache gets older
    # Near expiry: high probability of refresh
    # Just cached: low probability
    
    if random.random() < beta * log(random.random()) / time_until_expiry:
        # Refresh in background
        background_task(db.query(key), lambda v: cache.SET(key, v))
    
    return value
```

**Diagram: Probabilistic Expiration**

```
Cache age over time (for same key):

Expiry at t=3600:

P(refresh)     Age
    ^          (seconds)
  1 |     +++  (high refresh probability)
    |  +++     (medium)
  0 | +++      (low)
    +--+--+--+--+--+---> time
      0  600 1200 1800 2400 3000 3600

Result:
  - Some requests at t=3599 refresh cache
  - Cache is already fresh when hard TTL hits
  - No thundering herd at t=3600
```

**Pros:**
- No thundering herd (spread out refreshes)
- Simple to implement
- Minimal overhead

**Cons:**
- Requires tuning (beta parameter)
- Probabilistic (not deterministic)
- Extra DB queries (some refresh early)

**When to use:** High-concurrency systems with hot keys (trending tweets, stock prices).

---

## Strategy 2: Locking / Mutex (Cache Lock Pattern)

First request to miss the cache gets a lock. Other requests wait for lock holder to refresh:

```python
def get_with_lock(key):
    value = cache.GET(key)
    if value is not None:
        return value
    
    # Cache miss
    lock = cache.SET_IF_NOT_EXISTS(f"{key}:lock", "1", EX=10)
    
    if lock:
        # I got the lock, refresh from DB
        value = db.query(key)
        cache.SET(key, value, TTL=1hour)
        cache.DELETE(f"{key}:lock")  # Release lock
        return value
    else:
        # Someone else has the lock, wait for them to refresh
        for attempt in range(100):
            value = cache.GET(key)
            if value is not None:
                return value
            sleep(10ms)
        
        # Timeout, fallback to DB query
        return db.query(key)
```

**Diagram: Lock-Based Stampede Prevention**

```
Cache miss at t=3600:

Request 1: Tries to SET lock
  Result: lock=acquired (no lock existed)
  Action: Query DB, update cache, release lock
  Latency: 15ms (1 DB query)
  
Request 2 (arrives 1ms later): Tries to SET lock
  Result: lock=failed (Request 1 has it)
  Action: Wait for cache to be populated
  Polls cache every 10ms
  t=3605ms: Cache is populated, returns
  Latency: 5ms (wait) vs 10ms (DB query)

Request 3-10000: Same as Request 2
  All wait for Request 1 to refresh
  Total DB queries: 1 (vs 10,000)
```

**Pros:**
- Prevents thundering herd completely
- Only 1 DB query for N requests
- Works with any cache backend

**Cons:**
- Lock holder latency increases (must wait for DB query)
- Waiting requests add latency (polling)
- Lock failures (what if holder crashes?)

**When to use:** Consistent refresh requirements. Database can handle occasional spike.

---

## Strategy 3: Cache Warming (Proactive Refresh)

Don't wait for expiry or misses. Refresh cache proactively based on schedule or events.

**Approach 1: Time-based warming**

```python
def warm_cache_job():
    """Run every hour, 5 minutes before expiry"""
    hot_keys = [
        'products:trending',
        'users:top_influencers',
        'config:feature_flags',
    ]
    
    for key in hot_keys:
        value = db.query(key)
        cache.SET(key, value, TTL=1hour)
        log(f"Warmed {key}")
```

**Pros:**
- Predictable, deterministic
- No thundering herd
- Cold start is predictable

**Cons:**
- Requires knowing which keys are hot
- Doesn't adapt if access patterns change
- Extra DB queries for unpopular keys

**Approach 2: Event-driven warming**

```
User behavior trigger:
  - User searches for "iPhone"
  - Search query becomes trending
  - System proactively caches "iPhone:trending"
  
Stock price trigger:
  - Stock price changes > 5%
  - Cache price immediately
  - Notify dependent systems
```

**Approach 3: Dependency-based warming**

```
If caching product_details (depends on product_prices):
  - When price cache is refreshed
  - Also refresh product_details cache
  - Avoid cascade of misses
```

---

## Strategy 4: Stale-While-Revalidate (Serve Stale)

Serve stale value while refreshing in background:

```python
def get_with_stale(key):
    value, expires_at = cache.GET_WITH_TTL(key)
    
    if value is None:
        # Hard miss, query DB
        value = db.query(key)
        cache.SET(key, value, TTL=1hour, STALE_TTL=10hours)
        return value
    
    if expires_at < now():
        # Cache expired, but we have stale value
        # 1. Return stale value immediately (fast!)
        # 2. Refresh in background
        background_task(db.query(key), lambda v: cache.SET(key, v, ...))
        
        return value  # Stale, but better than miss
    
    # Cache fresh
    return value
```

**Diagram: Serve Stale vs Hard Miss**

```
Request arrives at t=3605 (5s after expiry):

Option 1: Hard expiry (current behavior)
  Cache miss
  Query DB (10ms)
  Latency to user: 10ms
  All requests block on DB

Option 2: Stale-while-revalidate
  Return stale value immediately (1μs)
  Refresh in background (10ms)
  Latency to user: 1μs
  User doesn't notice (value is ~5s old)
  No thundering herd
```

**Pros:**
- User experiences no latency impact
- No thundering herd
- Works even if refresh fails (stale value is fallback)

**Cons:**
- Users may see slightly old data
- Requires background refresh process
- Stale value might be significantly old (if refresh was slow)

**When to use:** Non-critical data where staleness is acceptable (rankings, feeds, recommendations). High-concurrency systems.

---

## Failure Scenario: Cascading Stampedes

```
System architecture:

Clients → Load Balancer → 10 web servers → Cache → DB

t=0: Cache expires for 'hot_products'

t=0.001: 
  Web1: Cache miss, queries cache
  Web2: Cache miss, queries cache
  Web3: Cache miss, queries cache
  ...
  Web10: Cache miss, queries cache

All 10 web servers → Cache (all misses)
All 10 web servers → DB (simultaneous queries)

If DB response time > lock timeout:
  Web servers think lock holder crashed
  Web servers all query DB again
  
Result: DB gets 20 queries instead of 10
```

**Detection:**
- Monitor cache miss rate spikes
- Monitor DB query rate spikes at same time
- Compare miss rate before/after expiry

**Prevention:**
- Use locking + reasonable timeout (5-10s)
- Use probabilistic expiration
- Warm critical keys proactively

---

## Interview Pattern: Stampede Recovery

```
Q: "You're on-call at 2 AM.
   Cache for daily_deals expires.
   Database gets 50,000 queries/sec (normal: 100).
   Website times out.
   You have 10 minutes to fix it.
   What do you do?"

Weak answer:
  "Increase the cache TTL"
  (❌ Doesn't help right now, still stampeding)
  
  Or: "Clear the cache and restart"
  (❌ Makes it worse, still stampeding)

Strong answer:
  "Incident response:
  
  1. Immediate action (first 2 minutes):
     - Check cache miss rate (dashboard)
     - Is this a stampede? (spike in misses + DB queries)
     - If yes, trigger emergency lock pattern
     
  2. Implement locking (if not already):
     - Code change: add mutex on cache miss
     - Deploy with blue-green (5 min)
     - Or if not deployed, enable feature flag
     
  3. Workaround while deploying:
     - Manually warm critical keys
       for key in critical_keys:
         cache.SET(key, db.query(key))
     - Reduces miss rate immediately
     
  4. Monitor recovery:
     - Watch miss rate drop
     - Watch DB queries drop
     - Once stable, call off incident
  
  5. Post-incident (after shift):
     - Implement probabilistic expiration
     - Add monitoring for miss rate spikes
     - Load test to find breaking point
     - Add alert: if miss_rate > threshold, page on-call

Why this works:
  - Acknowledges it's a stampede (diagnosis)
  - Has multiple options (short-term + long-term)
  - Prioritizes speed (manual warm > deploy)
  - Measures impact (monitoring)
  - Prevents next incident (monitoring + alert)
  
Why this signals good judgment:
  - You recognize the pattern (stampede)
  - You have tactical vs strategic solutions
  - You understand production constraints (can't always redeploy)
  - You prioritize fixing the current incident first
  - You prevent recurrence"
```

---

## Checklist: Stampede Prevention

- [ ] Identified critical hot keys (top 20 by traffic)
- [ ] Stampede pattern chosen (lock / xfetch / warming / serve-stale)
- [ ] Monitoring in place (miss rate, DB query spikes)
- [ ] Alerting for high miss rates (page on-call)
- [ ] Load tested to breaking point
- [ ] Fallback strategy defined (what if cache is down?)
- [ ] Team trained on incident response (5-10min playbook)

## Common Wrong Answers

1. **"Just increase the TTL"**
   - Reduces frequency of stampedes, doesn't prevent them
   - Makes staleness worse

2. **"Clear the cache"**
   - Makes stampede worse by forcing all requests to DB
   - Never do this under load

3. **"Use a background job to refresh"**
   - Good idea, but timing is hard
   - If refresh is slow, cache may expire before refresh completes

4. **"The stampede won't happen in production"**
   - Famous last words
   - It will, during peak traffic or holiday spike

5. **"We can just scale the database"**
   - Expensive and slow
   - Better to prevent stampede in the first place
   - Database scaling doesn't help if CPU is bottleneck
