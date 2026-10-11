# Data and ML System Debugging: Silent Bugs and Non-Determinism

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Silent Data Bugs

Your code is correct. Tests pass. But data is wrong.

```
Example: Off-by-one in date window

code:
  def get_orders_for_week(monday):
      return db.query(
          where date >= monday and date < monday + 7 days
      )

Looks correct. Test passes. But data is wrong.

Why:
  Monday = 2026-10-11 (day 0)
  Window: 10-11 to 10-17 (7 days)
  But wait: Monday to Sunday should be 10-11 to 10-17 (7 days)
  
  Problem: Off-by-one if code says 10-11 to 10-18 (8 days)!
  Result: Each week, one extra day of orders included
  Silent: Tests don't catch (test only checks count, not correctness)
```

**The challenge:** Code is correct, logic is correct, but output is wrong.

## Silent Data Bug Categories

**1. Schema Drift**

```
Database schema changed, but code wasn't updated

Old schema:
  CREATE TABLE users (
    id INT,
    created_at TIMESTAMP
  );

New schema (DBA added nullable field):
  CREATE TABLE users (
    id INT,
    created_at TIMESTAMP,
    migrated BOOLEAN DEFAULT NULL  ← NEW FIELD
  );

Code:
  SELECT id, created_at FROM users;  ← Still works
  But downstream code assumes 2 columns, now 3
  → Parsing errors, NULL fields, silent failures
```

**2. Data Type Mismatch**

```
Code assumes integer, but data is string:

Code:
  price = int(price_str)  # Fails if price_str = "12.99"
  
Result:
  ValueError: invalid literal for int() with base 10: '12.99'
  Silent if error is caught and ignored
```

**3. Off-by-One in Windows**

```
Weekly aggregation bug:

Correct (Monday 00:00 to Sunday 23:59:59.999):
  WHERE timestamp >= '2026-10-11 00:00:00'
    AND timestamp < '2026-10-18 00:00:00'

Wrong (Monday 00:00 to Monday 00:00 inclusive):
  WHERE timestamp >= '2026-10-11 00:00:00'
    AND timestamp <= '2026-10-18 00:00:00'
    
Bug: One extra day included each week
Silent: Count is off by 5-10%, might not notice
```

**4. Null Handling**

```
Aggregation:

SELECT AVG(price) FROM orders;

If some rows have NULL price:
  NULL is excluded from AVG (SQL standard)
  
But code assumes:
  AVG should be (sum of all / count of all)
  
Result: Silently different calculation
  SQL: Divides by count_non_null
  Code: Divides by count_all (includes NULLs)
  → Wrong average
```

## Detecting Silent Data Bugs

**Approach 1: Data Profiling (Summarize and Compare)**

```
Every day, compute summary stats:

  SELECT COUNT(*), MIN(price), MAX(price), AVG(price)
  FROM orders
  WHERE date = CURDATE();
  
Daily stats:
  Date        Count    Min    Max    Avg
  2026-10-08  1,000    1.00   999    150.00
  2026-10-09  1,050    1.00   999    150.50
  2026-10-10    950    1.00   999    149.50
  2026-10-11  1,200    1.00   999    149.75  ← Unusual spike!
  2026-10-12    980    1.00   999    150.00
  
Alert: Count spiked on 10-11
  Why? Data error? User behavior change? Bug?
```

**Approach 2: Invariant Checks**

```
Code-level assertions:

SELECT COUNT(*) FROM users WHERE age < 0;
→ Should be 0, always

SELECT COUNT(*) FROM orders WHERE amount = 0;
→ Should be rare

SELECT COUNT(*) FROM orders 
  WHERE created_at > updated_at;
→ Should be 0, always

If any assertion fails: Data bug found
```

**Approach 3: Comparison with Gold Source**

```
You have two ways to compute something:

Method A: SQL query
  SELECT SUM(amount) FROM orders;
  Result: 1,234,567
  
Method B: Manual aggregation (reference implementation)
  orders = load_orders()
  total = sum(order.amount for order in orders)
  Result: 1,234,568
  
Difference: $1
→ Data bug found (off-by-one somewhere)
```

## ML System Debugging

Unique challenges for ML systems:

**Problem 1: Non-Determinism**

```
Same model, same input, different predictions?

Causes:
  - RNG not seeded
  - Batch normalization (statistics vary per batch)
  - Data shuffling
  - Floating-point rounding
  
Symptom: Test fails 50% of time
Solution: Seed RNG, freeze batch norm, freeze data order
```

