# Evaluation Harness Engineering: Building Regression Test Suites for ML

## The Problem: How Do You Know If a Change Improved Your Model?

You train a new model. Accuracy went from 92% to 93%.

Is that a real improvement, or just noise?

You deploy it. User experience feels worse (slower).

Did you pick a metric that doesn't capture reality?

**Evaluation harness:** automated test suite that proves a model is better (or worse) before shipping.

## What Is an Eval Harness?

An evaluation harness is:
1. A suite of test cases (inputs + expected outputs)
2. A scoring function (how correct was the model?)
3. A regression test (did the new model break old capabilities?)
4. Automated runs (before every commit, before deployment)

```
Code change:
  Model learns from new data
  Feature engineering updated
  Inference pipeline changed

Test suite runs:
  1. Load old model (baseline)
  2. Load new model (candidate)
  3. Run 1000 test cases on both
  4. Score each: precision, recall, latency, cost
  5. Compare: is new > old? By how much?

Result:
  ✓ New model is 2% better, no regressions → SHIP
  ✗ New model is 3% worse on edge cases → BLOCK
  ✗ New model is slower (50ms vs 10ms) → BLOCK
```

## Structure of an Eval Harness

### Layer 1: Test Dataset

```python
# test_cases.json
[
  {
    "id": "frustration_001",
    "input": "Customer call transcript",
    "context": "spoke for 5 minutes, then hung up",
    "expected_output": "frustrated",
    "tags": ["negative_emotion", "short_call"]
  },
  {
    "id": "frustration_002",
    "input": "Customer call transcript",
    "context": "thanked support, satisfied",
    "expected_output": "calm",
    "tags": ["positive_emotion", "long_call"]
  }
  // ... 998 more test cases
]
```

**Criteria:**
- Cover happy paths, edge cases, rare cases
- Tag by scenario (makes it easy to debug)
- Don't leak into training data
- [VERIFY] Rule of thumb: 1000-2000 test cases per model

### Layer 2: Evaluation Metrics

```python
def eval_frustration_model(model, test_cases):
  results = {
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "latency_p50": 0.0,
    "latency_p99": 0.0,
    "cost_per_prediction": 0.0
  }
  
  predictions = []
  latencies = []
  
  for test in test_cases:
    start_time = time.time()
    pred = model.predict(test["input"])
    latency = time.time() - start_time
    
    predictions.append({
      "expected": test["expected_output"],
      "predicted": pred,
      "correct": (pred == test["expected_output"])
    })
    latencies.append(latency)
  
  # Compute accuracy metrics
  tp = sum(1 for p in predictions if p["correct"])
  fp = sum(1 for p in predictions if not p["correct"])
  
  results["precision"] = tp / (tp + fp)
  results["latency_p50"] = percentile(latencies, 50)
  results["latency_p99"] = percentile(latencies, 99)
  
  return results
```

### Layer 3: Regression Testing

```python
def regression_test(baseline_results, candidate_results):
  regressions = []
  
  # Check for accuracy drop
  if candidate_results["f1"] < baseline_results["f1"] * 0.95:
    regressions.append({
      "metric": "f1",
      "baseline": baseline_results["f1"],
      "candidate": candidate_results["f1"],
      "drop": baseline_results["f1"] - candidate_results["f1"],
      "severity": "high"
    })
  
  # Check for latency regression
  if candidate_results["latency_p99"] > baseline_results["latency_p99"] * 1.1:
    regressions.append({
      "metric": "latency_p99",
      "baseline": baseline_results["latency_p99"],
      "candidate": candidate_results["latency_p99"],
      "increase": candidate_results["latency_p99"] / baseline_results["latency_p99"],
      "severity": "medium"
    })
  
  return regressions
```

### Layer 4: Stratified Evaluation

```python
def stratified_eval(model, test_cases):
  results_by_tag = {}
  
  for tag in ["negative_emotion", "positive_emotion", "neutral"]:
    subset = [t for t in test_cases if tag in t["tags"]]
    
    if not subset:
      continue
    
    metrics = eval_frustration_model(model, subset)
    results_by_tag[tag] = metrics
  
  return results_by_tag
```

Why stratified?
- Model might be 95% accurate overall
- But 50% accurate on rare frustration cases
- Stratified eval catches this

## Common Anti-Patterns

### Anti-Pattern 1: Single Global Metric

```python
# ❌ BAD
if candidate_accuracy > baseline_accuracy:
  ship_model()
```

Problem: Accuracy averages across all cases.
- Rare edge cases hidden
- Class imbalance masked
- Different use cases have different needs

