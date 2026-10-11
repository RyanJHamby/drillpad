# Design Communication: Red Flags & Smell Tests

## Design Red Flags (What Interviewers Worry About)

### Red Flag 1: Single Point of Failure

```
Your design:
  Client → Load Balancer → Replica Group → Database

Question: "What if load balancer dies?"

Red flag answer:
  "Uh, we'd need another load balancer"
  (❌ You just described a second point of failure)

Better:
  "Load balancers are stateless, clients retry. 
   Second LB takes over. Or use failover DNS."
  (✅ You prevent the single point of failure)

Interviewer thinks: Does this person understand availability?
```

### Red Flag 2: Unbounded Growth

```
Your design:
  Client → Queue → Workers

Question: "What if 1M requests arrive at once?"

Red flag answer:
  "The queue will hold them all"
  (❌ Queue grows to infinity, OOM crash)

Better:
  "Queue has max size 10k. Beyond that, return 429.
   Clients retry with backoff."
  (✅ You prevent cascading failure)

Interviewer thinks: Does this person think about limits?
```

### Red Flag 3: No Consistency Mechanism

```
Your design:
  Write → Replica A, Replica B (fire and forget)

Question: "Replicas diverge, what's truth?"

Red flag answer:
  "Uh, we pick the one with more data?"
  (❌ No tie-breaker, inconsistency possible)

Better:
  "Master tracks version, replicas check version.
   If divergence, replicas catch up."
  (✅ You have a mechanism to recover)

Interviewer thinks: Does this person understand consistency?
```

### Red Flag 4: No Monitoring

```
Your design:
  (Describe system with no mention of how you know it's working)

Question: "How do you know if this is slow?"

Red flag answer:
  "Users complain?"
  (❌ Reactionary, not proactive)

Better:
  "P99 latency alert at 100ms. 
   Queue depth alert at 1000. 
   Error rate alert at 1%."
  (✅ You prevent problems before users notice)

Interviewer thinks: Does this person think operationally?
```

### Red Flag 5: Oversimplification

```
Your design:
  "Use cache for everything"

Question: "Cache hit rate for new items?"

Red flag answer:
  "Uh, cache will be warm quickly?"
  (❌ Cache thrash on new items, actually hurts)

Better:
  "New items miss cache initially. 
   For trending items, pre-warm cache.
   For tail items, fetch from DB."
  (✅ You understand real behavior)

Interviewer thinks: Does this person know limits of their tools?
```

## Smell Test Checklist

**Before you present design, ask yourself:**

```
Single Point of Failure?
- [ ] Can any one component fail and take down system?
- [ ] If yes: How do you prevent it? (replication, failover)

Unbounded Growth?
- [ ] Can any queue grow to infinity?
- [ ] Can memory grow without limit?
- [ ] If yes: How do you bound it? (max size, backpressure)

Consistency?
- [ ] If replicas diverge, what's truth?
- [ ] How do you recover from divergence?
- [ ] If not sure: Say "strong consistency on this path"

Monitoring?
- [ ] Can you detect if it's slow? (metrics, alerts)
- [ ] Can you detect if it's broken? (health checks)
- [ ] If no: Add it to design

Simplification?
- [ ] Did I oversimplify? (cache hits always? load balanced fairly?)
- [ ] Did I reason about edge cases? (cache cold start, hash collisions)
- [ ] If not: Mention edge cases in design
```

## How to Catch Your Own Red Flags

**During design explanation:**

```
As you talk, listen for these phrases:
  - "We'll assume..." (assumptions need validation)
  - "Eventually, it will..." (eventual consistency = risk)
  - "Probably won't happen..." (but what if it does?)
  - "The system will handle it" (how? specifically?)

If you catch yourself, PAUSE and address it:
  "I was assuming cache hits 95%, but let me think about cold start...
   New items will miss cache, so we need a secondary strategy."
  (✅ Self-correction shows maturity)
```

## Interview Red Flags vs Green Flags

🚩 **Red flag phrases:**
- "We'll worry about that later"
- "Probably won't be a bottleneck"
- "The database will just scale"
- "Consistency isn't important"

✅ **Green flag phrases:**
- "This could fail, so we..."
- "The bottleneck is probably X, let me verify..."
- "If replicas diverge, we..."
- "We measure this with alerts on..."

