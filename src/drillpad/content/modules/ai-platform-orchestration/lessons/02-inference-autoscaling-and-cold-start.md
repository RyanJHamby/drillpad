# Inference Autoscaling: Signals, Cold Start, Warm Pools, Scaling to Zero

## The Problem

Your inference service has variable traffic: 100 req/sec at 3 PM, 10 req/sec at 3 AM. You have 10 GPU pods running 24/7. At 3 AM, 9 of them are idle, burning electricity and money.

```
Cost analysis:

10 GPU pods, 24 hours/day:
  GPU cost: $2.50/hour × 10 pods × 24h = $600/day
  
If you could scale to 1 pod at 3 AM:
  Scale to 1 pod for 8 hours: $2.50 × 1 × 8 = $20
  Scale to 10 pods for 16 hours: $2.50 × 10 × 16 = $400
  Total: $420/day (30% savings)

But scaling to zero means:
  Cold start (model load): 30 seconds
  User request waits: 30 seconds (unacceptable)
  
Trade-off: Save 30% cost but accept 30s latency 5x/day?
```

**Why this matters:** Autoscaling is critical for cost-effective AI infrastructure. Understanding the signals, cold start costs, and warm pools is essential for production systems.

---

## First Principles: Autoscaling Signals

What metric triggers "scale up" or "scale down"?

**Option 1: CPU/Memory Utilization**

```
Auto-scale rule: If CPU > 70% for 1 min, add pod

Problem with AI workloads:
  - GPU utilization might be 5% (waiting for network I/O)
  - Or 100% (saturated, can't accept more requests)
  - CPU doesn't correlate to load for GPUs
```

**Option 2: Queue Depth (Requests Waiting)**

```
Metric: Number of requests in queue

Rules:
  If queue_depth > 50 for 1 min → add pod
  If queue_depth < 5 for 5 min → remove pod

Example:
  t=0: 1 req/sec, queue=0
  t=10: spike to 100 req/sec, queue grows
  t=15: queue_depth=50 → trigger scale-up
  t=25: new pod ready → process queue
  t=30: queue_depth < 5 → scale down

Advantage: Directly measures waiting load
Problem: Reaction time (scale-up takes 30s, but pod might be full in 10s)
```

**Option 3: Concurrency (Requests In-Flight)**

```
Metric: Number of requests being processed

Rule: If concurrency > max_per_pod × 0.8 → add pod

Example:
  Pod capacity: 8 concurrent requests
  Current: 6 in-flight
  Threshold: 8 × 0.8 = 6.4
  
  New request arrives (7 in-flight):
  7 > 6.4 → trigger scale-up
  
Advantage: Proactive (scale before we're full)
Problem: Need to know pod capacity (may vary by model)
```

**Diagram: Autoscaling Signals Over Time**

```
Traffic pattern: Peak 3PM, low 3AM

         Requests/sec
             |    ▲ Peak
             |   /|
             |  / |
        100 | /  |
             |   |
        50  |    |
             |    \
        10  |     \
             |      ▼ Trough
             |____________________ time
            12AM  3AM  6AM  12PM  3PM  6PM  12AM

Scaling response:

Pods   |
  10   |     ╭─────────────╮
       |    ╱              ╲
   5   |   ╱               ╲
       |  ╱                 ╲__
   1   |_╱                      ╲___
       |____________________________
         12AM  3AM  6AM  12PM  3PM

Delay: Scale-up lags demand by ~5-10 min (pod creation + startup)
```

---

## Cold Start Cost

When scaling from 0 to 1 pod (or from 1 to 2), there's startup latency:

```
Timeline for cold start (scale from 0 → 1 pod):

t=0: Autoscaler detects queue_depth > threshold
     Triggers scale-up: "Create 1 new pod"

t=1-5s: Kubernetes scheduler finds node, reserves resources
        Container image downloaded/extracted
        
t=5-10s: Container starts, application initialization
        
t=10-30s: Model loading (weights from disk/network to GPU)
         H100 GPU: 80GB model at 40 GB/s = 2 seconds
         But: S3 download (network) = 10-20 seconds
         Total: 30 seconds typical
        
t=30s: Pod ready to accept requests
       First request can be served
       Latency to user: 30s (unacceptable!)

Cost per cold start:
  Pod creation: ~$0.01 (negligible)
  Requests during startup: Queued, delayed
  User experience: 30s wait time
```

