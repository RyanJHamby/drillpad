# Scaling Review & Meetings Without Firefighting: Team-Scale AI Adoption

## The Structural Problem (Not Just Discipline)

Before agents: Writing was the bottleneck, review was fast.
- Slow writing → review bandwidth roughly matched output
- One person = 5 PRs/week, reviewer capacity ~5 PRs/week

After agents: Writing got fast, review capacity didn't.
- Agent-assisted dev → 20-30 PRs/week per person
- Reviewer capacity → still ~5-10 PRs/week
- **Result: Firefighting** (reviews pile up, everything becomes urgent)

**This is structural, not a discipline problem.** More reviewers doesn't fix it; a different review *structure* does.

## The Actual Lever: Tiered Review Depth

Don't review everything the same way. Allocate review effort to blast radius.

```
Tier 1: Trivial / Mechanical (5% of changes)
  Examples: formatting, dependency bump, config-only, boilerplate scaffolding
  
  Review depth: Automated checks only (lint, types, tests)
  Who: Anyone with merge rights
  Turnaround: Immediate
  
  Cost: Zero human time (pure automation)

Tier 2: Routine (70% of changes)
  Examples: standard feature work in well-tested code paths
  
  Review depth: One reviewer, normal depth, async
  Who: Whoever has context (rotated)
  Turnaround: 24 hours
  
  Cost: 30 mins per PR

Tier 3: High-Risk (20% of changes)
  Examples: auth, payment, concurrency, public API, data migrations, hot path
  
  Review depth: Two reviewers, one with domain expertise
  Who: Named owner for that risk category
  Turnaround: Before merge (not async)
  
  Cost: 1-2 hours per PR, but only 20% of PRs

Tier 4: Irreversible / Destructive (5% of changes)
  Examples: prod migrations, deletions, no rollback
  
  Review depth: Human approval gate, explicit sign-off, logged
  Who: Explicit stakeholder approval
  Turnaround: Before merge, with discussion
  
  Cost: Risk management, non-negotiable
```

**Real math:**
- 100 PRs/week agent-assisted team
- 5 Tier 1 (0 hours) + 70 Tier 2 (35 hours) + 20 Tier 3 (40 hours) + 5 Tier 4 (5 hours)
- Total: ~80 hours of review / ~4 developers = 20 hours per reviewer
- Sustainable. Without tiering: 100 PRs × 1 hour = 100 hours (not sustainable)

## Automate Everything That Isn't Human Judgment

Before a human ever looks at a diff:

```
CI Gates (must pass before PR is reviewable):
  ✓ Tests (unit + integration)
  ✓ Type checking (mypy, rustc, TSC)
  ✓ Linting (style, naming, complexity)
  ✓ Security scan (secrets, SAST, dependency audit)
  ✓ Performance regression check
  
If any of these fails, PR is not reviewable. Period.

Pre-review automated analysis:
  - Static analysis flagging correctness bugs
  - Code-review pass (automated, not human) flagging style/opportunities
  - Diff statistics (is this 50KB of boilerplate or 500 lines of logic?)
  
Human reviewer's job is now:
  "Are the flagged findings worth fixing?"
  "Does the evidence (tests, benchmarks) support this change?"
  
  Not: "Find all the problems" (automation found them)
  Not: "Is this correct" (tests verify it)
```

## Handling Agent-Specific Review Issues

Agent-generated code often has specific patterns that need checking:

```
Red flags to watch:
  - Is this a tier-2 change disguised as tier-1? (scope creep)
    Example: agent fixed the immediate problem but also refactored
             related code (blast radius went up)
  
  - Does this change trust assumptions?
    Example: agent added dependency, changed error handling, modified
             the safe/unsafe boundary
  
  - Is the explanation/comment truthful or confident-but-wrong?
    Example: agent wrote safety comment that doesn't establish safety
  
Tool-specific checks:
  - Did the agent stay in scope? (check diff vs. original request)
  - Did the agent introduce unnecessary complexity?
  - Are there commented-out alternatives the agent tried?

Pattern: agents often explore more than human-written code.
Some of that is good (thoroughness), some is noise (half-finished ideas).
Review should distinguish.
```

