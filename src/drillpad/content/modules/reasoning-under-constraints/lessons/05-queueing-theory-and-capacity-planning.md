# Queueing Theory & Capacity Planning: Little's Law, Utilization, Tail Latency

## Overview

Most systems don't fail at average load—they fail at peak load. Queueing theory gives you the math to predict when. This lesson covers:

1. **Little's Law (L = λW):** Fundamental relationship between load, latency, and queue depth
2. **Utilization curve:** Why 99% CPU usage = unacceptable latency
3. **M/M/1 queueing model:** Exponential interarrival, exponential service time
4. **Tail latency (P99, P99.9):** Why you can't ignore outliers
5. **Overprovisioning:** How much headroom you actually need

---

## The Problem: Why Averages Lie

**Scenario: Database server**

```
Average load: 10K queries/sec
Average latency: 10ms

"We can handle 100K QPS, so we have 10x headroom!"

Reality:
  Time 0-10s: 10K QPS, 10ms latency
  Time 10s: Spike to 50K QPS (flash storm)
  
  What happens?
    - Queue builds (more arrivals than departures)
    - Latency climbs (queue delay)
    - At 50K QPS: queries pile up, latency → 500ms (50x worse!)
    - Cascade failures (timeouts, circuit breaker trips)
    - System recovers, then queue drains
```

**Key insight:** Peak latency depends on queue depth, not average load.

---

## Little's Law: L = λW

The fundamental equation of queueing:

```
L = λ × W

L: Average queue length (number of jobs in system)
λ: Arrival rate (jobs per second)
W: Average time in system (waiting + service)

Example:
  Queries arriving: λ = 10K QPS
  Average latency: W = 10ms = 0.01 seconds
  
  Average queue length: L = 10K × 0.01 = 100 jobs
  
Interpretation:
  At any moment, ~100 queries in flight (queued + executing)
  
Under spike (λ = 50K):
  If service time stays 10ms: L = 50K × 0.01 = 500 jobs
  Queue depth grows 5x!
```

**Rearranging Little's Law to solve for W:**

```
W = L / λ

If you can only handle L = 100 jobs in flight (due to memory constraints):
  At λ = 10K QPS: W = 100 / 10K = 0.01s = 10ms ✓
  At λ = 50K QPS: W = 100 / 50K = 0.002s = 2ms (IMPOSSIBLE!)
  
Actual behavior at 50K QPS with L_max = 100:
  - Requests arrive at 50K/sec
  - System can only handle 100 in flight
  - New requests either queued or rejected (backpressure)
  - Latency → infinity (or explicit timeout)
```

---

## Utilization Curve: The Cliff

**Utilization (ρ) = λ / µ**

```
λ: Arrival rate (requests/sec)
µ: Service rate (capacity, requests/sec)
ρ = λ / µ = utilization (0 to 1)

Example:
  Server capacity: µ = 100K QPS
  Actual load: λ = 10K QPS
  Utilization: ρ = 10K / 100K = 10% (very light)
  
  Under spike: λ = 50K QPS
  Utilization: ρ = 50K / 100K = 50% (moderate)
  
  Critical point: λ = 100K QPS
  Utilization: ρ = 100K / 100K = 100% (at capacity)
```

**Latency vs Utilization curve (M/M/1 queueing):**

```
Latency (seconds)
│
│                        ╱╱╱╱╱╱
│                      ╱╱
│                    ╱╱
│                  ╱
│                ╱
│              ╱
│            ╱
│          ╱
│        ╱
│      ╱
│    ╱
│  ╱
└─────────────────────────── Utilization (ρ)
0     10%   20%   50%   80%   90%   99%   100%

Key insight:
  At ρ = 50%: latency ≈ 2x average
  At ρ = 80%: latency ≈ 4x average
  At ρ = 90%: latency ≈ 10x average
  At ρ = 99%: latency ≈ 100x average (CLIFF)
```

**Real numbers (M/M/1 model):**

```
Service time: S = 10ms
Server capacity: µ = 100 QPS

At ρ = 50% (load = 50 QPS):
  W = S / (1 - ρ) = 10 / (1 - 0.5) = 20ms

At ρ = 90% (load = 90 QPS):
  W = S / (1 - ρ) = 10 / (1 - 0.9) = 100ms (10x service time!)

At ρ = 99% (load = 99 QPS):
  W = S / (1 - ρ) = 10 / (1 - 0.99) = 1000ms (100x service time!)

At ρ = 99.9% (load = 99.9 QPS):
  W = S / (1 - ρ) = 10 / (1 - 0.999) = 10,000ms (1000x service time!!)
```

**Key takeaway: Avoid ρ > 70%**

Operating at >70% utilization means:
- P99 latency = 10x average
- One hiccup in processing → massive queue buildup
- Zero headroom for traffic spikes
- Cascading failures (timeouts)

---

## M/M/1 Model: Exponential Arrivals & Service

**Assumptions:**

