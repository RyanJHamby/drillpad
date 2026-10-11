# LLM-as-Judge Reliability: Bias, Drift, and Deployment Gating

## The Problem: Using an AI to Judge AI

You evaluate your model with an LLM-as-judge (using GPT-4 or Claude to score outputs).

```
Your model output: "The tone was frustrated."
Judge (GPT-4): "Correct, I agree."

Your model output: "The tone was frustrated."
Judge (Claude 3): "Incorrect, actually calm."

Same output, different judges disagree.
Who's right? Can you trust either?
```

**LLM-as-judge is powerful** (can evaluate nuanced tasks like tone, coherence, safety).

**But it's brittle** (sensitive to prompt wording, context, model version).

This lesson teaches how to measure judge reliability and gate deployments safely.

## Sources of Judge Bias

### Bias 1: Prompt Sensitivity

```python
# Prompt A: Strict framing
prompt_A = """
Rate the response quality: 0-10.
Respond with only the number.
Positive examples: clear, concise, factual.
Negative examples: vague, rambling, inaccurate.
Response: {output}
"""

# Prompt B: Lenient framing
prompt_B = """
Rate the response quality: 0-10.
Be generous in scoring.
Even partially correct answers deserve credit.
Response: {output}
"""

Same response, different prompts:
  Prompt A: score=6 (strict, penalizes rambling)
  Prompt B: score=8 (lenient, rewards any effort)
```

**Impact:** Same model can appear to improve or regress based on prompt rewording.

### Bias 2: Position Bias

```python
# Prompt variant A: Your model first
prompt = """
Response A: {your_model}
Response B: {baseline_model}

Which is better? A or B?
"""
→ LLM-as-judge picks A more often (first position bias)

# Prompt variant B: Baseline first
prompt = """
Response A: {baseline_model}
Response B: {your_model}

Which is better? A or B?
"""
→ LLM-as-judge picks A more often (first position bias)

Result: Same judge, different orders → different decisions!
```

**Impact:** You can make any model look good by putting it first.

### Bias 3: Model Version Sensitivity

```
Same response, different judge models:
  GPT-4 (June 2023): score=8
  GPT-4 Turbo (Nov 2023): score=7
  GPT-4 Vision (April 2024): score=6
  
Scores drift over time (model updates, safety training changes).
Can't compare evaluations across different judge versions.
```

### Bias 4: Context Window Effects

```python
# Short context
judge.score("Great job")
→ score=9

# Long context (history of bad examples)
history = [bad_output_1, bad_output_2, bad_output_3, ...]
judge.score(history + "Great job")
→ score=6 (recency bias, anchored by bad examples)
```

**Impact:** Same output scores differently depending on context length/order.

## Measuring Judge Reliability

### Test 1: Judge Consistency (Does it agree with itself?)

```python
def test_judge_consistency():
  test_case = "The customer was frustrated."
  
  # Ask judge 3 times
  score_1 = judge.evaluate(test_case)
  score_2 = judge.evaluate(test_case)
  score_3 = judge.evaluate(test_case)
  
  # Did it give the same answer?
  if score_1 == score_2 == score_3:
    print("Judge is consistent ✓")
  else:
    print("Judge is noisy ✗")
    # e.g., [7, 8, 7] → std_dev=0.5 (some variance OK)
```

**Metric:** std_dev of repeated scores
- std_dev < 0.5 (out of 10): good consistency
- std_dev > 1.0: unreliable judge

### Test 2: Judge Agreement (Do different judges agree?)

```python
def test_judge_agreement():
  test_case = "The customer was frustrated."
  
  # Ask multiple judges
  score_gpt4 = gpt4_judge.evaluate(test_case)
  score_claude = claude_judge.evaluate(test_case)
  score_human = human_rater.evaluate(test_case)
  
  # Are they correlated?
  correlation(score_gpt4, score_human)  # Should be > 0.85
```

**Metric:** Correlation with human labels
- correlation > 0.85: judge is reliable
- correlation < 0.7: judge is worse than coin flip

### Test 3: Robustness to Prompts

```python
def test_prompt_robustness():
  test_case = "The customer was frustrated."
  
  # 5 different prompt variants
  prompts = [
    "Rate quality 0-10",
    "Rate quality: 1 (bad) to 10 (excellent)",
    "Is this good? Yes/No",
    "Score this response",
    "What's your assessment?"
  ]
  
  scores = [judge.evaluate(p.format(output=test_case)) for p in prompts]
  
  # Large variance = prompt-sensitive
  std_dev = numpy.std(scores)
  if std_dev > 1.0:
    print("Judge is prompt-sensitive ✗")
```

