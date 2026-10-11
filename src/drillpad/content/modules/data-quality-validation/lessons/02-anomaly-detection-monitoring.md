# Anomaly Detection & Data Quality Monitoring

## Detecting Bad Data

```
Pipeline: Daily customer events

Normal distribution:
  100K-110K events per day
  $50-$100 average order value
  75% completion rate
  Peak hour: 2-3 PM

Day 5: Anomalies detected
  Events: 2.5M (25x normal!)
  Order value: $0.01-$0.99 (looks like test data)
  Completion: 5% (something broken?)
  Peak hour: 4 AM (weird)

Questions:
  - Is the data real or corrupted?
  - Is the system under attack?
  - Did code change break something?
  - Should we load this data?
```

## Distribution Shift Detection

```
Model trained on 2024 data:
  Payment methods: 80% credit_card, 15% paypal, 5% other
  Average order: $100
  Geography: 60% US, 40% international

Production 2025:
  Payment methods: 50% credit_card, 40% apple_pay, 10% other
  Average order: $250 (inflation + product mix change)
  Geography: 40% US, 60% international (expansion)

Data looks valid (right types, no nulls) but different

Problem: Model was trained on 2024 data
Solution: Detect shift, retrain on 2025 data, or add domain adaptation
```

## Outlier Detection

```
Order amounts (histogram):
  $10-$100: 95,000 orders
  $100-$500: 4,500 orders
  $500-$1000: 400 orders
  $1000+: 50 orders
  
One order: $999,999,999
  
Statistical outlier? Yes (99.99th percentile)
Real or mistake?
  - Customer ID valid? Yes
  - Payment method valid? Yes
  - Date reasonable? Yes
  - But price is absurd
  
Action: Flag for manual review, don't auto-load
```

## Monitoring Strategy

```
Metrics to track daily:
  1. Row count
     Normal: 100K-110K
     Alert: < 50K or > 200K
  
  2. Null percentage per column
     Normal: customer_id 0% null, notes < 2% null
     Alert: customer_id > 1% null
  
  3. Value distribution (per category)
     Normal: payment_method distribution stable
     Alert: If credit_card drops from 80% to 10%
  
  4. Numeric ranges
     Normal: amount in [0.01, 1000]
     Alert: If min < 0 or max > 10000
  
  5. Timestamp freshness
     Normal: Latest event < 1 hour old
     Alert: Latest event > 6 hours old (data pipeline stalled)

Example alerting rule (Datadog/Prometheus):
  if row_count_today < 50k or row_count_today > 200k:
    alert("Data volume anomaly")
  
  if null_percentage["customer_id"] > 1:
    alert("High null rate in customer_id")
  
  if max_order_amount > 10000:
    alert("Unusual high order detected")
```

## Data Observability

```
Three pillars of data quality:

1. Freshness
   - How recent is the data?
   - SLA: Latest event < 1 hour old
   - Alert if: Latest event > 6 hours old

2. Completeness
   - What percentage of expected data arrived?
   - SLA: 99% of rows expected
   - Alert if: < 95% received

3. Accuracy
   - Does data match business rules?
   - SLA: 0 constraint violations, < 0.1% type errors
   - Alert if: > 0.1% validation failures
```

## Interview Pattern: Anomaly Detection

```
Q: "Your ML model uses daily events data.
   Every morning, you load yesterday's data.
   One day, you get 10x more events than normal.
   Should you load it?"

Weak answer:
  "Yes, load it"
  (❌ What if it's corrupted? Or test data?)
  
  Or: "No, skip it"
  (❌ What if it's real? You're dropping data)

Strong answer:
  "Investigate first:
  
  1. Detect (automated check):
     Row count: 1M vs normal 100K (10x)
     → Trigger anomaly alert
  
  2. Investigate (manual):
     a) Check data quality metrics:
        - Nulls: Within normal? Yes ✓
        - Type errors: Within normal? Yes ✓
        - Amount ranges: Within normal? No ✗
        - Average amount: $0.01 (test data!)
     
     b) Check upstream (logs, events API):
        - Any deploys yesterday? Yes (new feature flag)
        - Did we enable test environment? Yes
        - Is production traffic normal? Yes
     
     Conclusion: Mix of test + production data
  
  3. Handle:
     - Quarantine this load (don't load to prod)
     - Investigate feature flag (disable/fix)
     - Re-run tomorrow with clean data
     - Alert on-call (data quality issue found)
  
  4. Prevent:
     - Add check: Average amount must be > $10
     - Add check: Test data markers (environment=prod only)
     - Improve data quality monitoring
     - Add validation before load"

Why this signals good judgment:
  - You don't blindly load data
  - You have metrics to detect problems
  - You investigate root cause (feature flag)
  - You prevent next time (add validation)
```

## Checklist: Data Monitoring

- [ ] Metrics defined (volume, nulls, ranges, distribution)
- [ ] Alerting rules set (on-call aware, thresholds sensible)
- [ ] Anomaly detection (outliers, distribution shift)
- [ ] Monitoring dashboard (daily check, trending)
- [ ] Escalation path (what to do when alert fires)
- [ ] Testing (validate alerts on historical data)

## What This Signals

- You catch problems before they hit ML models
- You have systematic monitoring (not ad-hoc checks)
- You understand data as a product (track quality like code)
- You balance automation + manual investigation (don't robot blindly)
