# Distributed and Production Debugging: When You Can't Use a Debugger

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Challenge: Multi-Service Systems

You have 5 services: Frontend, API, DB, Cache, Queue.

```
User → Frontend (slow) → API (slow) → DB (slow) → User (slow)

Where is the time?
- Frontend rendering takes 100ms?
- Network latency adds 200ms?
- API processing takes 500ms?
- DB query takes 1000ms?

You can't use a debugger on all 5 services simultaneously.
```

**The solution:** Distributed tracing + correlation logs.

## Partial Failure: The Distribution Problem

A single machine fails in one way. A distributed system fails in many ways.

```
Single service failure:
  Service down → all requests fail (obvious)

Distributed system failures:
  Service A down → requests timeout (slow)
  Service B slow → requests queue (cascading)
  Network partition → some requests succeed, some timeout
  Partial data corruption → some users affected, most OK
  Clock skew → timestamp-based logic breaks
  
Debugging symptom "Slow request":
  - Could be any of 5 services
  - Could be network
  - Could be race between services
  - Need visibility into all services
```

## Distributed Tracing: Following One Request

**Goal:** See exactly what each service did for one request.

```
Request ID: req_abc123

Trace:
  Frontend receives: req_abc123 at 10:00:00.100
  ├─ Renders template: 5ms
  └─ Calls API at 10:00:00.105
  
  API receives: req_abc123 at 10:00:00.110 (5ms latency)
  ├─ Validates input: 1ms
  ├─ Calls DB at 10:00:00.111
  │  └─ DB receives at 10:00:00.113 (2ms latency)
  │     ├─ Query execution: 800ms
  │     └─ Returns at 10:00:00.913
  ├─ Receives response at 10:00:00.915 (2ms latency)
  ├─ Processes result: 2ms
  └─ Returns at 10:00:00.917
  
  Frontend receives: req_abc123 at 10:00:00.922 (5ms latency)
  └─ Total time: 822ms (most is DB query)
```

**Tools:** Jaeger, Datadog, CloudTrace, X-Ray

**How it works:**

1. Frontend generates trace ID: `trace_id=abc123`
2. Includes trace ID in API request header
3. API logs with trace ID, passes to DB
4. DB logs with trace ID
5. Central trace collector combines all logs by trace ID
6. Visualization shows the entire path

## Correlating Logs Across Services

Without tracing, logs are scattered:

```
Frontend logs:        [10:00:00] User request
API logs:             [10:00:00.005] Received request
DB logs:              [10:00:00.008] Query received
                      [10:00:00.800] Query complete
API logs:             [10:00:00.802] Response sent
Frontend logs:        [10:00:00.810] Rendered

Problem: How do you know these logs are for the SAME request?
```

**Solution: Include request ID in every log**

```
Frontend logs:        [10:00:00] req=abc123 User request
API logs:             [10:00:00.005] req=abc123 Received request
DB logs:              [10:00:00.008] req=abc123 Query received
                      [10:00:00.800] req=abc123 Query complete
API logs:             [10:00:00.802] req=abc123 Response sent
Frontend logs:        [10:00:00.810] req=abc123 Rendered

Now you can grep for "req=abc123" and see the full path.
```

## Canary vs. Production: Differential Debugging

You deploy a new version. Some users see old behavior, some see new.

```
Canary deployment (5% of traffic):
  Version A: 95% of users (old code)
  Version B: 5% of users (new code)
  
Symptom: P99 latency spiked for some users

Hypothesis: Version B is slower

Debugging:
  1. Compare metrics: Version A vs Version B
     A: P99 = 50ms, Error rate = 0.1%
     B: P99 = 500ms, Error rate = 2%
     → Confirmed: Version B is problematic
     
  2. Rollback: Disable version B, all users get version A
     P99 returns to 50ms
     
  3. Investigate: What changed in version B?
     Check: Commit between version A and B
     Found: New database query without index
     
  4. Fix: Add index, re-deploy version B
     Canary metrics now match version A
     
  5. Full rollout: Deploy to 100%
```

**Tools:** Feature flags (deploy dark), gradual rollout, metrics comparison

