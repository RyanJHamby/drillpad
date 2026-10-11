# Feature Store Operations - Freshness, Validation, Versioning

## Computing and Updating Features

```
Daily feature computation workflow:

1. Source data (events table, 100M rows)
   yesterday's events (Jan 15)

2. Compute batch features (Spark job, 1 hour)
   SELECT user_id,
          COUNT(*) as purchase_count,
          AVG(amount) as avg_order,
          MAX(timestamp) as last_purchase_time
   FROM events
   WHERE DATE(timestamp) = '2025-01-15'
   GROUP BY user_id

3. Offline store (warehouse)
   Write features to user_features_2025-01-15 table
   500K unique users, features computed

4. Online store (Redis)
   For each user:
     redis SET user:123:features "{
       purchase_count: 42,
       avg_order: 125.50,
       last_purchase: 2025-01-15T23:45:00Z
     }"
   
   500K writes (takes 5 minutes)

5. Validation
   - Row count: 500K (expected)
   - Nulls: 0 (required fields populated)
   - Ranges: avg_order in [0, 100K] (sanity check)
   - Freshness: Latest timestamp = 2025-01-15 (correct)

6. Activation
   Model queries online store: redis GET user:123:features
   Features are available, predictions use them
```

## Feature Freshness SLA

```
Commitment: Features update by 2 AM daily

Monitoring:
  Freshness metric = NOW() - MAX(feature_timestamp)
  
  9 PM (yesterday's data, 5 hrs old): OK
  1 AM (2 hrs until update): OK
  2:30 AM (update complete, 30 min old): OK
  3 PM (13 hrs old): ALERT! (too stale)
  
Alert threshold: If any feature > 26 hours old, page on-call

On-call investigation:
  - Did batch job fail?
  - Did Redis load fail?
  - Is warehouse down?
  - Action: Retry or roll back to previous day's features
```

## Feature Validation

```
Before activating new features, validate:

1. Schema validation
   Expected features: purchase_count (int), avg_order (float)
   Actual: ✓ All present, right types

2. Completeness
   Expected rows: 500K users
   Actual: 495K (99% coverage)
   Status: OK (> 95% threshold)

3. Range checks
   purchase_count: 0-10000 (no user has > 10000? Sanity check)
   avg_order: $0.01-$999,999 (none outside range? No outliers)
   
4. Consistency
   New vs old (compare yesterday's features):
   User 123:
     Old purchase_count: 40
     New purchase_count: 42
     Diff: +2 (makes sense, 2 purchases yesterday)
   
   User 456:
     Old avg_order: $100
     New avg_order: $95
     Diff: -5 (expected, new cheaper order included)

5. Quality gates
   If 1+ checks fail: PAUSE rollout, investigate
   If all pass: Activate features to online store
```

## Feature Versioning

```
Scenario: Need to change feature definition

v1: avg_order = MEAN(amount)
  Works fine for 1 year

v2: avg_order = TRIMMED_MEAN(amount, 0.05)
  Removes top/bottom 5% outliers
  Better for realistic average

Models using features:
  Model A: Trained on v1 (avg_order without trimming)
  Model B: Trained on v2 (avg_order with trimming)
  
Problem: Serving mixes versions!
  User query gets: avg_order_v2 (latest from feature store)
  Model A expects: avg_order_v1 (what it was trained on)
  → Skew! Performance drops

Solution: Feature versioning in registry

Registry definition:
  "avg_order":
    v1: "SELECT AVG(amount) FROM orders" (deprecated)
    v2: "SELECT PERCENTILE_CONT(amount, 0.05) FROM orders" (current)
    v3: "SELECT APPROX_PERCENTILE(amount, 0.05) FROM orders" (dev)

Online store keys:
  user:123:features:avg_order:v1 → 100.00
  user:123:features:avg_order:v2 → 98.50
  user:123:features:avg_order:v3 → 98.45

Model deployment:
  Model A queries: avg_order:v1 (it expects v1)
  Model B queries: avg_order:v2 (it expects v2)
  
No skew! Each model gets what it needs
```

## A/B Testing with Feature Store

```
Test: Does higher avg_order (trimmed) improve recommendations?

Setup:
  Control group (50% of users): Uses avg_order:v1
  Treatment group (50% of users): Uses avg_order:v2
  
Traffic routing (online serving):
  if is_in_treatment_group(user_123):
    features = redis GET user:123:features:avg_order:v2
  else:
    features = redis GET user:123:features:avg_order:v1

Model serves both:
  if user in control: use model_v1 (expects v1 features)
  if user in treatment: use model_v2 (expects v2 features)

Metrics:
  Control: click_rate = 8.2%, revenue_per_user = $50
  Treatment: click_rate = 8.5%, revenue_per_user = $52
  
Result: Treatment wins (+0.3% clicks, +4% revenue)
Decision: Roll v2 to all users
```

## Interview Pattern: Feature Store Operations

```
Q: "You have a feature store serving 1000 QPS.
   Features update daily, but it's 2 PM and features are 16 hours old
   (should have been updated at 2 AM but failed).
   Serving production model. What do you do?"

Weak answer:
  "Just wait for the next update"
  (❌ Model is already using stale features for hours)
  
  Or: "Immediately update all features"
  (❌ Might not be safe, what if compute was wrong?)

Strong answer:
  "Incident response:
  
  1. Assess impact (immediately):
     - Feature freshness SLA: 26 hours old (violated)
     - Model performance: Degraded? Check logs
     - User impact: High (serving with stale data)
  
  2. Immediate action:
     - Option A: Use last known good features (from yesterday)
       redis RESTORE user:*:features from 2025-01-14 snapshot
       Cost: One day older, but consistent
     
     - Option B: Recompute features NOW (emergency)
       Trigger on-demand batch job (expensive, 1h)
       Cost: Expensive but latest data
     
     - Option C: Disable feature, use fallback
       Some models can work without features
       Cost: Reduced model quality
     
     My choice: Option A (restore yesterday, then debug)
  
  3. Root cause (while serving continues):
     - Check batch job logs (did it error?)
     - Check Redis connectivity (network issue?)
     - Check disk space (ran out?)
     - Fix issue
  
  4. Recovery:
     - Once fixed, run emergency batch job
     - Compute today's features (2 PM, not 2 AM)
     - Validate thoroughly (don't compound problem)
     - Load to online store
     - Monitor freshness (back to SLA)
  
  5. Postmortem:
     - Why did batch job fail?
     - Why didn't we alert sooner?
     - Add monitoring: Alert at 6 AM if still not updated
     - Add fallback: Automatic restore if update fails
     - Prevent next time"

Why this signals good judgment:
  - You had incident response plan (not panic)
  - You understood impact (stale data hurts model)
  - You had options + trade-offs (A/B/C)
  - You balanced speed (restore) vs quality (recompute)
  - You debugged root cause
  - You prevented next time (monitoring)
```

## Checklist: Feature Store Operations

- [ ] Feature computation automated (batch job, scheduled)
- [ ] Validation gates (schema, completeness, ranges)
- [ ] Freshness monitoring (alert if stale)
- [ ] Versioning system (safe rollouts, no skew)
- [ ] Rollback strategy (if something breaks, restore)
- [ ] A/B testing support (test feature changes safely)
- [ ] On-call runbook (what to do if features are stale)

## What This Signals

- You've operated ML infrastructure at scale
- You understand operational risk (stale data, rollouts)
- You have systematic processes (validation, versioning)
- You think about safety (gradual rollouts, A/B testing)