```
Arrivals: Poisson process (exponentially distributed interarrival times)
  - Some arrivals closely spaced, some far apart
  - Average: λ arrivals per second
  
Service: Exponential service time
  - Some jobs finish quick, some take longer
  - Average: 1/µ = service time
  
Single server (M/M/1)
  - One processor handling arrivals sequentially
  - Real: database query server
```

**M/M/1 formulas:**

```
Average queue length: L = ρ / (1 - ρ)

Average latency: W = 1/µ × 1/(1-ρ)  = S / (1-ρ)

Probability queue > n: P(Q > n) = ρ^(n+1)

Example (µ = 100 QPS, S = 10ms, ρ = 50%):
  L = 0.5 / (1 - 0.5) = 1 job in flight
  W = 10ms / 0.5 = 20ms average latency
  P(Q > 10) = 0.5^11 = 0.0005 (0.05% chance queue > 10)
```

**Real implications:**

```
Database with 1000 concurrent connections (worst case):
  If each connection needs 1 job slot: max 1000 concurrent requests
  If ρ = 50%: average latency = 20ms, max queue ~2-3
  If ρ = 90%: average latency = 100ms, max queue ~50 (connections might timeout)

Lesson: Even at 50% utilization, queue is growing (Little's Law)
```

---

## Tail Latency: P99, P99.9, P99.99

**Why P99 matters:**

```
Average latency: 10ms
P50 (median): 5ms
P99 (99th percentile): 100ms

Interpretation:
  1% of requests take 100ms (100x worse than median)
  
Real impact (1 second of traffic):
  1000 requests arrive per second
  10 requests (1%) take 100ms (vs 5ms)
  
  User experience:
    99% of requests: snappy (5ms)
    1% of requests: slow (100ms)
    
For user on web page:
  Page has 100 objects (images, CSS, JS)
  P99 = 100ms, 100 objects
  
  Probability all 100 objects < 10ms: 0.99^100 = 36%
  Probability all 100 objects < 100ms: nearly 100%
  
  Actual page load: slowest object = P99 at 100ms
  User sees 100ms+ latency (if P99 = 100ms)
```

**Tail latency formula (M/M/1):**

```
P(W > t) = ρ × e^(-(1-ρ) × µ × t)

Example (µ = 100 QPS, ρ = 50%, find P99):
  0.01 = 0.5 × e^(-(1 - 0.5) × 100 × t)
  0.02 = e^(-50t)
  ln(0.02) = -50t
  t ≈ 0.08 seconds = 80ms
  
  P99 latency ≈ 80ms (vs 20ms average)
  
At ρ = 90%:
  0.01 = 0.9 × e^(-(1 - 0.9) × 100 × t)
  0.011 = e^(-10t)
  t ≈ 0.5 seconds = 500ms
  
  P99 latency ≈ 500ms (vs 100ms average)
```

**Real P99 measurements (percentile degradation with load):**

```
Load (%)   P50    P99    P99.9   P99.99
50%        5ms    50ms   200ms   500ms
80%        8ms    150ms  1s      5s
90%        10ms   500ms  5s      50s
95%        15ms   1.5s   50s     (timeout)
99%        50ms   10s    (timeout) (timeout)

Lesson: ρ > 90% is unacceptable (P99.9 = seconds)
```

---

## Capacity Planning: How Much Overprovisioning?

**Rule of thumb: Provision for 2-3x peak load**

```
Observe peak load: λ_peak = 50K QPS
Provision capacity: µ = 150K QPS (3x)
Utilization at peak: ρ = 50K / 150K = 33%

At ρ = 33%:
  W = 10ms / (1 - 0.33) = 15ms (reasonable)
  P99 ≈ 50ms (acceptable for user experience)

If you provision for 2x only (µ = 100K):
  ρ = 50K / 100K = 50%
  W = 10ms / (1 - 0.5) = 20ms
  P99 ≈ 80ms (borderline)
```

**Real example: Black Friday capacity planning**

```
Normal day: 10K QPS
Expected Black Friday: 30K QPS (3x spike)

Mistake: Provision for 30K (2x headroom to 60K)
  ρ_black_friday = 30K / 60K = 50%
  But unexpected spike hits 50K (traffic surge)
  ρ = 50K / 60K = 83%
  P99 latency: 500ms (users complain)

Better: Provision for 100K (10K normal load)
  ρ_black_friday = 30K / 100K = 30%
  Even with spike to 50K: ρ = 50%
  P99 latency: 80ms (acceptable)
```

---

## Overprovisioning vs Cost

**Trade-off: Overprovisioning reduces latency but increases cost**

