# Choosing the Right Metric - Precision, Recall, F1, AUC, Custom

## The Core Question

Trained two models. Which is better?

```
Model A: Correct on 95% of examples (accuracy = 95%)
Model B: Correct on 92% of examples (accuracy = 92%)

Answer: Model A is better (95% > 92%)

Real world is harder.
```

## Classification Metrics: The Confusion Matrix

```
Binary classification: Did the model detect frustration? (Yes/No)

             Predicted Yes    Predicted No
Actual Yes:  TP (90)         FN (10)       ← True Positives, False Negatives
Actual No:   FP (5),          TN (895)      ← False Positives, True Negatives

Total: 1000 examples
```

### Precision: Of the ones we said "Yes", how many were right?

```
Precision = TP / (TP + FP) = 90 / (90 + 5) = 94.7%

Interpretation: "When the model says 'frustrated', it's correct 94.7% of the time"

Use case: a speech-emotion product (false positive = wrong business decision)
  If we wrongly flag a calm customer as frustrated,
  We might over-service them (waste resources)
  Precision matters more than recall
```

### Recall: Of the actual "Yes", how many did we find?

```
Recall = TP / (TP + FN) = 90 / (90 + 10) = 90%

Interpretation: "Of all truly frustrated customers, we found 90%"

Use case: Medical (false negative = missed diagnosis)
  If we miss a truly sick patient,
  They don't get treatment (dangerous)
  Recall matters more than precision
```

### F1 Score: Harmonic mean of precision and recall

```
F1 = 2 * (Precision * Recall) / (Precision + Recall)
   = 2 * (0.947 * 0.90) / (0.947 + 0.90)
   = 0.924

Use case: Balanced tradeoff when precision and recall both matter
```

### AUC (Area Under Curve): Ranking metric

```
Classifier gives probability: 0.95 (very confident yes), 0.75, 0.3, 0.1 (very confident no)

Rank by probability, threshold at different points:
  Threshold 0.95: Catch only highest confidence (high precision, low recall)
  Threshold 0.5: Catch medium confidence (balanced)
  Threshold 0.0: Catch everything (low precision, high recall)

AUC = 0.91: Under the curve from recall=0% to recall=100%

Use case: Compare models when threshold is unknown
```

## Worked Example: Tone Detection

```
Model A: Frustration detection
  Precision: 92% (of detected frustrated, 92% are truly frustrated)
  Recall: 85% (of actual frustrated, we detect 85%)
  
Model B: New version
  Precision: 88% (slightly worse)
  Recall: 92% (better at catching frustrated)

Which is better?

Depends on business goal:
  Goal 1: Avoid wasting resources on false positives
    → Use Model A (higher precision)
  
  Goal 2: Catch as many frustrated as possible
    → Use Model B (higher recall)
  
  Goal 3: Balanced
    → Use F1 score (Model A F1=0.885, Model B F1=0.899)
    → Model B wins (slightly)
```

## Custom Metrics: Domain-Specific

```
A speech-AI team wants to measure tone quality. Options:

Option 1: Frustration detection accuracy
  - Easy to compute (binary classification)
  - Limited (only captures frustration)

Option 2: Custom metric: "Tone clarity"
  - Measure: "Can human experts agree with model?"
  - Compute: Inter-rater agreement (Cohen's kappa)
  - Interpretation: 0.85 = good agreement

Option 3: Business metric
  - Measure: "Do customers improve after tone feedback?"
  - Compute: Conversion rate before/after model deployment
  - Interpretation: 15% improvement in resolution rate

Which to optimize?
  - Option 1: Technical (fast to compute)
  - Option 2: More realistic (human judgment)
  - Option 3: True goal (business impact)
  
  Best: Use all three
  1. Optimize Option 1 and 2 (technical proxy)
  2. Validate with Option 3 (true goal)
```

## Computing Metrics: At Scale

```
1 million test examples
Compute precision for each threshold (0.0 to 1.0, step 0.01)

Loop:
  for threshold in [0.0, 0.01, ..., 1.0]:
    tp = count(prediction >= threshold AND actual == yes)
    fp = count(prediction >= threshold AND actual == no)
    precision = tp / (tp + fp)

Cost: O(N * thresholds) = 1M * 100 = 100M operations (~1 second)

At scale: Batch compute, cache results
```

## Interview Pattern: Metric Selection

```
Q: "Compare two tone models. Model A: 90% accuracy. Model B: 88% accuracy.
   Which is better?"

Weak answer:
  "Model A (90% > 88%)"
  (❌ Accuracy alone hides the real tradeoff)

Strong answer:
  "Need to know the tradeoff:
  
  1. Confusion matrices:
     Model A: TP=900, FP=50, FN=100, TN=8950 (accuracy 90%)
     Model B: TP=920, FP=20, FN=80, TN=8980 (accuracy 88%)
  
  2. Metrics:
     Model A: Precision=94.7%, Recall=90.0%
     Model B: Precision=97.9%, Recall=92.0%
  
  3. Interpretation:
     Model A: Less precise (might misclassify calm as frustrated)
     Model B: More precise, better recall
  
  4. Business question: What costs more?
     False positive (wrongly flag as frustrated): $10 (unnecessary service)
     False negative (miss frustrated): $100 (lose customer)
     
     Model A cost: 50*$10 + 100*$100 = $10,500
     Model B cost: 20*$10 + 80*$100 = $8,200
     
     Model B is better (saves $2,300)
  
  5. Decision: Use Model B
     Higher precision + recall, lower business cost
     Accuracy alone was misleading"

Why this signals good judgment:
  - You didn't stop at accuracy
  - You computed confusion matrix (found the real tradeoff)
  - You thought about business impact (not just metrics)
  - You had a decision framework (cost-based)
```

## What This Signals

- You understand precision-recall tradeoff (not just accuracy)
- You can choose metrics by business goal (not arbitrarily)
- You think about custom metrics (domain-specific reality)
- You validate metrics on held-out data (not training data)
