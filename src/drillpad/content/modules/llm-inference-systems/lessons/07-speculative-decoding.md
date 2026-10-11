# Speculative Decoding: Latency Reduction via Draft Models & Verification

## The Problem: Decode Latency is Sequential

LLM inference is inherently sequential: each token is generated one at a time, and the next token depends on all previous tokens.

```
Standard autoregressive decode:

Generate token 1:
  Forward pass: input_ids → logits → sample token 1
  Latency: 100 ms (forward pass time on H100 for 70B)

Generate token 2:
  Forward pass: [input_ids, token_1] → logits → sample token 2
  Latency: 100 ms

Generate token 3:
  Forward pass: [input_ids, token_1, token_2] → logits → sample token 3
  Latency: 100 ms

Total for 10 tokens: 1000 ms
Throughput: 10 tokens per second (for a single user)

Problem: You can't parallelize token generation across time.
You CAN parallelize across batch (multiple users), but each user sees latency = #tokens * 100ms.
```

**User experience impact:**
- Latency to first token (TTFT): 100 ms (good)
- Latency per token (TPOT): 100 ms (slow)
- For a 100-token response: 10 seconds total (unacceptable for interactive use)

---

## Speculative Decoding: Gamble on Token Prediction

**Key insight:** Use a small, fast draft model to **predict multiple tokens ahead**, then verify them with the main model in **one batch**.

```
Draft model strategy:

1. Draft model generates K candidate tokens (e.g., K=4) very fast
   Small model (7B): ~10 ms per token
   Time: 4 tokens * 10 ms = 40 ms

2. Main model verifies all K tokens in one batch forward pass
   Main model (70B): 100 ms for a batch of 4
   Time: 100 ms

3. Sampling/verification:
   If tokens 1–3 match the main model's top-1, accept them.
   Token 4 might mismatch; verify or fall back.

4. Append accepted tokens, continue from there.

Total: 40 ms (draft) + 100 ms (verify) = 140 ms for 1–4 tokens
Speedup: 4 tokens in 140 ms = 28 tokens/sec
vs standard: 1 token per 100 ms = 10 tokens/sec
→ 2.8x speedup!
```

**Diagram of the process:**

```
Standard decode (no speculation):
  Step 1: Model(input) → token_1      [100 ms]
  Step 2: Model(input, token_1) → token_2      [100 ms]
  Step 3: Model(input, token_1, token_2) → token_3      [100 ms]
  Total: 300 ms for 3 tokens

Speculative decode:
  Step 1: Draft(input) → [token_1, token_2, token_3, token_4]  [40 ms]
  Step 2: Main(input, [token_1..4]) → verify all 4  [100 ms]
  Step 3: Accept [token_1, token_2, token_3], reject token_4
  Step 4: Draft(input, token_1, token_2, token_3) → [token_5..8]  [40 ms]
  Step 5: Main verify  [100 ms]
  Total: 280 ms for 7 tokens (vs 700 ms standard)
```

---

## Verification: When Does Speculation Succeed?

The draft model's predictions are verified by the main model.

```
Probability of acceptance (per token):

Let p_token = prob that draft matches main model's top-1.

Example: draft model is 7B, main is 70B. They're similar but not identical.
p_token ≈ 0.7 (70% of tokens draft guesses correctly)

For K candidate tokens:
  p_success = p_token^K = 0.7^4 = 0.24 (only 24% of 4-token sequences pass)

Implication:
  If you speculate 4 tokens, most will need fallback.
  Better: speculate 1–2 tokens per round (higher acceptance rate).
```

**Acceptance criteria:**

```
Token is accepted if:
  1. Matching: draft_token == main_model_argmax(logits)
     OR
  2. Probabilistic: draft_token in top-k of main model (k=5)
     AND sampled token is draft_token

If any token in the sequence is rejected:
  Truncate at that position, use main model's sample instead.
  Continue speculation from there.
```

---

## Architecture: Draft Model Selection

```
Option 1: Same model, pruned weights (9–10% speedup)
  Pros: Minimal memory overhead
  Cons: Minimal speedup; still slow

Option 2: Smaller model, same family (7B for 70B)
  Pros: 10–15x speedup (7B is much faster)
  Cons: More memory (need both models loaded)
  Tradeoff: Load both on separate GPUs or re-load fast

Option 3: Distilled model (trained to match 70B)
  Pros: Better alignment with main model
  Cons: Need training data, latency to train

Option 4: Lookahead encoding (linear draft predictor)
  Pros: No separate model; pure compute
  Cons: Lower quality predictions (~50% accuracy)
```

**Real example (Medusa, 2023):**
```
Main model: Llama 70B
Draft approach: Medusa heads (small linear layers predicting k-ahead)
  Each head predicts the next token, given the current token's embedding.
  Cost: ~20% overhead on forward pass, but parallelizes k tokens.

Speedup: 2.2x (for 4-token speculation)
Advantage: No separate model, runs in parallel with main forward.
```

---