**Diagram: Cold Start vs Warm Start**

```
Request arrives at different times:

Scenario A: Warm pod already running
  t=0: Request arrives
  t=0.1: Pod processes (forward pass)
  t=0.2: Response sent
  Latency: 200ms (acceptable)

Scenario B: Scale from 0 pods
  t=0: Request arrives, queue = 1
  t=0-30s: Autoscaler detects, creates pod
           Pod starts, loads model
  t=30s: Pod ready
  t=30.2s: Pod processes request
  Latency: 30.2s (unacceptable!)
```

---

## Warm Pools (Pre-warming)

Solution: Keep idle pods ready to reduce cold start:

```
Warm pool strategy:

Rule 1: Minimum pods (always running)
  Set min_pods = 2 (always have 1 backup)
  Cost: 2 × $2.50/hr = $5/hr
  Benefit: If traffic spike, first pod doesn't cold start

Rule 2: Over-provision during peak
  Peak traffic: 100 req/sec
  Pod capacity: 10 req/sec
  Need: 10 pods
  Target: 12 pods (20% over-provision)
  
  Cost of over-provision:
    2 extra pods × $2.50/hr = $5/hr
    But: Handles bursty traffic without cold start
    And: Can handle node failures

Rule 3: Predictable scaling (schedule-based)
  Monday-Friday 8AM-6PM: min=10 pods
  Nights/weekends: min=1 pod
  
  Example: 
    Cost without schedule: $2.50 × 10 × 24 = $600/day
    Cost with schedule: $2.50 × (10×10 + 1×14) = $285/day (52% savings)
```

**Trade-off: Cost vs Latency**

```
No warm pool:
  Cost: Low (scale to 0)
  Latency: High (30s cold start when needed)
  Use case: Non-critical batch jobs

Minimal warm pool:
  Cost: Medium ($50-100/day warm buffer)
  Latency: Good (first pod handles request)
  Use case: Online serving (production)

Aggressive warm pool:
  Cost: High ($200-300/day)
  Latency: Excellent (instant response)
  Use case: Trading systems, mission-critical
```

---

## Scaling to Zero

When is it safe to scale to 0 pods?

```
Safe scenarios:
  1. Non-critical service (internal monitoring dashboard)
  2. Predictable quiet periods (no traffic 3AM-6AM)
  3. Batch processing (can wait for cold start)
  4. Serverless model (charge user for cold start time)

Dangerous scenarios:
  1. Unpredictable traffic spikes
  2. Mission-critical service (financial systems)
  3. Time-sensitive requests (trading)
  4. User-facing where 30s latency is unacceptable

Example: Trading system

  Scaling to 0 with minimum wait time:
    Market opens (8:30 AM EST)
    Autoscaler detects traffic → scale from 0 → 1
    Cold start: 30 seconds
    But market is now open and orders are being placed
    Our model is not ready yet (miss opportunities)
    
  Better: Always-on minimum (min_pods=1)
    Cost: $2.50/hr, runs 24/5 = $300/week
    Benefit: Ready instantly
    Better than missing 30s of market at 1000x cost
```

---

## Failure Scenario: Scaling Cascade

```
Scenario: E-commerce site, flash sale starts

t=0: 10 req/sec
t=1: 100 req/sec (sale announced)
     Queue depth > threshold
     Autoscaler triggers: scale from 2 → 5 pods

t=5s: 50 pods pending (Kubernetes creating them)
     Queue still growing (current pods can't keep up)
     Autoscaler thinks more pods needed
     Triggers: scale from 5 → 20 pods

t=30s: 100 pods pending
     Node pool depleted
     Kubernetes can't schedule new pods
     Queue backs up indefinitely
     Requests timeout
     
Result: 100 pods created for brief spike
Cost: $2.50 × 100 × 30min = $125 (!)

Root cause: Autoscaler didn't account for scale-up latency
The metric (queue_depth) was already high from previous scaling
Autoscaler kept adding pods without waiting for them to be ready
```

