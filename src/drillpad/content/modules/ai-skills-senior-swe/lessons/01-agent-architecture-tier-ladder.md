# Agent Architecture: The Tier Ladder and When to Stop Climbing

## The Core Mistake

Most engineers building AI-assisted systems make the same error: they default to "agent" for everything. An agent is *slower*, *more expensive*, *less predictable*, and *harder to debug* than a simpler alternative. The most important skill in AI systems engineering is knowing when you've solved the problem with the simplest tier that works.

## The Tier Ladder (Know This Cold)

```
Tier 1: Single call
  Input → one LLM call → output
  Example: "Classify this email"
  Cost: O(1) call, 100% predictable
  
Tier 2: Workflow / chain
  Fixed sequence you control
  Input → call A → call B → call C → output
  Example: Extract fields → validate → format → send
  Cost: O(n) calls, sequential, deterministic
  
Tier 3: Agent
  Model decides sequence based on results
  Observe → plan → act → observe → plan → act → ...
  Example: "Fix this failing test" (model reads error, edits file, reruns)
  Cost: O(n) calls, looping, unpredictable depth
  
Tier 4: Multi-agent
  Multiple agents coordinate/delegate/supervise
  Coordinator delegates to specialists
  Cost: O(n²), latency compounds, coordination overhead
```

## Decision Tree (The Interview Pattern)

Before reaching for tier 3 or 4, ask these questions in order:

1. **Is this task genuinely open-ended?**
   - Can you know the steps in advance, or do the steps depend on intermediate results?
   - If you can list the steps now → workflow (tier 2)
   - If the steps genuinely must be discovered → agent (tier 3)

2. **Is the value of getting it right high enough to justify extra latency/cost?**
   - "This takes 3s with a workflow vs. 30s with an agent" — if that matters → workflow
   - If latency doesn't matter → agent is okay

3. **Is the model actually capable at this task type?**
   - Frontier models are genuinely good at code, planning, multi-step reasoning
   - Frontier models are weak at numerical precision, knowing when to stop, real-time judgment
   - Be honest about whether the model can actually do this

4. **Can errors be caught and recovered?**
   - Do you have tests the agent can run?
   - Do you have a way to verify correctness?
   - If not → workflow (so you can validate each step)

## Trading Firm Interview Answer

```
Q: "We have a system that needs to process trades. Should it use an agent?"

Weak answer:
  "Agents are cool, let's use one"
  (❌ Ignores actual workflow structure)

Strong answer:
  "Depends on what 'process trades' means:
  
  If it's:
   - Fixed steps (validate → check risk limits → route → confirm)
     → Workflow (tier 2). We control the sequence, latency matters,
       each step is testable independently.
   
   - Open-ended (something unusual happened, model must diagnose)
     → Possible agent (tier 3), but only if:
       • The model is actually good at trade diagnosis
       • We have a tight cost/latency budget, or 'uncertain time' is acceptable
       • We have strong verification (backtesting, paper trades)
   
  For production trade processing, 99%+ of the time workflow is right.
  The agent is slower, more expensive, and 'confident but wrong' is
  exactly the failure mode you can't afford in this domain.
  
  If there's genuinely ambiguous logic, better to:
   - Write it down (risk rules in code, not in the model's head)
   - Make the model suggest, humans approve
   - Then hardcode the logic"
```

## AI Lab Interview Answer

```
Q: "We need to fine-tune models at scale. Should we use an agentic
   loop to automate the process?"

Answer:
  "The engineering part (data pipeline, training loop, eval harness,
   plotting/analysis) is genuinely agent-friendly (tier 2 or 3, mostly mechanical).
  
  The research judgment part (which experiment to run next, why this
   result is suspicious, what to try if this doesn't work) is where an
   agent is weak. That's where the human should stay.
  
  So: agent as a 'fast mechanical executor' for the planned experiments,
   but the human owns the planning.
  
  If the human is writing every experiment manually anyway, the agent
   isn't buying you much — the bottleneck is judgment, not typing.
   If the human has a clear experimental plan, the agent removes friction
   on implementation."
```

## Common Failure: The Tier-3 Trap

You wrote a tier-2 workflow, but the model suggested "and then I should also try X," and you said "sure, let's add that," and now you have a tier-3 agent that's:
- 5x slower
- Much more expensive
- Harder to debug when it goes wrong
- Wider blast radius if it mistakes

**In review, watch for this.** When you see an agent doing something a workflow could do, push back. "Why can't we just hardcode this sequence?" is a valid question.

## The Practical Rule

```
Does the task decompose into steps you can list in advance?
  └─ YES → stop at tier 2 (workflow)
  
Does the value of getting it right justify 3-10x latency increase?
  └─ NO → stop at tier 2
  
Can you verify each agent step independently?
  └─ NO → don't use an agent for anything critical
  
THEN: maybe tier 3 is right. Even then, keep the tool surface small
and the loop tight.
```

## Interview Setup: Multi-Agent Trap

```
Q: "Design a system where agents specialize:
   - Agent A does research
   - Agent B synthesizes findings
   - Agent C writes the final report"

Trap answer:
  "Yes, multi-agent coordinator pattern, delegates to workers"

Better answer:
  "Multi-agent adds coordination overhead and latency compounds.
  
  Better: is this genuinely three independent problems, or one problem
  with three logical steps?
  
  If three steps: workflow (tier 2).
  If three independent parallel jobs: maybe agent with parallel tool calls
  (still tier 3, but at least concurrent).
  If truly three separate, autonomous agents needed to negotiate: tier 4,
  and you pay the cost.
  
  Most 'multi-agent' systems are just workflows misidentified. Fix that
  before adopting a multi-agent framework."
```

## What This Signals (For You, in Interviews)

When you pick the simplest tier that solves the problem, you're signaling:
- You understand cost/latency tradeoffs
- You can distinguish "the tool is cool" from "the tool solves this problem"
- You reason about verification and safety (simpler tier = easier to verify)
- You have production intuition (shipping is about constraints, not capability)

This is a differentiator for **systems/AI-infra/trading roles** specifically. Junior engineers are excited by agents. Senior engineers know when NOT to use them.
