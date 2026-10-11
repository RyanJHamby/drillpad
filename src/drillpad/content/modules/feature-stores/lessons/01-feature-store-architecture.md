# Feature Store Architecture - Online & Offline Serving

## The Training-Serving Skew Problem

```
Training (model development):
  1. Load historical data (Jan-Sep 2024)
  2. Engineer features:
     - user_avg_order_value = AVG(amount) per user
     - user_purchase_count = COUNT(*) per user
     - user_days_since_signup = NOW() - signup_date
  3. Train model (uses those features)

Serving (production inference):
  4. User makes a purchase
  5. Compute features AGAIN:
     - user_avg_order_value = query database (slow, 200ms)
     - user_purchase_count = query database (slow, 200ms)
     - user_days_since_signup = compute (fast, 1ms)
  6. Call model (10ms)
  7. Return prediction (total: 410ms, user waits)

Problem: Feature computation in training vs serving differs
  - Training: Used all historical data
  - Serving: Uses current database
  - Result: Skew, model sees different features, predictions are unreliable
  
Also: Serving is slow (200ms per feature query)
```

## The Solution: Feature Store

```
Feature Store = Centralized feature repository

Architecture:
  1. Offline Store (for training)
     - Data warehouse (Snowflake/BigQuery)
     - Features computed in batch (daily)
     - Historical snapshots (Jan-Sep 2024)
     - Used by data scientists for training
  
  2. Online Store (for serving)
     - Cache/KV store (Redis/DynamoDB)
     - Pre-computed features, sub-ms lookup
     - Updated daily (near real-time)
     - Used by models in production
  
  3. Feature Registry
     - Defines what features exist
     - Data type, source, how computed
     - Versioning (feature_v1 vs feature_v2)

Workflow:
  Training:
    a) Data scientist specifies: "I need user_avg_order_value, user_purchase_count"
    b) Feature store queries offline store
    c) Gets historical snapshot (Jan-Sep 2024)
    d) Train model
  
  Serving:
    e) New user makes purchase
    f) Query online store: "Get features for user_123"
    g) Redis returns pre-computed features (< 1ms)
    h) Model uses same features as training
    i) Prediction is consistent, fast
```

## Online vs Offline Stores

```
Offline Store (Batch)
  Purpose: Training data
  Technology: Data warehouse
  Update frequency: Daily (batch job)
  Query pattern: "Give me all user features for 100K users"
  Latency: Seconds OK (it's batch)
  Cost: Cheap (run once/day)
  
  Example:
    SELECT user_id, avg_order_value, purchase_count, days_since_signup
    FROM user_features
    WHERE date='2024-09-15'

Online Store (Real-time)
  Purpose: Inference
  Technology: KV cache (Redis, DynamoDB)
  Update frequency: Near real-time (seconds)
  Query pattern: "Get features for user_123"
  Latency: < 10ms (required!)
  Cost: Expensive (keep data in memory/fast storage)
  
  Example:
    redis GET user:123:features
    → {"avg_order_value": 125.50, "purchase_count": 42, "days_since_signup": 365}
```

## Feature Freshness

```
Freshness = How old is the feature?

Batch (daily):
  Update: 2:00 AM every morning
  Feature age at 11:59 PM: 22 hours
  Trade-off: Cheap infrastructure, but stale features

Batch (hourly):
  Update: Every hour
  Feature age: 0-60 minutes
  Trade-off: More expensive, fresher features

Streaming (real-time):
  Update: As events happen
  Feature age: Seconds
  Trade-off: Complex, expensive, only for critical features

Example (user purchase count):
  Daily: Count might be 1 day behind
  Hourly: Count might be 1 hour behind
  Streaming: Count is immediate

Model impact:
  For churn prediction: Yesterday's purchase count is fine (behavior stable)
  For fraud detection: Current session activity matters (need streaming)
```

## Interview Pattern: Feature Store

```
Q: "Your fraud model is trained on daily features but serves predictions
   100 times per second. Model performance drops 15% in production.
   Why and how do you fix it?"

Weak answer:
  "Data drift, retrain model"
  (❌ Maybe, but not addressing the real problem)

Strong answer:
  "Training-serving skew due to feature computation mismatch:
  
  1. Diagnosis:
     Training: Features computed from historical warehouse snapshot
       - user_purchase_count = historical count (stable)
       - user_avg_session_time = historical average
       - fraud_score = model score from yesterday
     
     Serving: Features computed fresh at request time
       - user_purchase_count = query live database (current)
       - user_avg_session_time = running average (not historical)
       - fraud_score = old model score (stale)
     
     Skew: Model sees different features, performance drops
  
  2. Solution: Feature Store
     a) Offline store: Data warehouse snapshot
        - Compute daily at 2am
        - Store user features for training
        - Data scientist gets exact same features as production
     
     b) Online store: Redis cache
        - Pre-compute features daily
        - Store as user:123:features → {count: 42, session_time: 3600}
        - Serve at < 1ms (no queries to warehouse)
     
     c) Feature registry:
        - Define user_purchase_count (source: warehouse, daily refresh)
        - Define user_avg_session_time (source: stream, rolling window)
        - All models use same definitions
  
  3. Implementation:
     - Set up Feast or Tecton
     - Define features (user_purchase_count, session_time, etc.)
     - Compute features in batch (daily warehouse job)
     - Load into online store (Redis)
     - Model queries online store at serving time
     - Training queries offline store (exact same data)
  
  4. Validation:
     - After feature store live, recompute model on offline features
     - Deploy new model (trained on feature store data)
     - Monitor: fraud_score in serving should match training
     - Monitor: latency (now < 10ms instead of 500ms)
  
  5. Result: Production performance matches training"

Why this signals good judgment:
  - You diagnosed the real problem (skew, not drift)
  - You understood compute latency impact
  - You knew feature store pattern
  - You had validation strategy (compare scores)
```

## Checklist: Feature Store Design

- [ ] Features defined (what, how computed, update frequency)
- [ ] Offline store set up (warehouse, historical snapshots)
- [ ] Online store set up (cache, sub-ms latency)
- [ ] Feature pipeline (batch job to compute + load)
- [ ] Monitoring (staleness, freshness SLA)
- [ ] Training/serving consistency validated

## What This Signals

- You've solved training-serving skew (common hard problem)
- You understand infrastructure for ML at scale
- You think about latency (can't compute features per-request)
- You've worked with feature store tooling (Feast, Tecton, etc.)
