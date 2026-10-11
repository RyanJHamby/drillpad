# Structured Output & Constrained Decoding

## Problem

LLM outputs free text. Need JSON schema. Stop token not enough.

Solution: constrained decoding (limit logits to valid tokens).

## Method 1: Logit Masking

```
Grammar: JSON object {name: "...", age: <number>}

At each step:
  ├─ Compute logits for all tokens
  ├─ Check: is this token allowed at this position?
  ├─ If yes: keep logit
  ├─ If no: set logit = -inf (no chance to sample)
  ├─ Sample from allowed tokens
  └─ Repeat

Example (parsing "name"):
  State: {"name":
  Valid next: " (quote)
  Logits: "a" -inf, "b" -inf, ..., " " normal, ...
  Result: only space can be sampled

Cost:
  ├─ Mask validation: O(vocab) per token = cheap
  ├─ Slowdown: ~5-10% (logit masking overhead)
  └─ Benefit: guaranteed valid JSON
```

## Method 2: Regex/FSM

```
Regex: [A-Z][a-z]+ (capitalized word)

Build FSM:
  State 0: start
  State 1: saw uppercase (→ State 2)
  State 2: need lowercase (→ State 2 or end)
  State 3: accept

At each step:
  ├─ Current state: 0
  ├─ Valid transitions: uppercase letters
  ├─ Mask logits: only those letters
  ├─ Sample: only valid continuation
  └─ Update state

Benefit:
  ├─ Fast (FSM is O(1) per token)
  ├─ Works for complex patterns
  └─ Guaranteed regex-compliant output
```

## Serving Cost

```
Latency impact:

Without constraints:
  ├─ Generation: 100 tokens in 2 seconds
  ├─ Post-processing: parse JSON (may fail)
  └─ Total: 2 sec + retry if invalid

With logit masking:
  ├─ Masking per token: 5ms overhead
  ├─ Generation: 100 tokens, 5ms each = 500ms extra
  ├─ Total: 2 sec + 0.5 sec = 2.5 sec (25% slower)

Alternative: post-process and retry
  ├─ Invalid output: 50% chance
  ├─ Retry: 2 sec per retry
  ├─ Expected: 1 * 2 + 0.5 * (2 + 2) + 0.25 * (2+2+2) = 5 seconds
  └─ Constrained faster (2.5 sec vs 5 sec)
```

---

## Interview Checklist

- [ ] Constrained decoding: logit masking or FSM
- [ ] Cost: 5-10% slower than unconstrained
- [ ] Benefit: 100% valid JSON guaranteed
- [ ] Trade-off: latency vs correctness

## Common Wrong Answers

- ❌ "Parse output after generation" — fragile, retry loops
- ❌ "No overhead to constrain" — 5-10% slowdown
- ❌ "Constraints prevent good generation" — minimal impact
