# Design Communication: Self-Scoring During Interview

## The Question You Can't Ask Out Loud

```
"Am I doing well? Should I slow down? Are they convinced?"

You can't ask this directly, but you can read signals.
```

## Signal 1: Interviewer Engagement

**High engagement (doing well):**
- Asks clarifying questions
- Nods, takes notes
- Follows up on details

**Low engagement (not convinced):**
- Quiet, no feedback
- Checks watch
- Tries to move on quickly

**Response:**
- High engagement: Keep going, go deeper
- Low engagement: Simplify, ask if they want more detail

## Signal 2: Question Type

**Gotcha questions (you missed something):**
- "What if the database is down?"
- "How do you handle failures?"
- Pattern: "But what about X?"

**Response:** You were underprepared. Add more failure cases.

**Clarifying questions (testing depth):**
- "Why did you choose cache over database?"
- "How would you measure latency?"
- Pattern: "Why/how" (deeper thinking)

**Response:** You're on the right track. Lean into the reasoning.

**Scope expansion questions (they believe you):**
- "Now scale to 10x"
- "Add multi-region support"
- Pattern: "Now assume..." or "Scale to..."

**Response:** They're convinced on basics. They want to see if you can scale thinking.

## Self-Scoring Rubric

```
Strong answer (80+ points):
- ✅ Draws clear architecture
- ✅ Identifies bottlenecks
- ✅ Handles failures proactively
- ✅ Shows tradeoffs
- Interviewer asks scope expansions

Medium answer (60-80 points):
- ✅ Has architecture, not detailed
- ⚠️ Misses some failure modes
- ⚠️ Tradeoffs mentioned but shallow
- Interviewer asks clarifying questions

Weak answer (< 60 points):
- ❌ Architecture vague or wrong
- ❌ No failure handling
- ❌ Oversimplifications
- Interviewer tries to help with hints
```

## Real-Time Adjustments

```
Interviewer is quiet after your design:

Bad interpretation: (silence = good)
  → Continue talking more
  → Actually digging hole deeper

Better interpretation:
  → "I described [X]. Does that make sense? 
     Want me to go deeper, or move to next component?"
  → Gives them control back
  
Response signals what they want:
  - "Go deeper" → They want to see depth
  - "Move on" → They're satisfied, confident in you
```

## When to Go Deeper vs. Move On

**Go deeper if:**
- Interviewer asking "why" questions
- Interviewer taking lots of notes
- Question targets your strength

**Move on if:**
- Interviewer asking "what if" (gotchas)
- You've spent 5+ minutes on one component
- Interviewer says "okay, what about X?" (bored)

## Time Management

```
45-minute interview:

0-5 min: Understand requirements
5-20 min: Describe design (15 min)
20-40 min: Deep dive on 1-2 components (20 min)
40-45 min: Wrap up, any questions? (5 min)

If interviewer is bored at 15 min:
  - You went too deep into one component
  - Move on faster next time

If interviewer keeps drilling at 30 min:
  - You're in their area of focus
  - Good sign, keep going

If you finish at 35 min:
  - Either very concise (good)
  - Or skipped hard parts (bad)
  - Ask: "Want to go deeper on anything?"
```

## Confidence Signals

**Sound confident, not arrogant:**

```
Bad: "This system is perfect"
  (❌ No design is perfect)

Good: "This is my approach. The tradeoff is [X].
      If requirements change, we'd adjust to [Y]."
  (✅ Confident but flexible)
```

## Quick Checklist

**Mid-interview, ask yourself:**

- [ ] Did I identify the bottleneck?
- [ ] Did I handle obvious failures?
- [ ] Can I explain the tradeoffs?
- [ ] Is interviewer nodding or quiet?
- [ ] Did I go too deep on one part?
- [ ] Am I out of time?

