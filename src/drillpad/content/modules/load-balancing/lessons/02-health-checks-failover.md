# Load Balancing: Health Checks, Failover & Circuit Breakers

## Health Checks: Detecting Dead Servers

Without health checks, load balancer sends traffic to dead servers.

```
Server 1: alive
Server 2: dead (OOM, hung process)
Server 3: alive

Without health check:
  Round-robin: Server 1, Server 2 (timeout!), Server 3, Server 1, Server 2...
  Users hit Server 2 → 30s timeout → retry → hit Server 3 → success (slow)

With health check (every 5s):
  LB polls: GET /health
  Server 2: no response → marked DOWN
  Round-robin: Server 1, Server 3, Server 1, Server 3...
  Server 2 marked DOWN, traffic diverts
```

## Health Check Implementation

**Passive health check:** Watch responses
```
If server returns 500+ errors for N consecutive requests
→ Mark DOWN, divert traffic
Problem: users suffer before detection
```

**Active health check:** LB polls
```
Every 5 seconds:
  LB sends: GET /health
  Expected: 200 OK + {"status": "ok"}
  
  If timeout or error:
    Fail count++
  If 3 consecutive fails:
    Mark DOWN
    
When server recovers:
  2 consecutive success → mark UP
  Divert traffic back
```

## Graceful Shutdown

Abrupt shutdown loses in-flight requests.

```
Old way (bad):
  SIGKILL server
  In-flight request 1: lost
  In-flight request 2: lost
  Load balancer retries, hits next server
  
  User sees: ~1-5s delay while LB detects death + retries

Better way (graceful):
  1. SIGTERM server
  2. Server stops accepting NEW requests
  3. Server waits for in-flight requests to finish
  4. Server exits (0 outstanding)
  5. Load balancer detects health check fail
  6. LB marks DOWN, diverts new traffic
  7. User sees: zero errors
```

## Real Example: Service Mesh (Istio/Envoy)

```
Kubernetes pod shutting down:
  1. Preemption signal (30s warning)
  2. Pod runs terminationGracePeriodSeconds (default 30s)
  3. Server stops accepting requests from Envoy sidecar
  4. Envoy health check: no response → mark DOWN
  5. Envoy drains existing requests (~10-15s)
  6. Pod exits

Without coordination:
  → Cold 20-30s restarts
  
With graceful shutdown:
  → Zero error rates
```

## Failover Strategies

**Fail-open (optimistic):**
```
Server marked DOWN
→ LB still sends traffic (but with reduced quota)
→ Hope it recovers

Used for: non-critical services
Risk: cascading failure if server is really dead
```

**Fail-closed (pessimistic):**
```
Server marked DOWN
→ LB STOPS sending traffic completely
→ Remaining servers overloaded (may cascade)

Used for: critical path
Risk: if all servers fail health check, all traffic lost

Better: health check timeout > actual timeout
  So LB marks DOWN before client sees timeout
```

## Circuit Breaker Pattern

Similar to health checks but application-level.

```
State machine:

CLOSED (healthy):
  Pass requests through
  If error_rate > threshold or latency > p99_limit
    → Go to OPEN

OPEN (circuit broken):
  Reject requests immediately (fail fast)
  Try to recover: go to HALF_OPEN after N seconds

HALF_OPEN (testing):
  Send limited requests (~10)
  If succeed: go to CLOSED
  If fail: go back to OPEN
```

**Real example: Stripe rate limiting**

```
Your service calls Stripe API
→ Stripe rate limit reached (429)
→ Stripe says: "Retry-After: 60s"

Naive (bad):
  Keep hammering Stripe API every 100ms
  → Stripe further throttles
  → Cascades

Circuit breaker (good):
  First 429: increment error count
  After 3 errors: OPEN
  Fail fast: "Stripe is overloaded, try again later"
  Wait 60s, go HALF_OPEN
  Send 1 request
  If success: go CLOSED
```

## Interview Questions

**Q: "Your service has 3 replicas. One gets stuck (memory leak, but doesn't crash). What happens?"**

A: "Without health checks: users hitting replica #1 timeout at 30s, retry, hit #2/#3, succeed. With active health checks, LB detects no response within 3-5s, marks DOWN, traffic diverts before user timeout. With graceful shutdown, replica #1 stops accepting requests but finishes in-flight, preventing 30s hangs."

**Q: "How would you handle a cascading failure in a Kubernetes cluster where all pods suddenly get unhealthy?"**

A: "Health check design is critical. If health check requires downstream dependency (e.g., check Redis), then Redis failure → all pods marked DOWN → all traffic lost. Solution: health check only checks local state (memory, CPU, file descriptors), not dependencies. For dependencies, use bulkheads: separate pool of instances with circuit breaker per dependency."

**Q: "Your monitoring shows 100ms spike in p99 latency. Load balancer says all backends are healthy. Why?"**

A: "Possible causes: (1) slow start ramp-up on one backend after restart; (2) GC pause on JVM backend; (3) packet loss on that backend's network path (TCP retransmit); (4) health check latency is low but actual request latency is high (health check doesn't reflect real workload — e.g., GET /health is cached, but POST request path is slow). Fix: health check should exercise realistic code paths, or use percentile-based health checks (reject if p99 > threshold)."

**Q: "Design a load balancer health check for a trading system where latency matters."**

A: "Active check every 1-2s (not 5s), expect response within 50ms. If latency > 100ms, count as fail (even if 200 OK). After 2 fails, mark DOWN. Use fail-closed: if all backends fail health check, reject new requests immediately with 503 (rather than trying) to prevent cascading timeouts. Graceful shutdown with 5s drain: in-flight requests finish within timeout, LB diverts new traffic while draining."
