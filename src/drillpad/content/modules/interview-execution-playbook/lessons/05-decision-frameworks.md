# Decision Frameworks: Reasoning Under Incomplete Information

## The Problem: You Don't Know Everything

```
Interviewer: "Design a notification system"

You don't know:
  - How many notifications per second?
  - What's the latency SLA?
  - Must notifications be delivered in order?
  - Can we lose a notification (0.01% is OK)?
  - How many users?
```

**Most candidates guess. Good candidates reason.**

## Framework: Default Assumptions

```
"Given nothing else, I assume:
  - Consistency over availability (unless told otherwise)
  - Strong latency requirements (unless told acceptable to be slow)
  - High scale (unless told it's small)
  - Failures happen (design for resilience)
  - Measurements matter (propose metrics)"
```

**Why this works:**
- Prevents you from oversimplifying
- Shows you think about worst case
- Interview will correct if you're wrong

## Framework: Constraint Propagation

```
Given one constraint, derive others

"1M QPS" → implies:
  - Need multiple servers (1 server ≈ 10k-100k QPS)
  - Data must be sharded
  - Failures will happen (at 1M QPS, hardware fails regularly)
  - Monitoring critical (can't debug 1M requests manually)

"P99 < 100ms" → implies:
  - Can't do synchronous I/O (DB lookup is 10ms)
  - Must cache or batch
  - Must avoid cascading timeouts
```

## Framework: Tradeoff Ranking When Unsure

```
You don't know the priority order

Step 1: Rank common priorities
  1. Consistency (usually most important)
  2. Latency (almost always matters)
  3. Cost (important but less urgent)
  4. Complexity (easier to add than remove)

Step 2: Ask to confirm
  "I'm assuming consistency > latency > cost.
   Are you testing that order?"
   
  Interviewer: "Actually, cost is critical here"
  You: "OK, changes things. I'd optimize for cost first..."
```

## Framework: "Good Enough" Design

```
When uncertain, build simplest solution first

Approach:
  1. "Single server solution for scale we have now"
  2. "Sharding strategy if we grow 10x"
  3. "Replication if we need multi-region"
  
Benefit:
  - Shows you understand layered scaling
  - Avoid over-engineering
  - Easier to evolve than change core architecture
```

## Framework: Error Budgets

```
"If we get this wrong, what's the cost?"

Cost map:
  Consistency error → $$$$$$ (user loses money)
  Latency error → $$$ (user annoyed)
  Availability error → $$ (users can try later)
  Cost error → $ (we overpaid)

Allocate design effort proportional to cost
```

## Interview Pattern

```
Q: "Design API rate limiter"

With framework:
  "Given no specific numbers, I assume:
   - 1M API calls per day (100 per second)
   - Must protect against abuse
   - False positives acceptable (block 0.1% legitimate)
   
   Tradeoff: accuracy vs simplicity
   I'd start with token bucket (simple),
   add machine learning if false positives too high.
   
   Would you confirm these assumptions?"
   
Result: Interviewer respects your reasoning
```