## Clock Skew: The Distributed Gotcha

Servers have different clocks. A request might have `created_at` > `updated_at`.

```
Service A (clock is 1 second slow):
  created_at = 10:00:01 (system time says 10:00:00, but A's clock is off)
  
Service B (clock is correct):
  updated_at = 10:00:00 (actual time)
  
Result:
  created_at (10:00:01) > updated_at (10:00:00)
  
Logic error:
  if created_at > updated_at: # This should never be true!
    raise error("Created after updated?!")
```

**Solution:** Use logical clocks or NTP time sync.

## Production Access: Debugging Without Debugger

You can't pause production to inspect variables. Instead:

**Approach 1: Structured Logging**

```python
# Bad logging
print(f"User {user} accessing {resource}")

# Good logging
logger.info("access_attempt", {
    "user_id": user.id,
    "user_name": user.name,
    "resource_id": resource.id,
    "resource_type": resource.type,
    "timestamp": datetime.now().isoformat(),
})
```

Structured logs are searchable (Elasticsearch, Datadog, etc.)

**Approach 2: Feature Flags for Debugging**

```python
if feature_flag('debug_slow_queries'):
    logger.debug(f"Query took {elapsed_ms}ms: {query}")
    
# Enable in production:
set_feature_flag('debug_slow_queries', True)
# Monitor logs
# Disable when done:
set_feature_flag('debug_slow_queries', False)

No deploy needed!
```

**Approach 3: Sampling**

```python
# Log 1% of requests (reduce noise)
if random.random() < 0.01:
    logger.info("request_detail", {...})
    
# Increase sampling if debugging:
if feature_flag('debug_mode'):
    sample_rate = 0.1  # 10%
else:
    sample_rate = 0.01  # 1%
```

## Rollback as Debugging Tool

Something broke in production. You don't have time to debug.

**Solution: Rollback first, debug later.**

```
10:05am: P99 latency spike detected
10:06am: Alert fires, oncall paged
10:07am: Identify last deploy (v123 → v124)
10:08am: Rollback to v123
10:09am: Metrics return to normal
         User impact resolved

Off-hours:
  10:00pm: Analyze what changed in v124
  11:00pm: Find the slow query
  12:00am: Fix the query
  1:00am: Test fix locally
  
Next day:
  9:00am: Re-deploy fixed version v125
```

## Interview: Distributed Debugging

**Q: "A distributed system is slow. You don't have source code access. How do you debug?"**

Weak:
```
"Check logs? Maybe add more servers? Restart services?"
(Vague, reactive)
```

Strong:
```
"Systematic approach:

1. Get one slow request (ID or timestamp)
   Trace that request through all services
   
2. Check distributed tracing (Jaeger, Datadog)
   - Which service is slow?
   - Is it latency or processing time?
   
3. Check logs for that request
   grep -r 'req_abc123' all_service_logs/
   See what each service did
   
4. Compare against good request
   Trace a fast request (same inputs)
   Compare traces → what's different?
   
5. Narrow to one service
   Once identified, use Layer 4+ tools on that service
   (debugger, profiler, etc.)
   
6. If still can't find root cause:
   Check deployment version
   Is this version slower than previous?
   → Rollback and debug off-hours
   
7. Prevent regression:
   Add monitoring alert for that metric
"
```

## Checklist

- [ ] Request traced (know which service is slow)
- [ ] Logs correlated (request ID in all logs)
- [ ] Metrics compared (version A vs B)
- [ ] Canary validated (5% before 100%)
- [ ] Rollback practiced (know how to revert fast)
- [ ] Clock sync checked (NTP running on all servers)
- [ ] Feature flags enabled (for debug logging)

## Common Mistakes

1. **No request ID.** Logs scattered, can't correlate.
2. **Debugging production with breakpoints.** Pauses service, impacts users.
3. **Clock skew ignored.** Timestamps are wrong, logic breaks.
4. **No metrics for comparison.** Deploy new version, but can't compare metrics (A vs B).
5. **Slow rollback process.** Something's broken, takes 30 min to rollback. Should be < 5 min.

