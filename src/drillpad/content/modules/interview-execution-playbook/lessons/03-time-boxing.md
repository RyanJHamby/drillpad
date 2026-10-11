# Time Boxing: 45-Minute Breakdown

## The Breakdown

```
0-5 min: Requirements & Scope
  - Ask clarifying questions
  - Nail down scale, constraints
  - Agree on what "done" looks like
  
5-15 min: Architecture Sketch
  - Draw boxes (components)
  - Draw arrows (data flow)
  - Name the bottleneck
  
15-35 min: Deep Dive on Bottleneck
  - Zoom into hardest part
  - Show tradeoff reasoning
  - Handle follow-ups
  
35-45 min: Wrap & Questions
  - Summarize design
  - Ask interviewer smart questions
  - Show you care about their feedback
```

## Time Pressure: When to Stop Going Deep

```
Minute 20: You're 5 min into deep dive
Interviewer asks: "How does replication work?"

Bad: Spend 10 minutes explaining Raft
  - You go too deep
  - Leave no time for other components
  - Interviewer thinks you can't prioritize
  
Good: Spend 2 minutes, signal depth
  "Replication uses Raft: leader election, quorum voting.
   I can go deep if needed, but want to check other components first.
   What's most important to you?"
  
Result: Interviewer respects time awareness
```

## What to Code vs What to Sketch

```
Do code (write actual code):
  - Data structure (if critical, e.g., LRU cache)
  - Algorithm (if complex, e.g., consistent hashing)
  - Complex state machine (if ambiguous)
  
Do sketch (pseudocode or boxes):
  - Distributed system components
  - API endpoints
  - Database schema
  - Flow diagrams

Rule of thumb:
  - If you can explain in 1 min: sketch
  - If it needs 5 min to understand: code it
```

## Pacing Red Flags

```
Red flag: You're at minute 20 and still on "requirements"
  - You're overthinking
  - Interviewer is bored
  - Fix: Move to architecture sketch NOW

Red flag: You're at minute 30 and haven't mentioned tradeoffs
  - You're just describing, not reasoning
  - Fix: Point out "This trades latency for consistency"

Red flag: You're at minute 35 and still designing
  - You'll have no time to wrap
  - Fix: Cut complexity, summarize what you have

Red flag: You finish at minute 15
  - You either oversimplified or went too fast
  - Fix: Interviewer will ask follow-ups (expected)
```

## Recovery If You're Behind

```
Minute 25: You're running 10 minutes behind

Option 1 (worse): Panic, talk faster
  - Come across as flustered
  
Option 2 (better): Acknowledge and pivot
  "I'm running behind schedule.
   Let me cut to the bottleneck:
   The hard part is X, I'd solve with Y.
   Want me to detail the implementation?"
  
Result: Shows maturity, saves face
```

## The Ideal Arc

```
Minutes 0-5: "Let me understand the problem"
  → Interviewer: "Good questions"
  
Minutes 5-15: "Here's my architecture"
  → Interviewer: Nods, makes notes
  
Minutes 15-35: "The hard part is this, I solve with..."
  → Interviewer: "But what if..." (follow-ups)
  → You: Adapt design, explain tradeoff
  
Minutes 35-45: "So to summarize... Any feedback?"
  → Interviewer: "Great design, a few notes"
```