Fix: Use multiple metrics + stratification.

### Anti-Pattern 2: Tuning on Test Set

```python
# ❌ BAD
for threshold in [0.3, 0.4, 0.5, 0.6, 0.7]:
  f1 = eval_on_test_set(threshold)
  if f1 > best_f1:
    best_f1 = f1
    best_threshold = threshold

# Now report F1 with best_threshold
```

Problem: You're overfitting the test set.

Results on new data will be worse.

Fix: Tune on validation set, report on test set (never touch).

### Anti-Pattern 3: Evaluating on Training Data

```python
# ❌ BAD
model.fit(training_data)
results = model.evaluate(training_data)  # Same data!
```

Problem: Model has memorized training data.

Will perform worse on real data.

Fix: Use 3-way split: train (60%), validation (20%), test (20%).

### Anti-Pattern 4: Ignoring Latency

```python
# ❌ BAD
if candidate_accuracy > baseline_accuracy:
  ship_model()

# Months later: new model takes 2x longer to run
# Cost of inference doubles, customers slow down
```

Fix: Measure latency, cost, throughput alongside accuracy.

## Interview Section

### Q1: You have a model with 99% accuracy. But when you stratify by gender, it's 95% accuracy for men and 99.5% for women. What do you do?

**Weak answer:** "Report the 99% accuracy."

**Strong answer:**
"Don't ship without fixing this. Steps:

1. Diagnose the problem:
   - Is training data imbalanced (more women examples)?
   - Does model overfit to majority group (women)?
   - Are men's speech patterns different (accent, vocabulary)?
   
2. Options to fix:
   a) Collect more labeled data for men (most reliable)
   b) Oversample men during training (synthetic, may overfit)
   c) Use group-aware loss function (penalize group imbalance)
   d) Separate models per gender (operational complexity)
   
3. After fix, re-evaluate:
   - Target: > 98% for both groups (or agreed SLO)
   - Validate on held-out test set (not training set)
   - Check latency, cost didn't increase
   
4. Before shipping:
   - Add regression test for gender stratification
   - Monitor in production for actual accuracy per group
   - Alert if men's accuracy drops below 98%

Result: Fair model that works for all customers, with monitoring."

### Q2: Describe a complete eval harness for a recommendation system.

**Weak answer:** "Measure precision and recall."

**Strong answer:**
"Setup:

1. Test Dataset (2000 cases):
   - User IDs: diverse activity levels (power users, casual, inactive)
   - Item IDs: popular items, niche items, new items
   - Ground truth: items user actually clicked/bought
   - Tags: by item type, user segment, recency
   
2. Metrics (measure quality):
   a) Ranking quality:
      - NDCG@10 (normalized DCG at top 10)
      - Precision@10 (% of top 10 are relevant)
      - Recall@10 (% of user's relevant items in top 10)
   
   b) Diversity:
      - % of top 10 from different categories
      - Penalize if all recommendations are same genre
   
   c) Novelty:
      - % of recommendations user hasn't seen before
      - Penalize if recommending only old, popular items
   
   d) Coverage:
      - % of catalog items recommended (not just Top 100)
      - Penalize recommending only popular items
   
   e) Latency:
      - p50, p99 latency (must be < 100ms to serve requests)
      - Cost per recommendation (ML inference cost)

3. Stratified Eval (catch group-specific issues):
   a) By user segment:
      - Power users (10+ purchases/month)
      - Casual users (1-2 purchases/month)
      - Inactive users (0 purchases in 3 months)
   
   b) By item freshness:
      - New items (< 1 week old)
      - Popular items (> 1000 sales)
      - Niche items (< 100 sales)
   
   c) By time:
      - Recommendations from morning vs evening
      - Seasonal shifts (Christmas vs July)