**Prevention:**
- Rate limit scaling: (max 1 scale event per 5 min)
- Target queue depth lower (don't wait for 50 items)
- Use predictive scaling (pre-warm before sale)

---

## Interview Pattern: Autoscaling Design

```
Q: "You run LLM inference serving 100K users globally.
   Peak traffic: 100K req/min (USA business hours).
   Off-peak: 1K req/min (nighttime).
   Model: 80GB (30s cold start).
   Pod: 10 req/sec capacity, $2.50/hr cost.
   
   Design autoscaling for cost-effectiveness without sacrificing latency."

Weak answer:
  "Scale from 0 to N pods based on queue depth"
  (❌ Ignores cold start, will be slow during spikes)

Strong answer:
  "Autoscaling strategy with warm pools:
  
  1. Calculate capacity needs:
     Peak: 100K req/min = 1,667 req/sec
     Pod capacity: 10 req/sec
     Pods needed: 167 pods for peak
     
  2. Warm pool strategy:
     Min pods: 10 (always on, $250/day)
     Max pods: 200 (safety limit)
     Target: Queue depth < 5 req/sec (90% utilization)
     
  3. Scaling rules:
     a) Scale-up: if queue_depth > 5 for 1 min → +10 pods
     b) Scale-down: if queue_depth < 1 for 5 min → -5 pods
     c) Rate limit: max 1 scale event per 3 min
     d) Max cool-down: don't scale-down within 10 min of scale-up
     
  4. Predictive scaling (schedule-based):
     Monday-Friday 8AM-7PM: min=100 pods
     Off-peak: min=10 pods
     
     Rationale: Cost is predictable
       Peak 11 hrs × 100 pods × $2.50 = $2,750
       Off-peak 13 hrs × 10 pods × $2.50 = $325
       Daily: ~$3,000
     
     Without schedule-based: $2.50 × 170 (avg) × 24 = $10,200
     Savings: 70% with predictive scaling
     
  5. Cold start handling:
     - 30s cold start is unavoidable
     - But: Min=10 pods means first request doesn't cold start
     - For spike: first 10 req/sec handled instantly
     - Queue builds, autoscaler scales
     - By time 100th pod is ready, queue has dissipated
     
  6. Cost-latency curve:
     Option A: No warm pool ($1,500/day, 30s latency for spikes)
     Option B: min=10 pods ($3,000/day, 100ms latency)
     Option C: min=50 pods ($4,000/day, 10ms latency)
     
     Choose B: 2x cost, but eliminates cold-start latency
     
  7. Monitoring:
     - Alert if max_pods reached (capacity limit)
     - Alert if scale-up rate > 20 pods/min (cascade risk)
     - Track pod startup latency (should be ~30-40s)
     - Track queue depth (should stay < 5)
"

Why this signals good judgment:
  - You calculated actual pod counts (100K req/sec → 167 pods)
  - You understand cold start cost (30s is real)
  - You have warm pool strategy (min=10)
  - You use predictive scaling (schedule-based)
  - You rate-limit scaling (prevent cascade)
  - You measure cost-latency tradeoff
```

---

## Checklist: Production Autoscaling

- [ ] Autoscaling metric defined (queue depth, concurrency, or custom)
- [ ] Min/max pods configured (realistic for workload)
- [ ] Cold start time measured (model load time)
- [ ] Warm pool size calculated (cost-latency tradeoff)
- [ ] Rate limiting in place (prevent cascade)
- [ ] Predictive scaling considered (peak hours pre-warmed)
- [ ] Monitoring: scale event rate, queue depth, pod startup latency
- [ ] Alerting: if max_pods reached or cascade detected
- [ ] Cost tracked: total pod-hours vs cost savings

## Common Wrong Answers

1. **"Scale to 0 pods when idle to save cost"**
   - 30s cold start may be unacceptable
   - Warm pool usually better ROI

2. **"Use CPU % for autoscaling"**
   - Doesn't work for GPU workloads
   - Use queue depth instead

3. **"Add pods aggressively (scale +20 at once)"**
   - Risk of cascade (100s of pods pending)
   - Better: +2-5 per event, retry every 1 min

4. **"Scaling is automatic, don't need to monitor"**
   - Autoscaler can get stuck (e.g., max_pods reached)
   - Always monitor queue depth, pod count, latency

5. **"Cold start doesn't matter"**
   - 30s is unacceptable for time-sensitive workloads
   - Plan for it (warm pools, predictive scaling)