**Metric:** std_dev of scores across prompt variants
- std_dev < 0.5: robust
- std_dev > 1.5: unreliable, don't use

### Test 4: Position Bias

```python
def test_position_bias():
  modelA = "output from model A"
  modelB = "output from model B"
  
  # Order 1: A first
  score_A_first = judge.compare(modelA, modelB)
  
  # Order 2: B first
  score_B_first = judge.compare(modelB, modelA)
  
  # If position-biased:
  # A always wins when first
  if score_A_first > score_B_first:
    print("Judge has position bias ✗")
```

**Mitigation:** Reverse prompt order in half your evaluations, average the results.

### Test 5: Drift Detection (Does judge behavior change over time?)

```python
def test_judge_drift():
  # Evaluate same set of outputs weekly
  
  Week 1: [8, 7, 9, 6, 8]  → mean=7.6
  Week 2: [7, 6, 8, 5, 7]  → mean=6.6
  Week 3: [6, 5, 7, 4, 6]  → mean=5.6
  
  Trend: mean dropping 1 point/week
  
  # Drift detected!
  if trend_slope < -0.5:
    print("Judge is drifting ✗")
```

**What causes drift?**
- Model version updates (GPT-4 changes)
- Safety fine-tuning changes judge behavior
- Market changes (what's considered "good" evolves)

**Impact:** Metrics reported in Week 1 are not comparable to Week 3.

## Gating Strategy: When Can You Trust the Judge?

```
Before shipping a model based on LLM-as-judge eval:

✓ Judge passes consistency test (std_dev < 0.5)
✓ Judge correlates with humans (correlation > 0.85)
✓ Judge is robust to prompts (prompt std_dev < 0.5)
✓ No position bias detected
✓ No recent drift detected
✓ New model > baseline by >= 2 points (to be safe from noise)

If any ✗:
  → Don't use judge-based eval for gating
  → Fall back to human eval or other methods
```

## Practical Implementation: Multi-Judge Voting

Instead of trusting one judge, use multiple judges and vote.

```python
def multi_judge_eval(output, judges=[gpt4, claude3, claude2]):
  scores = []
  
  for judge in judges:
    score = judge.evaluate(output)
    scores.append(score)
  
  # Voting strategies
  mean_score = mean(scores)        # [7, 8, 6] → 7.0
  median_score = median(scores)    # [7, 8, 6] → 7.0
  majority_vote = mode(scores)     # [good, good, bad] → good
  
  # Report all three
  return {
    "mean": mean_score,
    "median": median_score,
    "agreement": len(set(scores)),  # 3 different? low agreement
  }
```

**Advantages:**
- Reduces impact of any single judge's bias
- Detects disagreement (red flag)
- More reliable than single judge

**Disadvantages:**
- 3x cost (3 API calls instead of 1)

## Diagrams

### Judge Reliability Matrix

```
Judge Properties        Good           Bad
─────────────────────────────────────────────
Consistency            std_dev < 0.5  std_dev > 1.0
Human agreement        r > 0.85       r < 0.7
Prompt robustness      std_dev < 0.5  std_dev > 1.5
Position bias          None detected  Favors first
Drift detection        Stable         Dropping/rising

Verdict:               ✓ Use for      ✗ Don't use
                       gating         for gating
```

### Judge Drift Over Time

```
Week 1: Eval baseline model
  Human: 8/10
  Judge: 8/10
  Agreement: ✓

Week 2: Eval new model
  Human: 9/10
  Judge: 8/10 (should be higher)
  Agreement: ?
  
Week 3: Check baseline again (sanity check)
  Human: 8/10
  Judge: 7/10 (was 8 last week!)
  Agreement: ✗
  
Conclusion: Judge drifted -1 point/week
  Metrics from Week 1 incomparable to Week 3
  Can't trust judge for long-term comparisons
```

### Multi-Judge Voting Example

```
Output: "The customer seemed frustrated."

Judge 1 (GPT-4):      score=8 (good response)
Judge 2 (Claude 3):   score=7 (decent, slightly vague)
Judge 3 (Claude 2):   score=6 (okay, could be better)

Results:
  Mean: 7.0
  Median: 7.0
  Std_dev: 0.8 (moderate disagreement)
  
Interpretation:
  Judges mostly agree (std_dev < 1.0)
  Score ~7 is likely reliable
  Can use this for gating (with caution)

Compare to baseline:
  Baseline score was 6.0
  New model 7.0 vs baseline 6.0 = +1 improvement
  Within noise margin (std_dev 0.8)
  Marginal win, probably ship but monitor
```

## Interview Section

### Q1: You're evaluating a frustration-detection model. You use GPT-4-as-judge. In production, the judge sometimes gives contradictory scores for very similar inputs. How do you debug this?

**Weak answer:** "Try a different prompt."

**Strong answer:**
"Steps to diagnose:

1. Reproduce the issue
   - Collect pairs of similar inputs with contradictory scores
   - Example: input_A scores 8, input_B (very similar) scores 3
   
2. Test judge consistency
   - Run judge 10 times on same input
   - Measure std_dev of scores
   - If std_dev > 1.0: judge is too noisy
   
3. Test prompt sensitivity
   - Run 5 prompt variants on same input
   - Check if scores vary wildly
   - If yes: reword prompt for clarity
   
4. Check for position bias
   - Swap A and B order
   - Does judge now score B high and A low?
   - If yes: use randomized order
   
5. Detect drift
   - Are these contradictions new?
   - Did judge scores drop 1-2 points recently?
   - If yes: GPT-4 version updated, judge is drifting
   
6. Mitigation options:
   a) Use multi-judge voting (3 judges, vote)
   b) Fall back to human eval for borderline cases (score 4-6)
   c) Add clearer examples to prompt (few-shot prompting)
   d) Switch to different judge (Claude instead of GPT-4)
   e) Use different metric (not judge-based, e.g., heuristics)
   
