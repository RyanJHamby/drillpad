# Distributed Rate Limiting: Shared Counters, GCRA, Per-Region Budgets

## The Problem

Your API has a rate limit: 1,000 requests/sec per user. You have 10 servers handling traffic. How do you enforce a global limit across all servers?

```
Naive approach: Each server has own counter

Server 1: 200 requests/sec from user_123
Server 2: 200 requests/sec from user_123
Server 3: 200 requests/sec from user_123
Server 4: 200 requests/sec from user_123
Server 5: 200 requests/sec from user_123

Total: 1,000 requests/sec ✓ (exactly at limit)

But then:
Server 6: 1 request from user_123 (would breach limit!)
Server 6 doesn't know total is 1,000
Server 6 allows it (local counter = 1)
Total: 1,001 (over limit, user cheated!)
```

**Why this matters:** Distributed rate limiting prevents abuse at scale. Trading systems, payment APIs, public APIs all need this. Single-point-of-failure limits are unacceptable.

---

## First Principles: Shared vs Decentralized

**Shared counter (Redis):**
- Single source of truth
- All servers ask: "Can I have 1 token?"
- Accurate but centralized (single point of failure)

**Decentralized (GCRA, Token bucket with lease):**
- Each server has approximate counter
- Less accurate but resilient (no SPOF)
- Better for distributed systems

```
Shared counter approach:
  Client → Server 1 → Check Redis counter
                   ← Redis: "You have 500 tokens left, approved"
                    Update Redis: 499 left

Decentralized:
  Client → Server 1 → Check local counter
                   ← Local: "You have 500 tokens (approx), approved"
                    Decrement local: 499 left
  
  (Servers eventually sync with central authority)
```

---

## Shared Counter: Token Bucket (Redis)

```python
class RateLimiter:
    def __init__(self, redis, user_id, rate=1000, interval=1):
        self.redis = redis
        self.user_id = user_id
        self.rate = rate
        self.interval = interval
    
    def allow(self, tokens=1):
        key = f"rate_limit:{self.user_id}"
        
        # Get current tokens
        current = self.redis.get(key) or 0
        
        if current + tokens <= self.rate:
            # Tokens available, consume them
            self.redis.incrby(key, tokens)
            self.redis.expire(key, self.interval)  # Reset every second
            return True
        else:
            # Over limit
            return False
```

**Problem: Race condition**

```
Thread 1: GET current=999
Thread 2: GET current=999
Thread 1: 999 + 1 <= 1000? Yes, INCRBY (total: 1000)
Thread 2: 999 + 1 <= 1000? Yes, INCRBY (total: 1001) ← OVER!

Both threads thought they were safe
```

**Solution: Lua script (atomic)**

```lua
-- check_and_increment.lua
local key = KEYS[1]
local rate = tonumber(ARGV[1])
local interval = tonumber(ARGV[2])
local tokens = tonumber(ARGV[3])

local current = redis.call('GET', key)
if current == false then
    current = 0
else
    current = tonumber(current)
end

if current + tokens <= rate then
    redis.call('INCRBY', key, tokens)
    redis.call('EXPIRE', key, interval)
    return 1  -- Allowed
else
    return 0  -- Denied
end
```

**Usage:**

```python
def allow(self, tokens=1):
    script = """
    local current = redis.call('GET', KEYS[1]) or 0
    current = tonumber(current)
    local rate = tonumber(ARGV[1])
    if current + tonumber(ARGV[2]) <= rate then
        redis.call('INCRBY', KEYS[1], ARGV[2])
        redis.call('EXPIRE', KEYS[1], ARGV[3])
        return 1
    else
        return 0
    end
    """
    result = self.redis.eval(script, 1, f"rate_limit:{self.user_id}", 
                            self.rate, tokens, self.interval)
    return result == 1
```

---

## Decentralized: GCRA (Generic Cell Rate Algorithm)

Used for ATM/telecom rate limiting. Elegant without central coordination.

**Idea:** Simulate a queue with finite capacity. If queue is full, reject.

```
GCRA parameters:
  T = packet interval (1/rate, e.g., 1 ms for 1000 req/sec)
  I = increment (tokens per request)
  L = limit (max queue length)

State:
  next_allowed_time = when next request is allowed
```

**Algorithm:**