## The Meeting Bottleneck (Coordination Overhead)

Before agents: slow build → implicit coordination (people notice misalignment during long development)

After agents: fast build → explicit coordination (misalignment happens before you notice it, requires meetings to resolve)

```
Solution: Default to async, reserve meetings for genuine sync problems

Bad: "Let's sync on this"
  (Meeting scheduled, 30 min, 5 people, 2.5 hours total time, to answer
   a question that could be written down in 5 minutes)

Good: Async decision records
  Format:
    Decision: We're switching from Postgres to DuckDB for analytics
    Options considered:
      1. Postgres (current): [pros/cons]
      2. DuckDB: [pros/cons]
      3. Clickhouse: [pros/cons]
    Rationale: DuckDB [reasons]
    Timeline: [when]
    Reviewers: [who can object, by when]
  
  Approval: Silent consensus (no objections by Friday → approved)
  
  Cost: 15 minutes to write, 5 minutes to read, async approval
  vs. 1-hour meeting for same decision

Meetings are for:
  - Real disagreement that needs live negotiation
  - Relationship building (mentoring, team cohesion)
  - High-stakes decisions where read-backs won't suffice
```

## Metrics That Show You're Scaling Right

| Metric | Red Flag | Good | 
|---|---|---|
| **Review queue depth** | >20 PRs pending | <5 PRs |
| **Review turnaround time** | >48h for tier-2 | <24h |
| **Approval rate** | Rubber-stamping >90% of PRs | ~20% questioned/reworked |
| **Rework rate after merge** | >5% of merged PRs get hotfixed | <2% |
| **Meeting time per week** | >30% of calendar | <15% |
| **Firefighting incidents** | Frequent "urgent reviews" | Rare |

## Interview Pattern: Scaling Team AI Adoption

```
Q: "Your team of 4 engineers just started using agents.
   Suddenly you have 10x more PRs. Your review process is breaking.
   What do you do?"

Weak answer:
  "Hire more reviewers"
  (❌ Doesn't solve the structural problem, just delays it)

Strong answer:
  "This is a structural problem, not a capacity problem.
  
  1. First: Tier the review depth
     - Trivial (5%) → automation only, no human review
     - Routine (70%) → one reviewer, async, 24h
     - High-risk (20%) → two reviewers, blocking
     - Irreversible (5%) → human gate
     
     This drops review load from 100 hours/week to ~80 hours (for 100 PRs).
  
  2. Second: Automate pre-review
     - Tests must pass before human sees it
     - Linting must pass
     - Security scan must pass
     - Code-review bot flags commonalities
     
     Human's job is now 'approve or rework findings' not 'find all bugs'
  
  3. Third: Agent-specific checks
     - Did the agent stay in scope?
     - Did it introduce unnecessary complexity?
     - Are safety comments actually true?
     
     These are tier-3 checks (high-risk code), not routine review.
  
  4. Fourth: Async decision records
     - Replace 1-hour meetings with 15-minute written decisions
     - Approval via silent consensus
     - Frees up 5-10 hours/week per person
  
  Expected result:
    - Review scales with output (was bottleneck, now not)
    - Meeting load drops (was growing, now shrinks)
    - Quality stays the same (automation + targeted human review)
    - Firefighting stops (reviews aren't backed up)
  
  If we hired 2 more reviewers, we'd fix the backlog temporarily.
  By month 2, agent output scales again, we're back to firefighting.
  
  The right answer is to change the process, not add bodies."

Why this signals good judgment:
  - You identified the structural issue (not lack of reviewers)
  - You have a concrete solution (tiered review)
  - You thought about automation as a lever
  - You understood the meeting overhead
  - You measured success (metrics that show sustainability)
```

## What This Signals

- You've scaled teams under velocity pressure
- You understand bottlenecks are often process, not capacity
- You think about leverage (automation multiplies human effort)
- You're pragmatic about coordination (async > meetings)
- You see agent adoption as a team-scaling problem, not a tool problem

This is increasingly valuable: companies that adopt agents at scale without rethinking processes burn out their teams. Being the person who says "we need to change how we review, not hire more reviewers" is essential infrastructure thinking.