4. Regression Testing:
   - New model NDCG@10 >= 0.92 (don't ship if lower)
   - Latency p99 <= 150ms (no slowdown)
   - Coverage >= 0.60 (don't optimize only for top items)
   - Offline-online gap <= 5% (what we measure ≈ what users see)

5. Automation:
   - Every commit: run eval suite (10 min)
   - Every merge to main: full eval + stratified (30 min)
   - Before deployment: compare A/B test results (live eval)

Example output:
  Baseline (v5):
    NDCG@10=0.93, Latency_p99=85ms, Coverage=0.58
  
  Candidate (v6):
    NDCG@10=0.95, Latency_p99=110ms, Coverage=0.62
  
  Verdict:
    + NDCG up 2% (good)
    + Coverage up 7% (good, more diverse recommendations)
    - Latency up 29% (bad, need to optimize)
  
  Decision: Block, optimize latency and try again"

### Q3: What's the difference between validation set and test set?

**Weak answer:** "They're both for testing."

**Strong answer:**
"Both are held-out data, but used differently:

Validation Set (20% of data):
  - Used during training to tune hyperparameters
  - Example: threshold for classification
  - You see results, and you optimize
  - Can overfit to validation set (especially small dataset)

Test Set (20% of data):
  - Held completely secret during training
  - Used only at the END to report final metrics
  - Never optimize on test set
  - Gives honest estimate of production performance

Example:
  Train: 60% of 1000 examples = 600
  Validate: 20% = 200 (use to pick threshold)
  Test: 20% = 200 (report final accuracy)
  
  Process:
  1. Train model on 600 examples
  2. Tune threshold on 200 validation examples
     - Try threshold=0.3: F1=0.91 on validation
     - Try threshold=0.4: F1=0.92 on validation
     - Pick threshold=0.4
  3. Measure final performance on 200 test examples
     - F1 on test = 0.89 (slightly worse, expected)
     - Report 0.89 as final metric
  
  Why split test and validation?
    If you tuned on test set:
      Test F1=0.92 (because you optimized for test)
      Real-world F1=0.85 (different distribution)
      Your reported metric (0.92) is LYING
  
  With proper split:
    Validation F1=0.92 (tuning)
    Test F1=0.89 (honest measurement)
    Real-world F1=~0.88-0.90 (matches test)
    Your reported metric (0.89) is HONEST

Never touch test set until shipping."

### Q4: Numeric Exercise: Eval Harness Performance

You have:
- 2000 test cases
- Each test case takes 50ms to run (model inference + scoring)
- Test suite runs every commit
- Team commits 50 times/day

Questions:
1. How long does each eval run?
2. How much compute time do you need?
3. Can you cache results?

Answers:

1. **Time per eval run:**
   2000 cases × 50ms = 100 seconds = ~1.7 minutes
   
   Plus overhead:
   - Load model: 5 seconds
   - Setup: 5 seconds
   - Total: ~2 minutes per eval
   
2. **Compute time per day:**
   50 commits/day × 2 minutes = 100 minutes of eval
   
   But parallelized (4 eval machines):
   100 min / 4 machines = 25 minutes wall-clock time
   
3. **Caching strategy:**
   - Cache by (commit_hash, test_case_id)
   - If model didn't change, reuse baseline
   - If only 10 test cases changed (data update), run only those
   
   Typical savings: 30-50% of eval runs are cached
   
4. **Cost analysis:**
   - 4 eval machines: $200/month
   - Storage for results (git history): 10 GB/month = $1/month
   - Total: ~$200/month
   
   **Question:** Is this expensive?
   
   If you ship a bad model due to no eval → production outage
   Cost of outage: $100K+ (revenue loss, reputation)
   
   Eval harness is cheap insurance."

## When to Use / When NOT

| Scenario | Eval Harness? |
|----------|---------------|
| Changing model architecture | YES |
| Tuning hyperparameters | YES |
| Adding training data | YES |
| Upgrading inference hardware | MAYBE (latency only) |
| Bug fix in preprocessing | YES |
| A/B testing live models | NO (use online metrics) |
| Early-stage research | MAYBE (less rigor) |
| Production system | YES (required) |

## Checklist: Eval Harness Quality

- [ ] Test cases cover happy path, edge cases, rare cases?
- [ ] Test cases are NOT in training data (no data leakage)?
- [ ] Metrics measure what users care about (not just accuracy)?
- [ ] Stratified evaluation catches group-specific failures?
- [ ] Regression test catches latency, cost, throughput regressions?
- [ ] Validation set is used only for tuning, test set only for reporting?
- [ ] Baselines are reproducible (same commit, same results)?
- [ ] Auto-run on every commit, block deployment if regression?
- [ ] Results are logged, queryable (can you find why a change broke things)?

## Common Wrong Answers

1. "Validation set and test set are the same." → NO, tuning vs reporting.
2. "High accuracy on test means good production performance." → NO, need stratification.
3. "You can optimize on test set if you're careful." → NO, still overfits.
4. "One metric is enough." → NO, need multiple (accuracy, latency, cost, coverage).
5. "Eval harness takes too long." → NO, 2-5 minutes is fast (catches bugs worth 1000x more).
6. "Manual evaluation is more thorough." → NO, automated catches regressions humans miss.
7. "Caching eval results is cheating." → NO, smart optimization (as long as deps tracked).
