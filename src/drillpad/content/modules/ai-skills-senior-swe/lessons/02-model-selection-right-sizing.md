# Model Selection and Right-Sizing: Decision Trees and Cost Reasoning

## Why This Matters in Interviews

Model selection is where you prove you understand the actual economics of AI systems, not just the theory. Getting it wrong costs 10x, sometimes 100x. Getting it right is the single highest-leverage cost optimization most teams never do.

## The Simple Decision Tree (Memorize This)

```
Do you need to self-host / fine-tune / air-gap?
  └─ YES → open-weight (Llama/DeepSeek/Qwen) via vLLM, ignore rest of tree
  └─ NO ↓

Is the task mostly "ingest huge context, ask one thing"?
  └─ YES → Gemini (long context is real structural advantage here)
  └─ NO ↓

Is this agentic coding / long-horizon autonomous work?
  └─ YES → Claude (Opus for hard tasks, Sonnet for routine)
  └─ NO ↓

Do you need ecosystem / integrations / voice-first?
  └─ YES → OpenAI
  └─ NO ↓

Default to whichever you already have eval coverage on.
(Switching without evals = switching blind)
```

## Within a Provider: The Tier Table

| Tier | Example | Use | Cost Signal | Decision |
|---|---|---|---|---|
| **Flagship** | Claude Opus, GPT-4, Gemini Pro | Hard reasoning, long-horizon code, anything expensive to get wrong | $10-20 per 1M tokens | Start here if unsure, then downgrade once you measure |
| **Mid** | Claude Sonnet, GPT-4o, Gemini Flash | 80% of work: most coding, most agent subtasks, production traffic | $1-3 per 1M tokens | Where most spend should live |
| **Small/fast** | Claude Haiku, GPT-4o mini, Gemini Flash-lite | Classification, extraction, formatting, high-volume simple work | $0.01-0.20 per 1M tokens | For "is this spam," don't use flagship (10-25x overpay for zero quality gain) |

## The Effort/Thinking Lever (Separate from Model Choice)

**This is critical:** "how hard should it think" and "which model" are **two independent knobs**.

Common mistakes:
1. **Jumping to bigger model when the fix is turning effort up on the model you have**
   - More expensive, not faster, almost always wrong first move

2. **Leaving effort/thinking maxed out by default**
   - It's the single biggest lever on latency and cost for routine tasks
   - Sweep it: most workloads do fine at low/medium; save max for the 10% that's hard

3. **For agentic coding specifically,** higher effort at the *start* (better planning) often pays for itself in fewer round-trips
   - Front-load the thinking, not the correction cycles
   - Measure: 1 call at effort=max vs. 5 calls at effort=low

## Interview Pattern: Cost Modeling

```
Q: "Estimate your token cost for a document-classification pipeline
   processing 1M documents daily."

Setup:
  - Each doc ~500 tokens
  - Single classification call per doc
  - Tier selection is your job
  
Weak answer:
  "Use GPT-4 because it's the best"
  (❌ No cost reasoning, 100x overpay)

Strong answer:
  "What's the tolerance for error?
  
  If perfect accuracy matters (compliance, high-value decisions):
    → Flagship tier (Opus/GPT-4-class), ~$3/M tokens
    → 1M docs × 500 tokens × $0.003/1K = $1,500/day
  
  If 99% accuracy is fine (we catch errors downstream):
    → Mid tier (Sonnet/GPT-4o), ~$1/M tokens = $500/day
  
  If 95% accuracy is enough (rough triage):
    → Small tier (Haiku/GPT-4o mini), ~$0.03/M = $15/day
  
  Before committing, I'd:
    - Build a 100-doc eval set with human labels
    - Test each tier (flagship, mid, small)
    - Measure: accuracy vs. cost
    - Pick the smallest tier that hits your accuracy bar
  
  Example outcome: 'Mid-tier hits 98% accuracy on our eval set,
  which covers 99% of our downstream use cases. That's $500/day
  vs. $1,500/day for flagship, and downstream review catches the
  2% failures. Recommendation: start with mid, validate at scale.'"
```

## The Commodity Tier Pattern