## Story: Improving TTFT vs TPOT

**Setup:** Streaming chat API (like Claude). P99 latency requirement: 500 ms per response.

**Initial:** 
```
Main model: 70B on H100
TTFT (time to first token): 100 ms ✓
TPOT (time per token): 100 ms
Avg response: 50 tokens = 5000 ms ✗ (over budget)
```

**Problem:** Users see first token quickly, but subsequent tokens take forever.

**Solution:** Add speculative decoding.

```
Draft model: 7B on second H100 (or cheaper H10)
Speculation: K=4 tokens per round

Results:
  TTFT: still ~100 ms (draft + verify first batch)
  TPOT: 140 ms / 4 tokens = 35 ms average
  Avg response (50 tokens): ~2000 ms ✓ (under budget)
```

**Trade-off:** Need a second GPU for draft model (~$15K hardware vs software fix).

---

## When to Use Speculative Decoding

| Scenario | Use Speculative Decoding? | Why |
|----------|-------|-----|
| Streaming chat (single-user) | YES | Reduces TPOT dramatically |
| Batch inference (precompute, not latency-critical) | NO | Slows down total throughput |
| Limited GPU memory | MAYBE | Two models require ~2x VRAM |
| Long context (4K+ tokens) | YES | Amortizes draft cost |
| Short responses (< 20 tokens) | NO | Overhead of draft setup > benefit |
| Main model very accurate (near human) | YES | Draft can still predict many tokens |
| Draft model mismatched (7B vs 70B) | MAYBE | Lower acceptance rate, need more rounds |

---

## Q&A (Real Interview Depth)

**Recall 1:** Why does speculative decoding improve latency per token?

*Must-say:*
- Standard: generate 1 token in 100 ms.
- Speculative: draft 4 tokens in 40 ms, verify all 4 in 100 ms.
- If 70% accept, you get ~2–3 tokens verified per round.
- Amortized: 3 tokens / 140 ms ≈ 21 ms per token (vs 100 ms).
- Key: verify all candidates in ONE batch (parallelism), not sequentially.

*Interview-style context:* "Your chat endpoint has SLO of 50 ms per token. You're at 100 ms. Will speculative decoding help?"

**Probe 1:** You have a 7B draft model and 70B main. Draft generates 4 tokens. Accuracy is 60% per token. How many tokens are likely accepted in one round?

*Expected:*
- Acceptance rate: 0.6^4 = 0.1296 (only ~13% of 4-token sequences fully match)
- But partial acceptance: first token (60%), first 2 (36%), first 3 (22%).
- On average: 1.5–2 tokens accepted per round.
- Conclusion: speculation depth of 4 is aggressive for 60% accuracy. Better to use K=2.

**Numeric 1:** Draft model takes 5 ms per token, main model takes 80 ms per batch of 4. Speculation depth K=3. How many tokens/sec?

*Working:*
- Draft: 3 * 5 = 15 ms
- Verify: 80 ms (for batch of 4)
- Total: 95 ms for 3–4 tokens (if acceptance is high)
- Throughput: 3.5 / 95 ms = 37 tokens/sec
- Standard (80 ms per token): 12.5 tokens/sec
- Speedup: 2.9x

**Numeric 2:** Acceptance rate is 50% per token. You speculate K=5. What's the expected number of tokens accepted?

*Working:*
- P(all 5 match) = 0.5^5 = 0.03 (3%)
- Expected accepted = 0 + 0.5 * 1 + 0.5^2 * 2 + ... = sum over partial matches
- Simpler: E[# accepted] = sum(p^k for k=1..5) ≈ 0.5 + 0.25 + 0.125 + 0.0625 + 0.03 ≈ 2.0
- So ~2 tokens per round, 2 * K=5 speedup vs standard if rounds overlap perfectly

**Story:** Medusa (Song et al., 2023) showed that even simple head predictors (no separate draft model) can achieve 2–2.5x speedup. The bottleneck isn't the draft model quality, but latency hiding via parallelism.

---

## Checklist & Common Pitfalls

- [ ] **Measure acceptance rates, not just expected value.** You might see p50=70% but p99=40%. Tail matters.
- [ ] **Ensure draft & main models fit in memory together** (or fast reload).
- [ ] **Tune speculation depth (K) for your acceptance rate.** If K=4 but acceptance is 20%, reduce to K=2.
- [ ] **Compare against batch prefill on the same GPU.** Sometimes batching is faster than speculation.
- [ ] **Handle fallback gracefully.** If draft fails, you need to recover the main model's sample, not crash.

**Common wrong answer:** "Speculative decoding always gives 2–4x speedup."
*Corrected:* "Speedup depends on acceptance rates and draft model quality. Aggressive speculation (K=8) might fail if draft is mismatched."

---

## References & Next Steps

- Read Medusa paper (Song et al., 2023) for practical head-based prediction.
- Implement a simple draft model using weight pruning or distillation.
- Profile your system: what's TTFT vs TPOT? Optimize the bottleneck.