```python
def check_rate(user_id, now_time):
    key = f"gcra:{user_id}"
    
    # Get stored next_allowed_time (default 0)
    tat = redis.get(key) or 0  # TAT = Theoretical Arrival Time
    tat = float(tat)
    
    # Calculate when this request can be allowed
    new_tat = max(tat, now_time) + T  # T = interval between allowed requests
    
    if new_tat - now_time <= L:  # L = max allowed delay
        # Request is within budget
        redis.set(key, new_tat)
        return True, new_tat - now_time  # Return delay
    else:
        # Would exceed budget
        return False, new_tat - now_time
```

**Example:**

```
Rate limit: 100 req/sec
T = 1/100 = 0.01 seconds (10 ms per request)
L = 0.1 seconds (max 10 requests burst)

Request 1 at t=0:
  tat=0, new_tat = max(0, 0) + 0.01 = 0.01
  delay = 0.01 - 0 = 0.01s
  Allowed? 0.01 - 0 <= 0.1? Yes
  
Request 2 at t=0.001:
  tat=0.01, new_tat = max(0.01, 0.001) + 0.01 = 0.02
  delay = 0.02 - 0.001 = 0.019s
  Allowed? 0.019 <= 0.1? Yes
  
Request 11 at t=0:
  tat=0, new_tat = max(0, 0) + 0.01 = 0.01
  After 10 back-to-back: tat = 0.1
  
Request 11 at t=0:
  new_tat = max(0.1, 0) + 0.01 = 0.11
  delay = 0.11 - 0 = 0.11s
  Allowed? 0.11 <= 0.1? No, DENIED
```

**Pros:**
- Handles bursts naturally (up to L tokens)
- No per-request network call (use local clock)
- Elegant math

**Cons:**
- Requires synchronized clocks (server time skew = problems)
- Less intuitive than token bucket

---

## Distributed: Per-Region Budgets

Large systems have multiple regions. Total limit: 10,000 req/sec. Distribute across regions:

```
Total budget: 10,000 req/sec
  Region US-East: 4,000 req/sec (40%)
  Region US-West: 3,000 req/sec (30%)
  Region EU: 2,000 req/sec (20%)
  Region APAC: 1,000 req/sec (10%)

Each region enforces its budget independently
Requests routed to nearest region (locality)

Failure: US-East goes down
  Traffic reroutes to other regions
  Other regions enforce their local limits
  Global limit (gracefully) reduced
```

**Diagram: Per-Region Budgeting**

```
Global rate limiter:
  Total: 10,000 req/sec
    ↓
  Region budgets:
    US-East: 4,000 (distributed among 10 servers)
    US-West: 3,000 (distributed among 8 servers)
    EU: 2,000 (distributed among 5 servers)
    ↓
  Per-server budgets:
    US-East-1: 400 req/sec
    US-East-2: 400 req/sec
    ...
```

**Implementation:**

```python
class DistributedRateLimiter:
    def __init__(self, redis, user_id, region, global_limit, region_share):
        self.region_limit = global_limit * region_share
        self.local_limit = self.region_limit / num_servers_in_region
    
    def allow(self):
        # Check local counter (fast)
        local_key = f"rate_limit:{self.user_id}:local"
        if redis.incr(local_key) > self.local_limit:
            return False
        
        # Periodic sync with regional counter
        if random() < 0.01:  # 1% of requests
            regional_key = f"rate_limit:{self.user_id}:region"
            regional_count = redis.get(regional_key) or 0
            if regional_count > self.region_limit:
                # Limit hit at region level, reset
                redis.set(local_key, 0)
                return False
        
        return True
```

**Trade-off:** Local counters can go over budget briefly, but recover when sync happens.

---

## Failure Scenario: Clock Skew with GCRA

```
Two servers with slightly different clocks:

Server A: system_time = 1000.000
Server B: system_time = 1000.050  (50ms ahead)

GCRA with T=0.01 (100 req/sec):

User sends 10 burst requests to Server A:
  A stores TAT = 0.1 seconds in Redis

User sends request to Server B (which thinks it's 50ms later):
  B sees TAT = 0.1
  B thinks: new_tat = max(0.1, 1000.050) + 0.01 = 1000.060
  B thinks: can allow (delay is small)
  B increments counter again

Result: Rate limit exceeded (11 requests when limit is 10)
```