**Problem 2: Silent Performance Drop**

```
Your model accuracy was 95%, now it's 92%.
What happened?

Causes:
  - Data distribution changed (data drift)
  - Model weights changed (unintended update)
  - Preprocessing logic changed
  - Evaluation metric changed (reported differently)
  
Detection:
  Compare embeddings: Old vs new model on same input
  → If embeddings differ, model weights changed
  
  Compare predictions on held-out test set
  → Old model: 95%, new model: 92%
  → Which datapoints regressed?
```

**Problem 3: Training Instability**

```
Model loss oscillates:
  Epoch 1: Loss = 0.5
  Epoch 2: Loss = 0.4
  Epoch 3: Loss = 0.8  ← Spike!
  Epoch 4: Loss = 0.3
  
Causes:
  - Learning rate too high
  - Batch size too small
  - Gradient explosion / vanishing gradients
  - NaN propagation (one NaN makes everything NaN)
  
Detection:
  Plot loss curve → visual inspection
  Check for NaN: if loss == nan: raise error
  Check gradients: if gradient > 100: warning
```

**Problem 4: Model Divergence (NaN/Inf)**

```
Training starts fine, then suddenly:
  Loss = inf
  Predictions = nan
  Gradients = nan

Root cause:
  One number became too large (exploding gradient)
  → Multiplication by large value
  → Overflow
  → NaN/Inf propagation

Detection:
  assert not np.isnan(loss), "Loss is NaN"
  assert loss < 1e6, "Loss explosion"
  
Fix:
  Use gradient clipping: clip gradients to [-1, 1]
```

## GPU/NCCL-Style Hangs

Distributed training across GPUs:

```
Machine 1 (GPU 0): Finished training step, waiting for gradient sync
Machine 2 (GPU 1): Stuck in backward pass
Machine 3 (GPU 2): Finished training step, waiting

Result: Entire training hangs (deadlock)

Symptom: All GPUs idle, no progress

Causes:
  - Uneven batch processing (one batch much larger)
  - One GPU OOM'd (but didn't error, hung)
  - Communication timeout
  - Collective operation (AllReduce) deadlock
  
Detection:
  nvidia-smi: See GPU memory usage
  If one GPU at 0% usage while others busy → uneven load
  
  Logs: Check which machine is stuck
  If machine 2 not logging → likely hung there
```

## Interview: Data and ML Debugging

**Q: "Model accuracy dropped from 95% to 92% after retraining. What changed?"**

Strong answer:
```
"Systematic approach:

1. Isolate the variable that changed
   - Did code change? (check git diff)
   - Did data change? (check data version, distribution)
   - Did hyperparameters change? (learning rate, batch size)
   
2. Compare old vs new
   - Old model on test set: 95% accuracy
   - New model on test set: 92% accuracy
   - Which classes regressed? (per-class accuracy)
   
3. Narrow to root cause
   a) If data changed:
      - Compute data distribution stats (histogram)
      - Is test distribution different from train?
      - Check for data drift (covariate shift)
   
   b) If code/hyperparameters changed:
      - Retrain old code with new data
      - If 95% → data is fine, code matters
      - If 92% → data drift is root cause
   
   c) If model weights changed:
      - Load old weights
      - On new data: 95% or 92%?
      - Confirms if it's weights or data
   
4) Fix
   - If data drift: Retrain on new data distribution
   - If hyperparameters: Tune (learning rate, etc.)
   - If code bug: Fix the bug
   
5) Verify
   - Accuracy returns to 95%
   - Per-class metrics are balanced
"
```

## Checklist

- [ ] Data profiling (daily summary stats)
- [ ] Invariant checks (COUNT WHERE condition = 0)
- [ ] Gold source comparison (two ways to compute)
- [ ] Distribution checks (data drift detection)
- [ ] Off-by-one reviewed (boundary conditions)
- [ ] Null handling verified (aggregations include/exclude NULLs)
- [ ] RNG seeded (ML reproducibility)
- [ ] Loss/metrics monitored (NaN/Inf detection)

## Common Mistakes

1. **Assuming code is correct.** "Tests passed, so data must be wrong." But tests might not check correctness.
2. **Not comparing with gold source.** Two methods disagree → silently wrong, no alert.
3. **Ignoring data drift.** Model trained on 2025 data, now runs on 2026 data (distribution changed).
4. **Not seeding RNG.** ML model non-deterministic → test fails 50% of time.
5. **Silent NaN propagation.** One NaN early in training → silently infects everything.

