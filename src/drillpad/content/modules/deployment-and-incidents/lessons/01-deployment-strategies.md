# Deployment Strategies - Blue-Green, Canary, Rolling, Feature Flags

## The Deployment Problem

You deploy new code. Two things can happen:
1. **Good:** Feature works, users love it
2. **Bad:** Bug happens, traffic drops, business loses money

How do you minimize the downside?

## Strategy 1: Blue-Green Deployment

```
Blue (current):   v1.2.3, handling all traffic
Green (new):      v1.2.4, tested, waiting

Deploy:
1. Route 0% to green
2. Run smoke tests on green (is it alive?)
3. Route 100% to green
4. Keep blue running (rollback if needed)
5. After 1 hour with no issues, delete blue

If bug: Route 100% back to blue immediately
```

**Pros:**
- Instant rollback (keep old version running)
- Zero downtime (switch traffic, not restart)

**Cons:**
- Runs 2x infrastructure (expensive)
- Database migrations tricky (need backward compat)

**When to use:**
- Critical systems (payments, auth)
- Schema changes backwards compatible
- Can afford 2x hardware cost

## Strategy 2: Canary Deployment

```
Current: v1.2.3, handling 100% traffic
Deploy v1.2.4 to 5% of servers
  - Monitor: latency, errors, CPU
  - If good: 5% → 50% → 100%
  - If bad: Rollback that 5%, stay on v1.2.3

Timeline:
  T=0min:  5% of servers v1.2.4 (95% v1.2.3)
  T=15min: Monitor metrics, all green
  T=15min: 50% v1.2.4, 50% v1.2.3
  T=30min: 100% v1.2.4
  T=60min: All rolled out, no issues
```

**Pros:**
- Safe (catches bugs on small % first)
- Cheap (no 2x hardware)
- Fine-grained control (5% → 10% → 50%)

**Cons:**
- Takes time (30-60 min to fully deploy)
- More complex routing (some users on old, some new)

**When to use:**
- Normal deployments (features, bug fixes)
- Can wait 1 hour for rollout
- Infrastructure cost matters

## Strategy 3: Rolling Deployment

```
10 servers, all v1.2.3

1. Drain traffic from server 1
2. Deploy v1.2.4 to server 1
3. Route traffic back
4. Repeat for servers 2-10 (one at a time)

Timeline:
  T=0min:   10 servers v1.2.3
  T=5min:   9 servers v1.2.3, 1 server v1.2.4
  T=10min:  8 servers v1.2.3, 2 servers v1.2.4
  ...
  T=50min:  All servers v1.2.4
```

**Pros:**
- Zero downtime (always have capacity)
- Gradual (catches issues incrementally)
- No extra hardware

**Cons:**
- Can't rollback instantly (old version gone)
- Mix of old+new code running simultaneously

**When to use:**
- Backwards-compatible changes
- No database migrations
- Need gradual rollout

## Strategy 4: Feature Flags (Safest)

```
Deploy v1.2.4 with new feature disabled by default

Code:
  if FLAGS["enable_new_search"]:
      use_new_search()
  else:
      use_old_search()

Deployment:
  1. Deploy v1.2.4 (flag off) to 100% of servers
  2. Wait 1 hour, monitor metrics
  3. Enable flag for 1% of users
  4. Monitor errors/latency
  5. If good: 1% → 50% → 100%
  6. If bad: Disable flag (instant rollback, no redeployment)
```

**Pros:**
- Instant rollback (just toggle flag)
- Safe (enable for small % first)
- No need to keep old code running

**Cons:**
- Code complexity (if/else in every path)
- Database: have to support both old+new logic

**When to use:**
- Risky features (new algorithm, schema change)
- Want instant rollback
- Can tolerate code complexity

## Real-World: Combining Strategies

```
Deploy risky feature (new search algorithm):

1. Code review + unit tests
   ↓
2. Deploy with feature flag OFF (blue-green + canary)
   - 5% of servers first
   - Monitor for 30 min
   - If good: 100% of servers
   ↓
3. Enable feature flag for 1% of users (canary at feature level)
   - Monitor P99 latency, errors, user complaints
   - If good: 1% → 10% → 50% → 100%
   - If bad: Disable flag (instant rollback)
   ↓
4. Monitor for 24 hours
5. Remove feature flag (cleanup)

Safety: Triple-layered (code, infrastructure, feature)
```

## Interview Pattern: Safe Deployment

```
Q: "You're deploying a major database schema change.
   How do you do it safely?"

Weak answer:
  "Deploy and hope it works"
  (❌ No safety, risky)

Strong answer:
  "Backwards-compatible rollout:
  
  1. Schema change planning:
     - Old schema still works
     - New schema added alongside
     - Code handles both (migration period)
  
  2. Pre-deployment:
     - Create new table/column
     - Backfill old data to new column
     - Verify data integrity (checksums)
  
  3. Feature flag deployment:
     - Deploy code with flag OFF
     - Code can read from old or new (flag controlled)
     - Canary: 5% of traffic → new column
     - Monitor: latency, errors, data corruption
  
  4. Gradual cutover:
     - 5% traffic → new column
     - 50% traffic → new column
     - 100% traffic → new column
     - Run parallel for 24 hours (verify both equal)
  
  5. Cleanup:
     - Stop writing to old column
     - Delete old column (after backup)
     - Remove feature flag
  
  6. Rollback if issues:
     - Feature flag off → old column immediately
     - No redeployment needed
     - Data: old column still has values
  
  7. Monitoring:
     - Track latency per feature flag state
     - Alert if latency > SLA
     - Check data consistency (new vs old)
     - Monitor for any corruptions
  
  Cost: Takes 2-3 days (worth it for safety)
  Alternative (risky): Direct migration overnight (downtime, data loss risk)"

Why this signals good judgment:
  - You thought about backwards compat
  - You had a rollback strategy
  - You monitored before/after
  - You accepted the time cost for safety
```

## Deployment Checklist

- [ ] Test deployment on staging first (matches prod)
- [ ] Have rollback plan (blue-green, feature flag, or rolling back)
- [ ] Monitor key metrics during rollout (latency, errors)
- [ ] Gradual rollout (5% → 50% → 100%, not all at once)
- [ ] Notify on-call before deploying
- [ ] Have runbook if deployment fails
- [ ] Clean up old version after stable period

## What This Signals

- You understand deployment isn't binary (safe to risky)
- You've deployed at scale (know the tradeoffs)
- You think about rollback (not just launch)
- You'd monitor deployment metrics (not just code review)
