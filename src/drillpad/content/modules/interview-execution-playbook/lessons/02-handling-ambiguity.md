# Handling Ambiguity: Clarifying Questions, Assumptions, Constraint Evolution

## The Problem: Ambiguous Requirements

```
Interviewer: "Design a cache system"

Ambiguous:
  - Cache for what? (hot data, recently accessed, trending)
  - How big? (1GB, 1TB, 100TB)
  - How many requests? (1k QPS, 1M QPS)
  - What's the cost of miss? (1ms extra latency, user-facing failure)
  - Consistency requirement? (stale OK, or strong)
```

**Good candidates ask. Bad candidates guess.**

## The Right Questions to Ask

### Question 1: Scale (Give Me Numbers)

```
Bad question: "How many users?"
Good question: "How many requests per second? What's the P99 latency?"

Bad question: "How much data?"
Good question: "How many items in cache? Average item size?"

Why? Numbers constrain design.
```

### Question 2: Constraints (What Can't Change)

```
Bad question: "Is consistency important?"
Good question: "If stale data causes 0.1% errors, is that acceptable?"

Bad question: "How much latency?"
Good question: "Is 100ms P99 acceptable, or must it be <50ms?"

Why? Tradeoffs require concrete thresholds.
```

### Question 3: Boundary Conditions (Edge Cases)

```
Bad question: "What if cache is full?"
Good question: "How do we handle new items when cache is at capacity? Evict old, or wait?"

Bad question: "What if a node fails?"
Good question: "If a cache node dies, do we lose data (acceptable), or must we replicate?"

Why? Reveals what actually matters.
```

## Making Assumptions Explicit

**Good pattern:**

```
"Based on what you said:
  - 1M QPS means I need horizontal scaling
  - P99 < 100ms means I need sub-10ms lookups
  - Stale data OK means I can use TTL instead of write-through
  
Am I understanding correctly?"
```

**Why this works:**
- Interviewer confirms or corrects before you go wrong direction
- Shows you're thinking carefully
- Catches misunderstandings early

## Evolving Design as Constraints Change

```
Initial design (based on 1M QPS):
  - Single cache server (1TB memory)
  - TTL-based invalidation (5 min)
  
Interviewer: "Now make it 10M QPS"

Evolution:
  - (Your initial design breaks)
  - "At 10M QPS, single server is bottleneck
  - New design: partition by key (10 cache servers)
  - Trade-off: network latency (local server now 1ms slower)
  - Still acceptable if P99 was 100ms"
```

**Good response to constraint change:**
```
"Original constraint was P99 < 100ms.
New scale breaks single server.

Options:
  1. Partition (add complexity, still <100ms)
  2. Accept degradation to 150ms (simpler, might be OK)
  3. Use CDN (geo-distributed, but more complex)

I'd choose #1 (partition) to stay under SLA.
Here's how rebalancing works..."
```

**Bad response:**
```
"Oh, I'll just add more servers"
(Doesn't address that single server is now bottleneck)
```

## Interview Pattern: The Question That Saves 20 Minutes

```
Q: "Design YouTube"

Bad: Start designing immediately (guess wrong)
Good: Ask first
  "YouTube is huge. Let me scope:
   - Are we designing for creators (upload) or viewers (playback)?
   - One region or multi-region?
   - P99 latency target?
   - Consistency requirement?
   
  Based on answers, I'll focus on the bottleneck"

Result: Efficient design, no wasted time on wrong problem
```

## The Assumption Checklist

Before you start designing, verify:

- [ ] Scale (QPS, data size, latency target)
- [ ] Consistency (strong? eventual? eventual with bounds?)
- [ ] Availability (is downtime acceptable?)
- [ ] Cost (optimize for speed, cost, or balance?)
- [ ] Failure modes (what's acceptable to lose?)
- [ ] Time horizon (design for now or 5x growth?)

**Interview signal:**
- Asking good questions → 80 points (shows thinking)
- Guessing → 60 points (might be right, might be wrong)

