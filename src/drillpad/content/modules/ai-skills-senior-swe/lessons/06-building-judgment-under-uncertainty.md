# Building Judgment: Pattern Recognition and Decision-Making Under Uncertainty

## The Core Claim

Technical execution (writing code, choosing models, writing specs) is becoming commoditized. The durable skill is **judgment under uncertainty** — knowing when to trust an agent, when to slow down, which tradeoff is actually real, and when a plausible-sounding answer is subtly wrong.

## Why Judgment Matters in AI

Agents are really good at:
- Generating code that compiles
- Writing plausible-sounding explanations
- Completing obvious next steps

Agents are weak at:
- Knowing when something is subtly wrong (not obviously broken, but wrong)
- Recognizing when a pattern doesn't apply
- Knowing what CAN'T happen (negation)
- Catching domain-specific failure modes

**Judgment is your ability to distinguish "looks good" from "actually good."**

## Pattern 1: Fluent But Wrong

```
Example: Agent-generated trading code
  
Code:
  fn calculate_pnl(fills: Vec<Fill>) -> Result<f64> {
    let mut pnl = 0.0;
    for fill in fills {
      pnl += fill.price * fill.qty as f64;
    }
    Ok(pnl)
  }

What it looks like: clean, simple, obvious
What's actually wrong:
  1. No accounting for direction (long vs short)
  2. No accounting for commission
  3. Floating-point rounding errors on large volumes
  4. No type system preventing negative quantity
  
All of this is subtly wrong in a way that:
  - Will compile
  - Might pass unit tests (depends on test data)
  - Will fail silently on real data

This is the dangerous failure mode: code that's fluent enough to pass
review by someone not thinking hard, wrong enough to cost money."
```

## How to Build the Judgment to Catch This

```
Mechanism: Predict → Compare → Revise

Step 1: BEFORE seeing code, predict
  "What traps do I expect in PnL calculation?"
  - Direction handling (long/short sign)
  - Commission/fees
  - Rounding on large numbers
  - Currency/decimal precision
  
Step 2: See code, compare
  Does the code address each trap?
  What's the first thing I'd break-test on?

Step 3: Revise
  If I was right about a trap, note why (remember it)
  If I was wrong, update my model of what usually goes wrong
  
This predict-compare-revise loop is the only mechanism that actually
calibrates judgment. Without it, code review is just surface reading."
```

## Pattern 2: Domain-Specific Blindness

```
Example: Latency-critical system, agent adds logging

Code:
  if DEBUG {
    println!("Processing order {}", order_id);  // Harmless, right?
  }

Context: Order processing latency budget is 100μs
Debug is OFF in release build, so this doesn't run
Seems fine.

Actually wrong:
  - Even "off" log statements in Rust lock a mutex on stderr
  - Mutex contention destroys predictable latency (p99 spike)
  - In a latency-critical system, this is a design mistake
  
An agent that doesn't know "logging in latency-critical paths is
risky" will happily add it. You need to know this pattern."
```

## Building Your Own Pattern Library

```
Keep a private list of "things I've caught":

Trading systems:
  - PnL calculations without explicit direction
  - Race conditions in order acknowledgment
  - Stale quotes used in execution decisions
  - Rounding errors on large notionals

Distributed systems:
  - Retry without idempotence check
  - Timeout longer than needed (cascades failures)
  - Lock ordering assumptions that aren't documented
  - Partition assumptions (assumes perfect quorum voting)

Infrastructure:
  - Resource leaks in error paths
  - Concurrent access without bounds (unbounded queues)
  - Silent truncation (int overflow, buffer overrun)
  - State leaving traces observable by tenant B

This list is your actual expertise. It's what makes a junior engineer
and a senior engineer different: the senior knows which 20 patterns
account for 80% of real bugs in their domain."
```

## Interview Pattern: Judgment Signaling

```
Q: "Here's an agent-generated implementation of rate limiting.
   What's your gut reaction?"

Code: (fictional example)
  pub fn should_allow_request(client_id: &str) -> bool {
    let quota = get_quota(client_id);
    let used = get_usage(client_id);
    used + 1 <= quota
  }

Strong answer (signals judgment):
  "First gut: is this a TOCTOU race? Yes, almost certainly.
  get_quota and get_usage are separate calls. By the time we check,
  another concurrent request could have consumed the quota.
  
  In a real rate-limiting system, this silently allows double-usage:
  Request A sees 1 left, check passes
  Request B sees 1 left, check passes
  Both requests go through
  Now 2 used, 1 allowed
  
  The spec should be: 'Return true if you *atomically* increment usage
  while staying under quota.' That's different code entirely (probably
  a compare-and-swap on an atomic counter).
  
  I'd ask the agent: does your implementation have this race?"

Why this signals judgment:
  - You spotted a non-obvious pattern (TOCTOU)
  - You traced through the actual failure scenario (two requests)
  - You connected it to spec requirements (atomicity)
  - You didn't just say 'looks okay to me'"
```

## Pattern 3: Knowing When NOT to Use an Agent

```
Situations where judgment says "no agent":

1. The task is mostly judgment, not execution
   "Decide which customer gets priority in overload"
   → Agent shouldn't decide, should suggest
   → Human reviews, calls the shots

2. The result costs money if wrong
   "Wire the payment" → human approval gate, every time
   
3. The task requires domain knowledge the model doesn't have
   "Interpret these obscure error codes in our codebase"
   → More likely you need to add the context or codify the knowledge
   → Agent with perfect context sometimes works; agent guessing doesn't

4. The cost of being wrong exceeds the cost of human time
   "Optimize this query" (risky) vs. "Write the boilerplate" (safe)
   → Different answers for the same "code writing" task
```

## The Durable Skills (Things That Don't Commoditize)

As models improve and agents get better, what skills stay valuable?

```
Commoditizing (will be automated):
  - Prompt engineering ("ask nicely," exact phrasing)
  - Choosing which model (auto-routing will handle this)
  - Writing boilerplate (agents are now fast enough)

Durable (stays valuable):
  - Knowing what GOOD LOOKS LIKE in your domain
  - Recognizing when a plausible answer is subtly wrong
  - Reading an agent's code and catching what it missed
  - Designing systems that are hard to get wrong (via types, specs)
  - Judgment under incomplete information
  
The throughline: anything that relies on taste, domain intuition, or
catching subtle mistakes stays valuable. Anything mechanical gets
automated."
```

## Meta-Skill: Calibrating Confidence

```
You read code. You either think:
  A) "This looks right" (high confidence)
  B) "This looks right, but..." (medium confidence, uncertain)
  C) "This looks wrong for reason X" (high confidence, negative)

The person with good judgment is calibrated:
  - When they say "looks right," it usually is
  - When they say "uncertain," they're honest about doubt
  - When they say "wrong," they can explain why

The person with bad judgment:
  - Trusts their gut always (overconfident)
  - Approves quickly without engaging deeply
  - Can't explain why something is wrong (just a feeling)

To build calibration: keep a record of your predictions vs. outcomes.
"I said this was a race condition, was I right? I said this was fine,
were there bugs?" Your accuracy over 50-100 cases is your actual
judgment level, not your confidence."
```

## Stub Content

- **Reading unfamiliar code quickly** — pattern matching over line-by-line reading
- **The predict-compare-revise loop** — deliberate practice for judgment
- **Postmortem analysis** — learning from others' bugs to build intuition
- **Fast feedback loops** — domains where you find out quickly if you're right
- **Calibration exercises** — keeping your judgment honest

The theme: **Judgment is built by comparing your predictions to outcomes, repeatedly, in domains where you care about being right.**
