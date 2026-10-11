# Failure Diagnosis: Graceful Degradation Playbook

## The Core Question

```
When system overloaded, what should you:
  1. Keep? (core functionality)
  2. Degrade? (cache, async)
  3. Drop? (non-critical)

Wrong strategy: Overload everything equally
  → All features slow to unusable
  
Right strategy: Protect critical, degrade non-critical
  → Core features work, extras fail gracefully
```

## Decision Framework: Priority Tiers

```
Tier 1 (CRITICAL - Never degrade):
  - Payments (money at stake)
  - Authentication (can't work without it)
  - Core business logic (product differentiator)
  
Tier 2 (IMPORTANT - Degrade if needed):
  - Recommendations (nice to have)
  - Analytics (can queue for later)
  - Non-critical APIs
  
Tier 3 (NICE-TO-HAVE - Drop if needed):
  - Metrics collection
  - Tracing
  - Non-critical logging
  - A/B testing metadata
```

## Degradation Strategies (In Order)

### Strategy 1: Async Queueing (Low Impact)

```
Before (synchronous):
  POST /api/purchase
    → validate
    → charge card (5ms)
    → send confirmation email (10ms) ← SLOW
    → update analytics (5ms) ← SLOW
    → return response (30ms)

After (async degrade):
  POST /api/purchase
    → validate
    → charge card (5ms)
    → queue: {send email, update analytics}
    → return response (5ms) ← 6x faster
    
  Background: Process queued tasks when load is low
  
Cost: Eventual consistency (email sent 1 sec later, not 30ms)
Benefit: Can accept 6x more traffic
```

### Strategy 2: Cache & Stale Responses (Moderate Impact)

```
Before:
  GET /api/recommendations
    → query database
    → ML inference (1000ms)
    → return fresh recommendations

Overload scenario:
  GET /api/recommendations
    → query cache (5ms)
    → if miss: queue for async ML
    → return stale recommendations (from yesterday)
    
User sees: Yesterday's recommendations, not today's
Cost: Staleness (1 day old)
Benefit: Can serve cache for 1000x load
```

### Strategy 3: Request Rejection (Severe Impact)

```
Before:
  - Accept all requests
  - Queue fills, everything slow
  
After:
  - If queue > threshold: Return 429 (Too Many Requests)
  - Client backs off
  - Your queue drains
  
Cost: Some requests fail with 429
Benefit: System stays alive (doesn't crash)
```

## Real Example: E-commerce Surge (Black Friday)

```
Normal: 1000 QPS
Black Friday: 10,000 QPS incoming

System capacity: 2,000 QPS
Oversubscription: 5x normal

Degradation strategy (in order):

1. Drop metrics (5% load reduction)
   - Stop collecting metrics during surge
   - Still collect errors
   
2. Async analytics (10% load reduction)
   - Queue page views, clicks for later
   - Process them off-peak
   
3. Disable recommendations (30% load reduction)
   - Show cached/static recommendations
   - Don't run fresh ML inference
   - Or return generic "popular items"
   
4. Reduce logging (5% load reduction)
   - Log only errors, not all requests
   
5. Cache aggressively (40% load reduction)
   - Increase TTL on product pages
   - Use stale cache if fresh version slow
   
6. Backpressure (final resort)
   - If queue > 10,000: Return 429
   - Auto-retry handles it
   
Total reductions: 5% + 10% + 30% + 5% + 40% = 90%
System capacity: 2,000 QPS
Can now handle: ~3,800 QPS (close enough)
Deficiencies covered by auto-retry + backoff

Outcome:
  - Core checkout: Works (slow, but works)
  - Recommendations: Cached (stale, but fast)
  - Analytics: Queued (delayed, but collected)
  - Metrics: Dropped (okay for temporary surge)
```

## Implementation: Feature Flags for Degradation

```
Configuration:
  degradation:
    enabled: true
    queue_threshold: 5000  # Start degrading at this queue depth
    levels:
      1:
        - drop_metrics: true
        - drop_tracing: true
      2:
        - async_analytics: true
        - disable_recommendations: true
      3:
        - cache_aggressive: true
        - increase_cache_ttl: 3600  # 1 hour instead of 5 min
      4:
        - return_429: true
        - reject_non_critical: true

At runtime:
  if queue_depth > 10000:
    enable degradation level 4
  elif queue_depth > 5000:
    enable degradation level 3
  # etc
```

## Interview Answer

**Q: "Your system is experiencing 10x traffic. You can't scale horizontally in time. How do you stay alive?"**

```
"Graceful degradation strategy:

Tier 1 (protect):
  - Checkout (money at stake)
  - Authentication
  
Tier 2 (degrade):
  - Recommendations (cache yesterday's)
  - Personalization (use defaults)
  - Real-time analytics (queue for later)
  
Tier 3 (drop):
  - Metrics collection
  - Non-critical logging
  
Specific changes:
  1. Async queue: Recommendations (1000ms → 5ms)
  2. Cache aggressive: Increase TTL 5min → 1hr
  3. Drop metrics: Save 5% CPU
  4. Return 429: If queue overflowing
  
Result:
  - Checkout: Works (still available)
  - Experience: Degraded (cached recommendations)
  - Availability: 99%+ (system doesn't crash)
  
Timeline:
  - Minute 0: Detect surge, enable degradation
  - Minute 5: Scale horizontally (new servers online)
  - Minute 30: Back to normal (full features)
"
```

## Graceful Degradation Checklist

**Design time:**
- [ ] What's Tier 1? (can't degrade)
- [ ] What's Tier 2? (can queue async)
- [ ] What's Tier 3? (can drop)

**Implementation:**
- [ ] Async queue for Tier 2 work
- [ ] Cache strategy for stale responses
- [ ] Metrics flag (can disable)
- [ ] Circuit breaker (fail fast)
- [ ] 429 backpressure (don't overload)

**Testing:**
- [ ] Simulate 10x load
- [ ] Verify degradation triggers correctly
- [ ] Measure latency at each degradation level
- [ ] Test recovery (degrade → normal transition)

