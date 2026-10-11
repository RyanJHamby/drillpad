# Load Testing & Chaos Engineering: When to Use

## Load Testing: Pushing to Limits

Goal: Understand how system behaves under stress.

```
Normal day: 100 requests/sec (healthy)
Black Friday: 10,000 requests/sec (how much capacity do we have?)
```

### Load Testing Phases

**Phase 1: Baseline (Normal load)**
```
100 req/sec for 5 minutes
Baseline latency: P50=50ms, P99=200ms
```

**Phase 2: Ramp up (Gradually increase)**
```
100 → 500 → 1000 → 5000 → 10000 req/sec
At each step, measure latency
Find breaking point
```

**Phase 3: Stress (Beyond capacity)**
```
10,000 req/sec (beyond capacity)
Where does it break?
- CPU maxes out?
- Memory fills?
- Connection pool exhausted?
- Database overloaded?
```

**Phase 4: Soak (Long duration)**
```
5,000 req/sec for 24 hours
Does latency degrade over time?
Memory leak? File descriptor leak?
```

### Tools

```
Apache JMeter: Simple, GUI-based
Locust: Python-based, scriptable
k6: Modern, cloud-based
Vegeta: Command-line, simple
```

### Realistic Baseline

```python
# NOT realistic (every request is identical)
for i in range(10000):
    requests.get('/api/users/1')

# Realistic (mix of operations)
operations = [
    ('/api/users', 'GET'),
    ('/api/users', 'POST'),
    ('/api/users/1', 'GET'),
    ('/api/users/1', 'PUT'),
]
for i in range(10000):
    op = random.choice(operations)
    requests.request(op[1], op[0])
```

## Chaos Engineering: Introducing Failures

Goal: Test how system handles failures.

### Failure Types

**Network failures:**
```
Latency: 100ms → 1000ms (slow network)
Packet loss: 10% of requests lost
Timeout: Connection drops after 30s
```

**Service failures:**
```
Downstream service 500s
Database unavailable
Cache miss (memcached down)
```

**Resource failures:**
```
CPU overload (99% usage)
Memory exhausted
Disk full
```

### Chaos Engineering Tools

```
Gremlin: Closed source, paid
Chaos Mesh: Open source, Kubernetes
LitmusChaos: Open source, Kubernetes
PacBot: Simple failure injection
```

### Example: Database Unavailability

```
1. Baseline: All requests succeed in 50ms
2. Inject failure: Disable database
3. Observe: Requests timeout or fail
4. Measure: How many requests are rejected?
              What's the error rate?
              Do retries help?
5. Verify: Alerts trigger?
           Do people get notified?
           Does auto-recovery work?
```

## When to Load Test vs Chaos Engineer

| Scenario | Test Type | Why |
|---|---|---|
| **New service launch** | Load test | Know capacity limits |
| **Black Friday prep** | Load test | Ensure you can handle spike |
| **Database failover** | Chaos | Does failover work? |
| **Network partition** | Chaos | How does system degrade? |
| **Production alert** | Chaos | Verify alert triggers |
| **Scale out** | Load test | New servers help? |

## Interview Pattern: Reliability Testing

```
Q: "You're launching a service that's expected to handle
   10M requests on day 1. How do you ensure reliability?"

Weak answer:
  "Run load tests locally"
  (❌ Local ≠ production)

Strong answer:
  "Multi-stage testing:
  
  1. Baseline load test (local):
     - 1000 req/sec, measure latency
     - P50, P99, P99.9
     - Identify bottlenecks
  
  2. Ramp test (staging environment):
     - Match production hardware
     - Ramp from 1K → 10M req/sec
     - Find breaking point
     - Measure: CPU, memory, connection pools
  
  3. Soak test (staging):
     - Run 5M req/sec for 24 hours
     - Check for memory leaks
     - Monitor for cascading failures
  
  4. Chaos test (staging):
     - Inject database failure → verify failover
     - Inject network latency → verify timeouts
     - Kill a server → verify recovery
     - Hit rate limit → verify graceful degradation
  
  5. Dry run (production-like):
     - Final test in prod-identical environment
     - Hit expected traffic patterns
     - Verify monitoring + alerts work
     - Verify on-call team is paged correctly
  
  6. Day 1 plan:
     - Deploy with monitoring
     - Have runbook for scaling up (add servers)
     - Alert thresholds: CPU >80%, latency >500ms, errors >1%
     - Team on-call (even though we tested)
  
  7. Post-launch:
     - Continuous monitoring
     - Weekly chaos tests (keep failover skills sharp)
     - Quarterly soak tests
  
  Cost: Testing takes 2-3 weeks
  Benefit: Avoid pager at 3am on day 1"

Why this signals good judgment:
  - You tested at multiple scales
  - You simulated production environment
  - You included chaos (failure scenarios)
  - You had a post-launch plan
```

## Common Load Testing Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| **Test only happy path** | Miss failure modes | Include errors, timeouts |
| **Use toy data** | Unrealistic performance | Use prod-like data size |
| **Load test on dev machine** | Numbers are meaningless | Test on prod-identical hardware |
| **No chaos testing** | Assume failover works | Actually test failovers |
| **Test once, then forget** | System degrades over time | Quarterly re-testing |
| **No monitoring** | Don't know what broke | Instrument for load tests |

## What This Signals

- You've scaled systems (load testing is real experience)
- You understand failure modes (chaos testing)
- You test before launch (not just hoping)
- You have post-launch plan (monitoring + runbooks)
