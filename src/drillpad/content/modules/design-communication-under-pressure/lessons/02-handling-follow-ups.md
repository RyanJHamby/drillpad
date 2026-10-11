# Design Communication: Handling "But What If X Fails?" Follow-Ups

## The Pattern

```
Interviewer: "Design payment system for 1M transactions/day"
You: (explain design for 5 min)
Interviewer: "But what if the payment processor is down?"
(You weren't expecting this specific follow-up)
```

**Two types of follow-ups:**
1. **Gotchas** (you missed something)
2. **Probes** (testing if you've thought about it)

Both require different strategies.

## Strategy 1: Anticipate the Obvious Failures

**Before you present, pre-answer the top 3 failure modes:**

```
Your design:
  Client → Payment API → Card Processor → DB

Obvious failures:
  1. Card Processor down? (most likely)
  2. Database down? (second most likely)
  3. Payment API down? (your own service)

Pre-answer them:
  "For Card Processor down: Circuit breaker, queue for retry.
   For DB down: Failover replica, write ahead log.
   For API down: Horizontal scaling, health checks."
   
Interviewer asks: "What if Card Processor is down?"
You respond: (already have answer ready)
Interviewer thinks: (This person thought ahead)
```

## Strategy 2: The "Yes, And..." Technique

```
Interviewer: "But what if payment processor is slow?"

Weak response:
  "Uh, I didn't think about that. Let me think..."
  (Fumbling, unprepared)

Better response:
  "Good point. Yes, and we'd handle it with:
   1. Timeout after 5s (don't wait forever)
   2. Circuit breaker (stop hammering slow service)
   3. Retry queue (process later when service recovers)
   
   Would you prefer I add anything else?"
  (✅ You acknowledge, offer solution, invite feedback)
```

## Strategy 3: When You Don't Know

```
Interviewer: "What about network latency between regions?"

If you haven't thought about it:
  Bad: "I... uh... maybe we cache?"
  
Better:
  "That's a great question. Network latency between US and EU
   is ~150ms. In my design:
   
   1. I assumed each region independent (users in US → US servers)
   2. But cross-region replication needs consideration
   
   What I'm unsure about: Should we use strong consistency
   (slower, safer) or eventual consistency (faster, risky)?
   What's your recommendation?"
  
Interviewer thinks: (Honest about gaps, asks good questions)
```

## Strategy 4: The Clarifying Question

```
Interviewer: "What if you get DDoS attack?"

Instead of: "Uh, we'd block the IP..."
Better: "Good question. Let me clarify requirements:
  - Are we defending against volumetric DDoS (flood)?
  - Application-layer DDoS (slow-loris)?
  - Or both?
  
  My approach varies by type..."
  (✅ You show depth by asking clarifying questions)
```

## Common Follow-Ups & Preemptive Answers

```
Q: "What if database is down?"
A: "Failover to replica. If both down, graceful degradation—
   return stale cache while replicas restart."

Q: "What about network latency?"
A: "Depends on scale. Single DC? Acceptable. Multi-region?
   Need eventual consistency for cross-region replication."

Q: "What if hacker breaks in?"
A: "Outside scope of this design. Assume servers trusted.
   But if important: encryption in transit, secrets in vault, RBAC."

Q: "How do you scale to 10x?"
A: "Current bottleneck is database. Scale by:
   1. Sharding (hash by user_id) — 2 days
   2. Or read replicas — 1 day
   Which matters more: latency or cost?"
```

## Red Flags When Handling Follow-Ups

🚩 **Don't:**
- Ignore the question ("That's not important")
- Get defensive ("My design is fine")
- Go silent (pause too long without thinking out loud)

✅ **Do:**
- Acknowledge ("Good catch")
- Integrate it ("Let me add that")
- Ask for guidance ("What matters more for your use case?")