7. Gate on confidence:
   - Judge only for high-confidence cases (score 0-2, 8-10)
   - Don't gate on borderline cases (score 4-6)

Example gating logic:
  if judge_score <= 2 or judge_score >= 8:
    # High confidence, OK to gate
    if judge_score >= 8:
      approve_deployment()
  else:
    # Borderline, need human review
    escalate_to_human()"

### Q2: How can you detect judge drift before it breaks your model evaluation?

**Weak answer:** "Keep an eye on the metrics."

**Strong answer:**
"Setup continuous monitoring:

1. Baseline set (100 examples, golden standard):
   - These are examples with human labels you trust
   - Run judge on them every week
   - Track mean judge score over time
   
2. Detect drift:
   ```python
   scores_by_week = {
     'week_1': [8, 7, 9, 8, 7],  # mean=7.8
     'week_2': [7, 6, 8, 7, 6],  # mean=6.8 (down 1 point!)
     'week_3': [6, 5, 7, 6, 5],  # mean=5.8 (down 1 more!)
   }
   
   trend = linear_regression(weeks, means)
   if trend.slope < -0.3:  # Dropping > 0.3 points/week
     alert('Judge is drifting ✗')
   ```
   
3. Correlation with humans:
   - Weekly, correlate judge scores with human labels
   - Track correlation over time
   - If correlation drops from 0.9 to 0.7: drift detected
   
4. Action plan:
   - Alert if drift detected
   - Pause model deployments (fall back to human eval)
   - Investigate cause:
     - Did GPT-4 version change? (check in logs)
     - Did safety training change? (check release notes)
     - Did prompt get modified? (version control)
   - Re-calibrate or switch judges
   
5. Prevention:
   - Use multi-judge voting (reduces impact of single drift)
   - Version your prompts in git
   - Track judge version (GPT-4 June vs Sept)
   - Never change judge mid-evaluation cycle

Example: Detecting drift with statistical test
  Week 1 baseline: mean=7.8, std_dev=0.5
  Week 3 observed: mean=5.8, std_dev=0.6
  
  T-test: is difference significant?
  t = (7.8 - 5.8) / sqrt((0.5^2 + 0.6^2) / n)
  
  If p < 0.05: drift is real (not noise)"

### Q3: You have 1000 test cases. Evaluating with human raters costs $50 per case. Using GPT-4-as-judge costs $0.001 per case. But you worry judge is unreliable. What's your strategy?

**Weak answer:** "Use GPT-4 to save money."

**Strong answer:**
"Hybrid approach:

Phase 1: Validate judge against humans (small sample)
  - Evaluate 50 cases with both human raters and GPT-4
  - Cost: 50 × $50 = $2,500
  - Check correlation: is judge > 0.85 correlated with humans?
  
  If correlation > 0.85:
    Judge is reliable, proceed to Phase 2
  If correlation < 0.7:
    Judge is worse than baseline, don't use
  If correlation 0.7-0.85:
    Judge is okay, proceed cautiously

Phase 2: Judge-based eval with human spot-checks
  - Use GPT-4 to evaluate all 1000 cases
  - Cost: 1000 × $0.001 = $1
  - Spot-check 100 borderline cases (judge score 4-6) with humans
  - Cost: 100 × $50 = $5,000
  - Total: ~$7,500 (vs $50K if all human)
  
  Verify agreement:
  if human_spot_check_agreement > 0.8:
    High confidence in judge results
  else:
    Escalate remaining borderline cases to humans

Phase 3: Continuous validation
  - Every month: re-validate judge on new cases
  - Cost: 50 × $50 = $2,500/month
  - If correlation drops below 0.80: switch judges or revert to humans
  
Cost-benefit:
  All humans: $50,000
  Hybrid approach: $7,500 (first eval) + $2,500/month (ongoing)
  
  Savings: $42,500 (first eval), $47,500/month after
  Risk: judge unreliability detected early (spot-checks catch it)"

### Q4: Numeric Exercise: Multi-Judge Voting Cost

You have:
- 1000 test cases to evaluate
- GPT-4 costs $0.001 per evaluation
- Claude Opus costs $0.003 per evaluation
- Human rater costs $50 per evaluation

Options:
1. Single judge (GPT-4): 1000 × $0.001 = $1
2. Two judges (GPT-4 + Claude): 1000 × ($0.001 + $0.003) = $4
3. All human: 1000 × $50 = $50,000

Trade-off:

Option 1 (Single judge):
  Cost: $1
  Reliability: ~70% accurate (prone to bias)
  Shipping risk: HIGH (might deploy bad model)
  
Option 2 (Two judges):
  Cost: $4
  Reliability: ~85% accurate (voting reduces individual bias)
  Shipping risk: MEDIUM (most bad models caught)
  
Option 3 (All human):
  Cost: $50,000
  Reliability: ~95% accurate
  Shipping risk: LOW
  
Decision:
  If model ships bad → customer impact = $100K
  Option 1: 30% fail rate × $100K = $30K expected loss
  Option 2: 15% fail rate × $100K = $15K expected loss
  Option 3: 5% fail rate × $100K = $5K expected loss
  
  Expected cost:
  Option 1: $1 + $30K = $30.001
  Option 2: $4 + $15K = $15.004
  Option 3: $50K + $5K = $55K
  
  Recommendation: Option 2 (multi-judge) is most cost-effective"

## When to Use / When NOT

| Judge Type | Good For | Bad For |
|-----------|----------|---------|
| GPT-4-as-judge | Initial screening, bulk eval | Gating production deployments |
| Multiple judges (voting) | Important decisions | Real-time scoring (too slow) |
| Humans | Ground truth, edge cases | Scaling to 1000+ cases |
| Hybrid (judge + human) | Balancing cost/reliability | Simple yes/no decisions |
| Heuristic rules | Fast, reproducible | Nuanced judgments |

## Checklist: Judge Reliability for Production

- [ ] Judge consistency tested (std_dev < 0.5)?
- [ ] Judge correlates with humans (r > 0.85)?
- [ ] Judge robust to prompt variants?
- [ ] Position bias tested and mitigated?
- [ ] Drift detection in place (weekly checks)?
- [ ] Multiple judges used (voting) for critical decisions?
- [ ] Confidence gating (don't gate on borderline scores)?
- [ ] Fallback to human eval for disagreements?
- [ ] Judge version pinned (not auto-updating)?
- [ ] Human spot-checks done before deployment?

## Common Wrong Answers

1. "GPT-4 is always reliable." → NO, prone to prompt sensitivity, drift.
2. "One judge is enough." → RISKY, use multi-judge voting.
3. "Judge scores are deterministic." → NO, there's variance, need consistency test.
4. "You can ignore position bias." → NO, it swings scores ±1-2 points.
5. "Drift only happens with model updates." → NO, happens continuously over time.
6. "High accuracy on judge equals production reliability." → NO, need human spot-check.
7. "Use LLM-as-judge for real-time scoring." → NO, too slow (API latency 1-5 sec).