```
Example: Database server (costs $1000/month per 10K QPS capacity)

Scenario 1: Minimal provisioning (2x peak)
  Peak: 30K QPS, provision: 60K QPS capacity
  Cost: $6000/month
  P99 latency at peak: 200ms
  Risk: Traffic spike → overload → cascades

Scenario 2: Moderate provisioning (5x peak)
  Peak: 30K QPS, provision: 150K QPS capacity
  Cost: $15,000/month
  P99 latency at peak: 30ms
  Risk: Still some tail latency, but acceptable

Scenario 3: Aggressive provisioning (10x peak)
  Peak: 30K QPS, provision: 300K QPS capacity
  Cost: $30,000/month
  P99 latency at peak: 12ms
  Risk: Very safe, P99.99 still reasonable

Best practice: Scenario 2 (5x peak)
  Balance: Cost reasonable, latency acceptable, risk mitigated
```

---

## Q&A

**Q1: How do I know my current utilization?**

A: "Measure: λ = requests/sec (from logs), µ = capacity (benchmark or monitor). ρ = λ / µ. Monitor via: request count (CloudWatch), latency percentiles (New Relic, Datadog), queue depth. If P99 latency > 2x average or queue growing, you're approaching 70% utilization."

**Q2: Can I reduce latency by processing requests in batches?**

A: "Yes, but trade-off: batch processing increases latency variance (small batches wait for big batches). M/D/1 (deterministic service time) has lower P99 than M/M/1. Real example: batch 100 requests every 10ms = latency increases by 5ms for first request, but reduces queue buildup. Measure empirically."

**Q3: What if my traffic is bursty (not Poisson)?**

A: "M/M/1 assumes Poisson (most arrival processes are Poisson or Pareto, which is worse). If you have bursty traffic: use queuing simulation (discrete-event), or be more conservative (assume heavier tails). Rule: if traffic is bursty, provision for 1.5x more capacity than M/M/1 suggests."

**Q4: Should we use multiple servers instead of one large server?**

A: "Yes, usually. M/c/1 (c servers) has better tail latency than M/M/1 (single server). Example: 1 server @ 90% vs 10 servers @ 9% each = same throughput, but 10 servers have much lower P99. Cost usually similar or cheaper (horizontal scaling). Downside: more operational complexity."

**Q5: How do I handle traffic spikes (e.g., viral post)?**

A: "Three strategies: (1) Autoscaling (add servers when ρ > 70%). (2) Queue shedding (reject new requests, keep important ones). (3) Degraded mode (serve cached/stale data, reduce computation). Real systems use (1) + (2): scale up gradually, shed traffic if scale-up too slow."

---

## Real Example: Cascading Failure

```
Setup: 3-tier system (web → app → database)

Normal load:
  Web: 10K QPS, capacity 100K QPS (ρ = 10%)
  App: 10K QPS, capacity 50K QPS (ρ = 20%)
  Database: 10K QPS, capacity 30K QPS (ρ = 33%)

Traffic spike to 30K QPS:

Web layer:
  ρ = 30K / 100K = 30%, handles fine, latency ~12ms

App layer:
  ρ = 30K / 50K = 60%, starts queueing, latency ~25ms

Database layer:
  ρ = 30K / 30K = 100%, at capacity!
  Queries queue up, P99 latency → 5-10 seconds
  
App layer sees slow database:
  Connections block (waiting for database response)
  HTTP timeouts trigger (30 second timeout)
  App layer reaches capacity (ρ > 80%)
  App returns errors to web (connection refused)

Web layer:
  Sees errors from app, retry logic kicks in
  Retries increase load on app further
  ρ → 100%
  Web layer maxes out

Result: Cascading failure
  All three layers overloaded, system unresponsive
  Recovery: humans kill traffic, restart services

Lesson: Bottleneck tier (database) failed, propagated up
Solution: Provision database for 5x peak load (150K capacity)
  Then database ρ = 30K / 150K = 20%
  Cascading failure prevented
```

---

## Key Takeaways

1. **Little's Law (L = λW):** Fundamental relationship, not optional
2. **Utilization > 70% = unacceptable tail latency** (P99 > 10x average)
3. **M/M/1 model predicts P99 from ρ** (use formula or simulation)
4. **Tail latency matters more than average** (P99 = user experience)
5. **Provision for 5x peak load** (not 2x) for acceptable P99
6. **Bottleneck is system's weak link** (all tiers must be balanced)
7. **Monitor percentiles, not averages** (P50, P99, P99.9)

---

## Checklist

- [ ] Understand Little's Law and can apply it to your system
- [ ] Know utilization curve and cliff at ρ > 70%
- [ ] Can estimate P99 latency from service time and utilization
- [ ] Understand why averages don't predict tail latency
- [ ] Can identify bottleneck tier (highest utilization)
- [ ] Know how to provision for peak load (5x rule)
- [ ] Understand cascading failure mechanism (queue propagation)

## Common Wrong Answers

- "Average latency = user experience" ← No, P99 latency = user experience
- "99% utilization is safe" ← No, P99 latency is 100x, unacceptable
- "Little's Law doesn't apply to my system" ← Yes it does, it's universal
- "I'll just add more servers" ← Only works if bottleneck is one tier, not cascading
- "Overprovisioning is waste" ← No, cost of outage >> cost of overprovisioning