**Detection:** Monitor for:
- NTP clock skew (should be < 10ms)
- Rate limit overages (if GCRA, should be minimal)

**Prevention:**
- Sync clocks (NTP daemon)
- Use Redis time (not local clock)
- Add safety margin: if TAT - now > (L + safety_margin), reject

---

## Interview Pattern: API Rate Limiting

```
Q: "You have a public API with 1M users.
   Each user allowed 1,000 req/sec.
   You have 100 servers globally.
   A user finds a way to send 10,000 req/sec without being blocked.
   How did they cheat, and how do you fix it?"

Weak answer:
  "Each server tracks its own counter"
  (✓ Correct diagnosis, but doesn't explain the full problem)
  
  Or: "Use Redis to centralize"
  (✓ Correct, but doesn't address failure modes)

Strong answer:
  "They exploited client-side load balancing:
  
  Problem diagnosis:
    1. Without distributed coordination, each server allows:
       1,000 req/sec locally
    2. With 100 servers, they can send:
       100 servers × 1,000 = 100,000 req/sec (100x over limit!)
    3. Each server thinks traffic is fine (only seeing 1% of it)
  
  Solution options:
  
  Option A: Centralized counter (Redis)
    - All servers check shared counter
    - Lua script: atomic increment + check
    - Pro: Accurate, prevents cheating
    - Con: Redis is SPOF (if down, rate limiting fails)
  
  Option B: GCRA with Redis time
    - Decentralized algorithm (no per-request network call)
    - All servers use Redis GETTIME (synchronized)
    - Pro: Doesn't require counter calls for every request
    - Con: Requires clock sync, more complex
  
  Option C: Per-region budgets
    - Divide global limit across regions
    - Each region enforces locally
    - Pro: Resilient (region failure reduces limit gracefully)
    - Con: Hard to allocate budgets optimally
  
  I'd recommend A + B hybrid:
    - Use GCRA locally (fast, no SPOF)
    - Redis counter for audit (every 10 seconds)
    - Compare: if GCRA is > Redis counter + threshold, reject
    - Handles clock skew, but resilient to Redis failures
  
  Implementation:
    1. Add Lua script to Redis (atomic increment + check)
    2. Deploy to 100 servers
    3. Monitor: compare actual vs limit (should be ~ 1,000 per server)
    4. Alert if any server seeing 10,000+ (indicates cheating attempt)
  
  Cost:
    - One Redis call per request (1ms latency)
    - Or: GCRA + periodic sync (async checks)
  
  Testing:
    - Load test: 100 clients × 1,000 req/sec
    - Measure: total should be ~100,000 (or less if we rate limit)
    - Measure: Redis counter should match (within 1%)
"

Why this signals good judgment:
  - You diagnosed the attack (load balancing bypass)
  - You know multiple algorithms (centralized vs distributed)
  - You understand trade-offs (accuracy vs latency vs SPOF)
  - You picked a hybrid (best of both worlds)
  - You have monitoring (detect future attempts)
```

---

## Checklist: Distributed Rate Limiting

- [ ] Rate limit enforced globally (not per-server)
- [ ] Lua scripts or atomic operations (no race conditions)
- [ ] Burst handling defined (grace period or strict limit)
- [ ] Failure mode planned (what if Redis is down?)
- [ ] Clock sync verified (NTP, < 10ms skew)
- [ ] Monitoring in place (actual vs limit)
- [ ] Alerting for abuse (if actual > limit)
- [ ] Per-user limits vs per-IP vs per-API-key (clear definition)

## Common Wrong Answers

1. **"Each server tracks its own limit"**
   - Allows multiplying limit by number of servers
   - Invites cheating

2. **"Rate limit in application code without backup"**
   - If code has bug, no safety net
   - Always have Redis/external check

3. **"Reject immediately when limit hit"**
   - Better: Return HTTP 429 with Retry-After header
   - Clients know when to retry

4. **"Use strict token bucket (no bursting)"**
   - Legitimate traffic has bursts
   - Better: Allow short burst (10x normal) then rate limit

5. **"Don't monitor, just set limit and forget"**
   - Limits change, needs per-user customization
   - Monitor to detect abuse attempts