```
Old (2022): Only frontier models could do coding
Cost: $20+/M tokens, you paid it, that was it

Today (2026): Open-weight models (DeepSeek, Qwen, Llama) are 
within 5 points of frontier on agentic coding, at 1/30th cost

This means the tier YOU use has a depreciation schedule:
  
  Task you're doing now on Opus: 
    - In 6 months, Sonnet can do it
    - In 12 months, open-weight can do it
    - In 18 months, it's commoditized at $0.0001/1M

Right-sizing isn't a one-time decision — it's a quarterly check."
```

## When to NOT Right-Size (The Trap)

Don't micro-optimize for the 90% case if you'll regret it when the 10% hard case comes:

```
Example: Classification pipeline with 100 documents
  
99 documents: clearly one category (could use Haiku)
1 document: ambiguous, edge case (needs Opus reasoning)

Option A: Route ambiguous ones to Opus
  Cost: 99×$0.001 (Haiku) + 1×$0.01 (Opus) = $0.02/doc
  Complexity: routing logic, fallback handling
  
Option B: Just use mid-tier for everything
  Cost: 100×$0.002 = $0.20/doc
  Complexity: none, works first try

When the hard case is <5% of traffic, Option A is probably not worth it.
When it's 50% of traffic, Option A is obviously right.

That judgment — "is the complexity worth it" — is what interviews test."
```

## AI Lab Interview: Model Serving at Scale

```
Q: "You're serving multiple model sizes to different customers.
   How do you choose which customer gets which model?"

Answer framework:
  "Multi-model routing needs to optimize for three things:
   
  1. Customer requirements (SLA, accuracy target)
     - High-value/regulated customers → stronger model
     - Cost-sensitive customers → smallest model that hits requirement
   
  2. Task characteristics
     - Hard reasoning → stronger
     - Extraction → cheaper tier
   
  3. Cost vs. latency SLO
     - If latency is critical, smaller+faster often beats bigger
     - If latency is loose, smaller always wins on cost
  
  Implementation:
    - Build eval set covering your customer tasks
    - For each customer, measure: min model tier that meets SLA
    - Router checks customer → selects tier
    - Track: what % of customers use each tier (cost visibility)
  
  Observation: most setups end up using mid-tier for 70%+ of traffic
  because flagship-exclusive use cases are rarer than the marketing
  makes it sound. Small-tier is rare in production because it's used
  only for trivial, low-error-tolerance tasks."
```

## Trading Firm: Latency vs. Cost

```
Q: "Your inference budget is 1ms per trade decision. Which model?"

Strong answer:
  "With 1ms budget, flagship is out — it'll queue or timeout.
  
  Decision tree:
    - Haiku inference latency: ~10-50ms (too slow)
    - Sonnet: ~30-80ms (usually too slow)
    - Speculative decoding + quantized small model: ~5-20ms (viable)
  
  Or: don't use API at all, self-host quantized model on GPU.
  
  The lesson: latency budget changes which tier is even available,
  completely independent of accuracy or capability.
  
  For trading: self-hosted quantized model is almost always the answer,
  not 'which API model.' APIs trade latency for flexibility — you've
  picked latency as the constraint."
```

## What to Measure Before Committing to a Model

| Metric | Why | Example Failure |
|---|---|---|
| **Eval score on YOUR data** (not benchmarks) | Benchmarks optimize for what's easy to measure, not what you care about. | Flagship scores 95% on MMLU; scores 50% on your domain. |
| **P99 latency, not median** | One 30ms outlier per 100 calls kills a latency SLO. | Median 5ms, P99 150ms; your 1ms SLO is broken. |
| **Cost per successful inference** | Retries, fallbacks, and errors matter. | GPT-4 costs 10x; it fails 1%, Haiku fails 3%; net cost is similar. |
| **Degraded gracefully** (second-tier fallback) | Your primary model goes down; what do you use? | Didn't test smaller model as fallback; it fails harder than primary. |

## The Meta-Skill: Right-Sizing Discipline

Candidates who get this are explicitly distinguishing themselves:
- You understand tradeoffs, not just capabilities
- You measure before deciding (eval culture)
- You're cost-aware in interviews (signals ops maturity)
- You can reason about depreciation (the commodity tier pattern)

In trading/infra/systems roles, this is the difference between someone who can ship and someone who ships well.
