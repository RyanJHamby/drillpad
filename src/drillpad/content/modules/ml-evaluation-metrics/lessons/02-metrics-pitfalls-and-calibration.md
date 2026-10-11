# Metric Pitfalls - When Metrics Lie, How to Validate

## Pitfall 1: Class Imbalance

```
Dataset: 10,000 examples
Frustrated customers: 100 (1%)
Calm customers: 9,900 (99%)

Naive model: "Always predict calm"
Accuracy: 9,900 / 10,000 = 99%

But: Can't detect frustrated at all (recall = 0%)

Why accuracy lied:
Majority class (calm) dominates the metric
Minority class (frustrated) is invisible
```

**Fix: Use precision-recall, not accuracy**

## Pitfall 2: Metric Gaming

```
Model optimizes for F1 score (2021)
Researcher tweaks threshold to maximize F1 on test set
F1 = 0.95 (amazing!)

Deploy to production:
F1 = 0.72 (horrible, what happened?)

Why metric gamed:
- Test set had different distribution than production
- Threshold tuned to test set (overfitted to specific examples)
- Production has different class ratio, different data quality
```

**Fix: Hold-out test set (don't tune on it)**

## Pitfall 3: Distribution Shift

```
Model trained on 2024 data (60% female, 40% male)
Deployed in 2025 (now 50% female, 50% male)

Frustration detection accuracy on women: 92%
Frustration detection accuracy on men: 78%

Model performs worse on men (not enough training data)

Why metric lied:
- Metric averages across groups
- Hidden performance degradation on minority group
- Only noticed when disaggregating
```

**Fix: Stratified evaluation (per subgroup)**

## Pitfall 4: Calibration (Confidence ≠ Correctness)

```
Model predicts:
  Example 1: 95% confidence "frustrated" → actually calm
  Example 2: 95% confidence "calm" → actually frustrated
  Example 3: 95% confidence "frustrated" → actually frustrated

Accuracy: 66% correct
Confidence: 95% on average

Problem:
Model says "I'm 95% sure" but only correct 66% of the time
Confidence is not calibrated to accuracy
```

**Fix: Calibration curve (is model's confidence honest?)**

```
Binned by confidence:
  Model says 90-100%: Correct 85% (not 95%, model overconfident)
  Model says 80-90%: Correct 78% (not 85%, overconfident)
  Model says 70-80%: Correct 71% (good, well-calibrated)

Use calibration curve to adjust confidence:
  If model says 95%, actually interpret as 85%
```

## Pitfall 5: Wrong Metric for the Task

```
Ranking task: "Which customer is most frustrated?"

Model A: AUC=0.95 (99% accurate at ranking)
Model B: AUC=0.92

Choose Model A? Maybe not.

If top 10 customers are what matters:
  Model A: Gets 8 of top 10 frustrated
  Model B: Gets 9 of top 10 frustrated
  
  Model B is better for this use case
  AUC didn't capture it (AUC looks at full ranking)
```

**Fix: Use NDCG@10 (normalized DCG at top 10) for ranking**

## Validation: The Real Test

```
Development cycle:
  1. Train on training set (60%)
  2. Tune hyperparameters on validation set (20%)
  3. Report final metrics on test set (20%)

Never tune on test set!

For a speech-emotion model (evaluation):
  1. Collect 1000 call recordings
  2. Split: 600 train, 200 val, 200 test
  3. Train tone_v2.3 on 600
  4. Tune on 200 val (if needed)
  5. Report F1 on 200 test (hold this sacred)
  6. Compare tone_v2.2 vs tone_v2.3 on same 200 test
  
  Result: Fair comparison, no gaming
```

## Interview Pattern: Metric Pitfalls

```
Q: "Your ML model has 98% accuracy on test set.
   But in production, it underperforms. Why?"

Weak answer:
  "Data drift, need to retrain"
  (❌ Maybe, but not diagnosing the root cause)

Strong answer:
  "Multiple possibilities:
  
  1. Check if accuracy was meaningful:
     - What's the baseline (always predict majority class)?
     - Frustration label: 1% frustrated, 99% calm
     - Baseline accuracy: 99%
     - Model accuracy: 98% (worse than baseline!)
  
  2. Check for overfitting on test set:
     - Was test set metric tuned?
     - If yes: separate hold-out test set needed
  
  3. Check for distribution shift:
     - Training data: 2024 call center (specific accent, language)
     - Production: 2025 (different customer base)
     - Disaggregate accuracy: by region, by age, by language
     - Find: accuracy 98% overall, but 60% on new region
  
  4. Check for calibration:
     - Model says 98% confident
     - But actually only correct 85% of the time
     - Model is overconfident, predictions can't be trusted
  
  5. Check for metric mismatch:
     - Optimized for accuracy (average case)
     - But production cares about recall (catch all frustrated)
     - New metric needed: F1 or precision-recall
  
  6. Diagnosis approach:
     a) Collect new hold-out set (never seen by model)
     b) Disaggregate metrics (by region, demographics, etc.)
     c) Compute confusion matrix (precision, recall, F1)
     d) Check calibration (is confidence honest?)
     e) Compare to baseline (is model better than naive?)
  
  My guess: Distribution shift + metric mismatch
  - Accuracy = 98% is misleading
  - Real metric = F1 or precision-recall (should be lower)
  - Accuracy on new data = probably 70-80%"

Why this signals good judgment:
  - You didn't just blame data drift
  - You understood metric can be misleading
  - You had diagnostic approach (disaggregate, check calibration)
  - You'd establish a proper evaluation process (hold-out test, no tuning)
```

## Checklist: ML Evaluation in Production

- [ ] Choose metric by business goal (not just accuracy)
- [ ] Hold-out test set (never tune on it)
- [ ] Stratified evaluation (check per-subgroup performance)
- [ ] Calibration curve (is confidence honest?)
- [ ] Disaggregate metrics (find hidden problems)
- [ ] Baseline (is model better than naive?)
- [ ] Monitor for drift (does metric change in production?)

## What This Signals

- You've debugged model underperformance (know the pitfalls)
- You understand metrics can mislead (accuracy alone is dangerous)
- You have a robust evaluation process (hold-out test, disaggregation)
- You think about real-world impact (not just test-set numbers)
