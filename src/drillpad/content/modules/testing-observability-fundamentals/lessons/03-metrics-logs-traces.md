# Metrics vs Logs vs Traces: 3 Pillars of Observability

## The Observability Problem

Production is on fire. The pager woke you up at 3am.

You have 3 data sources to debug:
1. **Metrics:** Numbers (latency, throughput, CPU)
2. **Logs:** Text (what happened)
3. **Traces:** Paths (request flow through services)

## Metrics: The Big Picture

Metrics answer: "What happened to the system?"

```
CPU usage: 85%
Memory usage: 72%
Requests/sec: 5,000
P99 latency: 500ms
Error rate: 2%
Database connection pool: 95 active out of 100
```

### Metric Types

**Counters (always increasing)**
```
total_requests: 1,000,000 (never goes down)
total_errors: 50,000
```

**Gauges (can go up or down)**
```
active_connections: 50
memory_usage_bytes: 2GB
cpu_percent: 85%
```

**Histograms (distribution)**
```
request_latency: [100ms, 150ms, 200ms, 500ms, ...]
Summarized as P50, P99, P99.9
```

### Alerting with Metrics

```
Alert if CPU > 80% for 5 minutes
Alert if error_rate > 1%
Alert if P99_latency > 1000ms
```

**Pros:** Fast, actionable, clear trigger
**Cons:** Doesn't explain *why*

## Logs: The Details

Logs answer: "What happened in each operation?"

```
2025-01-15T12:34:56 INFO User login successful (user_id=123)
2025-01-15T12:34:57 ERROR Database connection timeout (timeout=30s)
2025-01-15T12:34:58 WARN Cache miss for key=user_123 (fallback to db)
```

### Structured Logs (Better)

```json
{
  "timestamp": "2025-01-15T12:34:56Z",
  "level": "INFO",
  "service": "api",
  "request_id": "req_abc123",
  "user_id": 123,
  "message": "User login successful",
  "duration_ms": 45
}
```

Structured logs are searchable and analyzable.

### Log Sampling (For Scale)

```
At 10,000 requests/sec:
Log every request: 10,000 * 1KB = 10MB/sec → not feasible

Better: Log 1 in 100 requests
Result: 100 logs/sec → 100KB/sec → manageable

But miss 99% of issues!

Best: Log all errors + 1% of successes
Result: Errors always logged, successes sampled
```

## Traces: The Timeline

Traces answer: "What was the request path?"

```
Request arrives at API
  → API calls User Service (45ms)
  → User Service calls Auth (10ms)
  → Auth calls Cache (1ms)
  → Cache miss, hits Database (30ms)
  → Returns to Auth
  → Returns to User Service
  → User Service returns to API
  → API returns to client (Total: 87ms)
```

### Trace Structure

```
Trace ID: abc123def456

Spans (each operation):
  Span 1: API receives request (0-87ms)
    Span 1.1: Call User Service (5-50ms)
      Span 1.1.1: Call Auth (10-20ms)
        Span 1.1.1.1: Check cache (10-11ms)
        Span 1.1.1.2: Hit database (11-41ms)
```

Shows exact latency and bottleneck.

### When to Use Traces

```
Latency is high (P99 = 500ms)
Logs don't explain why
Trace shows:
  - Auth service: 400ms (bottleneck!)
  - Everything else: <100ms
```

Now you know what to optimize.

## Integration: How They Work Together

### Scenario: Error Rate Spike

**Metric alert:** Error rate jumped from 1% → 5%

**Check logs:** 
```
ERROR Database connection pool exhausted
ERROR Failed to connect to user_service
```

**Drill into traces:**
```
User requests:
  → API (success)
  → User Service timeout (30s, then circuit breaker)
  → Fallback endpoint (success)
  
DB requests:
  → API (success)
  → DB connection (45/100 pooled)
  → Retry (60/100 pooled)
  → Fail (pool exhausted)
```

**Root cause:** User Service is slow → connections pile up → DB pool exhausted → cascading failures

## Tools

| Tool | Purpose | Type |
|---|---|---|
| **Prometheus** | Metrics collection | Metrics |
| **Datadog** | All three | Commercial SaaS |
| **ELK Stack** | Logs | Open source |
| **Jaeger** | Traces | Open source |
| **New Relic** | All three | Commercial SaaS |

## Interview Pattern: Diagnosing Production Issues

```
Q: "Your service has high latency (P99=2s).
   Users are complaining. Debug it."

Weak answer:
  "Check CPU and memory metrics"
  (❌ Doesn't diagnose root cause)

Strong answer:
  "Use three data sources strategically:
  
  1. Metrics (quick check):
     - CPU: 45% (not maxed)
     - Memory: 60% (healthy)
     - Requests/sec: 1000 (normal)
     - P99 latency: 2000ms (confirmed)
     - Error rate: normal
     
     Conclusion: Not a resource issue
  
  2. Logs (find the culprit):
     Filter logs: timestamp > now - 5 minutes
     Search: 'error', 'timeout', 'fail'
     
     Pattern: 'Database timeout' every ~200 requests
     DB is slow, not fully down (some requests succeed)
  
  3. Traces (find bottleneck):
     Sample 100 slow requests (P99)
     Measure span times:
       API: 100ms
       DB query: 1900ms (bottleneck!)
       Cache: 1ms
     
     Why? One SQL query is slow (missing index)
     Or: DB connection is slow (network latency to other region)
  
  4. Root cause:
     - Database query is 1900ms
     - Likely: Missing index on frequently-searched column
     - Or: Database in different region (network latency)
  
  5. Fix:
     - Add index to column
     - Monitor latency (should drop to 100ms)
     - If network latency: replicate DB closer
  
  6. Prevention:
     - Add alert: 'DB latency > 500ms'
     - Automated index recommendations
     - Query slow log (log queries > 100ms)
     - Test queries with EXPLAIN PLAN before deploy"

Why this signals good judgment:
  - You used all three data sources
  - You narrowed scope (not a resource issue)
  - You found the bottleneck (DB, not API)
  - You would prevent in future (alerts, monitoring)
```

## Observability Checklist

- [ ] Metrics: CPU, memory, latency P50/P99/P99.9, throughput, error rate
- [ ] Alerts: CPU >80%, error_rate >1%, latency >SLA
- [ ] Logs: Structured JSON, include request_id, searchable
- [ ] Traces: Sample all errors, 1% of successes, trace latency > 100ms
- [ ] Dashboard: P99 latency, error rate, key metrics visible
- [ ] Runbooks: For each alert, what to do
- [ ] On-call: Someone responds to alerts

## What This Signals

- You've debugged production issues
- You use data strategically (metrics → logs → traces)
- You understand each tool's purpose
- You design monitoring proactively (not after incident)
