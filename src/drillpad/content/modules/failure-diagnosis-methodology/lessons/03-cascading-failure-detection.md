# Failure Diagnosis: Cascading Failure Detection & Prevention

## The Cascading Failure Pattern

```
Service A: healthy
  ├─ Calls Service B
  ├─ B is slow (5s timeout)
  ├─ A's thread pool fills up (waiting on B)
  ├─ A's queue fills up
  ├─ Traffic continues arriving
  ├─ Queue overflow → dropped requests
  ├─ Clients retry → more requests
  ├─ A is now dead (can't process anything)
  ├─ B is now dead (overloaded from retries)
  └─ Cascade: A down, B down, C down (depends on B)

Result: 3 services down because 1 was slow
```

## Detection: The Queue Depth Signal

**Queue depth is the canary:**

```
Healthy system:
  Inbound queue depth: 0-10 (requests processed immediately)
  
Service B starting to slow:
  Queue depth: 100 (requests piling up, threads busy)
  
Service B timing out:
  Queue depth: 10,000 (backpressure building)
  A's queue depth: 5,000 (A waiting for B responses)
  
Cascade starting:
  A's queue: 100,000 (queue overflow)
  A dropping: yes (new requests rejected)
  A's clients: retrying (more load)
```

**Interview answer:**

```
Q: "How do you detect a cascading failure early?"

"Monitor queue depth as a leading indicator.

Red lights:
  - Queue > 1000: Something is slow (check downstream)
  - Queue > 10,000: Cascade risk (increase timeout? kill retries?)
  - Queue > 100,000: Cascade in progress (drop traffic)

Mitigation (in order):
  1. Kill retries: Stop clients from hammering B
  2. Drop traffic: Intentionally reject new requests
  3. Graceful shutdown: Stop accepting requests (drain existing)
  4. Escalate: Page oncall (incident in progress)
"
```

## Prevention: The Circuit Breaker Pattern

```
Service A calling B:

State 1: CLOSED (normal)
  - Forward requests to B
  - Track failures
  
State 2: OPEN (B is down)
  - Don't forward to B
  - Fail fast (return error immediately)
  - Don't waste A's resources waiting
  
State 3: HALF_OPEN (testing recovery)
  - Send 1 test request to B
  - If success: Go to CLOSED
  - If fail: Go back to OPEN
```

**Example:**

```
A → B interaction:
  1. B is healthy: A sends 100 req/sec, B processes fine
  2. B gets slow: A's timeout 2%, circuit still CLOSED
  3. B times out 5x in a row: Circuit OPEN
  4. A now fails fast: "B down, returning 503"
  5. A's queue doesn't fill up: Requests fail immediately
  6. B recovers: Circuit HALF_OPEN (test 1 request)
  7. Test succeeds: Circuit CLOSED (resume normal)
  
Result: Cascade prevented (A stays alive while B recovers)
```

## Backpressure: When to Push Back

**Good backpressure:**
```
Queue depth > 1000?
  - Return 429 (Too Many Requests) to client
  - Client backs off (exponential backoff)
  - Your queue drains
  - System recovers
```

**Bad backpressure:**
```
Keep accepting requests (hope for best)
  - Queue grows to 100,000
  - Memory fills up
  - System crashes (OOM)
  - Recovery takes hours
```

**Interview answer:**

```
Q: "Your system is being hammered. 10x normal traffic. What do you do?"

"In order:
  1. Enable circuit breaker (fail fast to downstreams)
  2. Return 429 when queue > threshold (push back to clients)
  3. Reduce work per request (cache responses, skip non-critical)
  4. Scale horizontally (add servers, load balance)
  5. If still overloaded: Shed traffic (drop lowest-priority requests)

Goal: Keep system alive, accept degradation
  - Better: 50% success at latency 50ms
  - Worse: 100% timeout at latency 10s (all requests fail)
"
```

## Real Example: Payment Service Cascade

```
Normal: 1000 TPS
  - Payment API
  - Payment Processor (backend queue)
  - Credit card processor (external API)

Card processor goes down (maintenance):
  1. Payment API times out calling card processor (5s timeout)
  2. API's thread pool fills (waiting for card processor)
  3. Queue builds: 10,000 requests waiting
  4. API's queue thread limit hit, rejects new requests
  5. But also: Clients retry (thinking it's temporary)
  6. More load arrives (cascade)
  7. API goes down despite having capacity

Without circuit breaker:
  - API down for 30 min
  - $10k lost revenue

With circuit breaker:
  - Card processor down detected in 10s
  - Circuit OPEN: API returns 503 immediately (no wait)
  - Clients retry with backoff
  - API stays alive (handles other operations)
  - Card processor comes back up
  - Circuit HALF_OPEN: Test 1 request (succeeds)
  - Circuit CLOSED: Resume normal
  - API down for 30 sec (not 30 min)
  - Retry logic handles the 503s
  - ~$100 lost revenue (not $10k)
```

## Degradation Strategy

**What to degrade when overloaded:**

```
Priority 1 (never degrade):
  - Payments (money at stake)
  - Critical functionality (core product)
  
Priority 2 (degrade if needed):
  - Analytics (can queue for later)
  - Logging (non-critical)
  
Priority 3 (drop if needed):
  - Metrics collection
  - Non-critical monitoring

Example (10x overload):
  1. Drop metrics collection (saves 10% CPU)
  2. Queue analytics to async queue (saves 20% CPU)
  3. Reduce logging verbosity (saves 5% CPU)
  4. Now handling: 70% of normal traffic
  5. With circuit breaker: System stays alive
```

## Cascading Failure Checklist

**After incident, ask:**

- [ ] What was the root cause? (B slowed down)
- [ ] When did we detect it? (Queue depth = leading signal)
- [ ] What was the cascade path? (A→B→C, how many affected?)
- [ ] How long did it take to recover? (30 min, too long)
- [ ] Did we have circuit breaker? (No, should add)
- [ ] Did we push back to clients? (No, accepted all requests)

**Before next incident, implement:**

- [ ] Circuit breaker (fail fast)
- [ ] Queue depth alerting (alert at 1000, escalate at 10000)
- [ ] Graceful degradation (know what to drop)
- [ ] Backpressure (return 429 when overloaded)

