# Production AI Systems: Evals, Observability, and Cost Control

## The Core Claim

Every claim about AI-assisted systems making things "faster" is conditional on having a way to know, cheaply and automatically, whether a change made things better or worse. Without that, every prompt tweak is a guess. This is the actual mechanism by which teams get burned by AI.

## Why Evals Matter More Than Model Choice

```
Story 1: Without evals
  - Switched from Sonnet to Haiku (cost down)
  - Thought we measured quality, but didn't use strict metrics
  - Two weeks later: silent quality degradation in 5% of requests
  - Cost savings eaten by 20 hours of firefighting
  
Story 2: With evals
  - Built 50-example golden set (2 hours of work)
  - Before any model/prompt change: run eval
  - Haiku drops from 95% to 87% on our golden set
  - Decision: use mid-tier for this task, not Haiku
  - Cost/quality tradeoff is *explicit*, not a surprise
```

## Minimum Viable Eval Suite (Build This First)

```
Steps:
  1. Collect 20-50 real examples (real user queries, real expected output)
  2. Define scoring:
     - Exact match where possible (did it call the right tool)
     - Structural checks (valid JSON, parsed correctly)
     - LLM-as-judge for subjective quality (is this summary faithful)
  3. Run on every model/prompt change
  4. Track over time (graph: does quality trend down)
```

Effort: 2-4 hours to set up. Payoff: prevents costly regressions.

## Observability for Production AI (What to Log)

| What | Why | Example |
|---|---|---|
| **run_id, model_id, timestamp** | Traceability | `run_20261009_claude_sonnet_1633856...` |
| **tokens_in, tokens_out, cache_hit** | Cost analysis | 1500 in, 200 out, cache_hit=true (counts toward cache cost) |
| **latency_ms** | Performance tracking | P50/P95/P99, not just average |
| **tool_calls[]** | Debugging | Which tools did the agent call, in order |
| **success/failure, error_code** | Incident response | Distinguish model errors from infrastructure errors |
| **tokens_in_cached, tokens_in_uncached** | Cost visibility | Verify prompt caching is actually working |

## Cost Modeling at Scale

```
Example: Document classification, 1M docs/day

Setup:
  - 500 tokens/doc
  - Sonnet at $1/1M input tokens, $5/1M output tokens
  - ~100 tokens output per classification
  
Daily cost WITHOUT optimization:
  - 1M docs × 500 tokens = 500M input tokens
  - 500M × $0.001 = $500/day (input only)
  
Optimization 1: Prompt caching (1 system prompt × 1000 classifications)
  - 95% of calls hit cache (cheap), 5% miss (expensive)
  - New cost: 500M × $0.001 × 0.1 (90% savings) = $50/day
  
Optimization 2: Downgrade to Haiku where accuracy allows
  - Haiku: $0.04/1M input, but fails 3% more often
  - Reclassify failures with Sonnet
  - Net: $30/day, same quality as all-Sonnet
```

## Interview Pattern: Cost Regression

```
Q: "Your AI costs just doubled month-over-month. What do you check first?"

Order of investigation:
  1. Is caching broken? (check cache_hit rate drop)
     - Silent cache-breaker (unstable JSON, random UUID) = silent cost explosion
  
  2. Did round-trip count go up? (are loops deeper than before?)
     - Each extra turn is ~20% more cost
     - Maybe the spec got vaguer or the model got dumber
  
  3. Did effort setting go up? (did someone max-out thinking?)
     - Thinking tokens are 3-4x more expensive than normal tokens
     - Easy to accidentally enable globally
  
  4. Did volume go up? (is this expected scaling?)
     - Measure cost-per-request, not aggregate cost
  
  5. Did you change models? (did someone swap to a more expensive one?)
     - Least common cause, but check
  
Answer to give:
  'I'd instrument with:
    - cost_per_request (not aggregate)
    - cache_hit_rate
    - avg_tokens_per_request
    - effort_level distribution
  
  Then correlate the doubling to which metric changed.
  
  Example: cost_per_request went from $0.02 to $0.04 last Tuesday
  and cache_hit_rate dropped from 80% to 20%. Root cause: 
  model output became non-deterministic, breaking cache prefix match.
  Fix: emit stable tool descriptions.'"
```

## Evals for Different Domains

```
Trading: backtesting the decision
  - Real historical trades where you know the outcome
  - Score: does your system decide correctly on past data?
  
AI Labs: task completion rate
  - Did the experiment run to completion without crashing?
  - Did the training converge?
  - Separate from quality (convergence is binary)

SaaS: customer-reported quality
  - Track: % of outputs users accepted without edit
  - Sample output for manual review (1% spot check)
```

## What Metrics Actually Matter

Don't measure:
- Benchmark scores (MMLU, etc.) — these don't correlate with your task
- Average latency — P99 is what breaks your SLO
- Input token count — care about *cost per successful request*

Do measure:
- Task completion rate (did the agent finish the job?)
- Quality metric you actually care about (accuracy, user acceptance rate, pass tests?)
- Cost per successful request (including retries, errors)
- Time to first token (user-perceived latency)

## Stub Content

- **How to instrument evals in CI** — running eval on every PR/deploy
- **LLM-as-judge patterns** — when safe, when risky, how to validate the judge itself
- **Regression testing** — golden sets that grow from production failures
- **Cost dashboards** — tracking spend per team/task/model
- **Observability tools** — Langfuse, Helicone, custom solutions

The theme: **you can't optimize what you don't measure.**
