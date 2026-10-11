# The Leverage Model: Delegation, Autonomy Ladders, and Verification as Bottleneck

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Delegation Paralysis

Before AI agents, delegation meant picking a person. The time cost was high, so you delegated only high-value, well-scoped work.

With AI agents, delegation is cheap. Now the question is: **What should agents do, and how autonomous should they be?**

Most people default to one of two extremes:
1. **Don't trust agents at all** — use them only to suggest (copy-paste every change), losing the speed benefit.
2. **Over-trust agents** — let them commit directly to main, creating production bugs and security issues.

**Neither is optimal.** The real lever is **evidence-based autonomy**: unlock each level of autonomy (suggest → edit → run → merge → deploy) only when you have evidence that the agent won't cause harm at that level.

## The Autonomy Ladder

There are five rungs. Each rung requires different evidence to unlock:

```
Level 5: DEPLOY
         └─ Agent can deploy to production
         └─ Requires: proven track record, automated rollback, monitoring

Level 4: MERGE
         └─ Agent can merge PRs without human approval
         └─ Requires: CI passes, test coverage, no regressions

Level 3: RUN
         └─ Agent can execute code locally/on CI (not just commit)
         └─ Requires: sandboxed execution, bounded cost, time limits

Level 2: EDIT
         └─ Agent can modify code (push commits, open PRs)
         └─ Requires: spec clarity, diff review, no security concerns

Level 1: SUGGEST
         └─ Agent suggests changes in conversation
         └─ Requires: human copy-paste for every change
         └─ Cost: high friction, agent slowdown wasted

(Rung 0: No agent — you write everything)
```

**The metric: time-to-verified-merge.** This is how long from "problem identified" to "fix is in main and verified good."

```
Rung 1 (suggest):   10 min (AI suggests) + 30 min (you copy-paste) + 10 min (review) = 50 min
Rung 2 (edit):      10 min (AI writes) + 5 min (review) + 5 min (merge) = 20 min
Rung 3 (run):       10 min (AI writes) + 2 min (review) + 2 min (merge) + 5 min (test) = 19 min
Rung 4 (merge):     10 min (AI writes) + 2 min (review) + 5 min (test) = 17 min
Rung 5 (deploy):    10 min (AI writes) + 2 min (review) = 12 min (+ auto-rollback on regression)

Unlocking rung 2-3: 20 min vs 50 min = 2.5x faster
Unlocking rung 4-5: 12 min vs 50 min = 4x faster
But: rung 5 requires months of evidence first
```

## Evidence-Based Unlocking

Don't unlock the next rung because you want it. Unlock it when you have evidence.

### Rung 1 → Rung 2 (Suggest → Edit)

**Evidence needed:**
- Spec clarity: you can write a task description that unambiguously specifies what to do
- Agent accuracy on your patterns: 95%+ of agent-suggested changes are correct or close-to-correct
- Scope boundaries: agent doesn't add extra changes ("scope creep fix")

**Check:**
```
Go back through 10 tasks you gave the agent.
For each: did it match the spec exactly? Did it avoid out-of-scope changes?
If yes on 9/10: unlock rung 2.
```

### Rung 2 → Rung 3 (Edit → Run)

**Evidence needed:**
- Test coverage: any agent-authored code is covered by tests
- CI gates: your CI has automated checks (tests, type checking, security scans)
- No surprises: agent-authored code doesn't bypass CI or create false positives

**Check:**
```
Next 5 tasks:
  Agent commits code.
  CI runs (tests, types, linting).
  Does CI catch all problems? Do any false positives slow you down?
If CI is reliable: unlock rung 3.
```

### Rung 3 → Rung 4 (Run → Merge)

**Evidence needed:**
- Merge fidelity: every PR with passing CI that you've reviewed was correct to merge
- No regression surprises: code that passed CI didn't create unexpected failures
- Monotonic trust increase: as you review more PRs, you're confident in the pattern

**Check:**
```
After 20 PRs reviewed:
  How many had regressions you missed?
  How many had security issues that passed CI?
  How many had scope-creep fixes?
If < 5%: unlock rung 4 (auto-merge passing CI).
```

### Rung 4 → Rung 5 (Merge → Deploy)

**Evidence needed:**
- Production safety: code that auto-merged has shipped to production
- Monitoring in place: you have rollback, metrics, and alert systems
- Track record: 3+ months of auto-merge without production incidents

**Check:**
```
Minimum: 3 months of auto-merge in main.
  No production incidents traced to agent code.
  Rollback system proven (tested, documented).
If yes: unlock rung 5 (deploy directly).
```

## Diagram: Autonomy Ladder and Trust Accumulation

```
Time-to-verified-merge vs. Evidence Accumulated

Time (min)
50 │ ┌─ Rung 1 (suggest)
   │ │  High friction, but safe
40 │ │
   │ │
30 │ │  ┌─ Rung 2 (edit)
   │ │  │  Agent commits, you review
20 │ ├──┤  ┌─ Rung 3 (run)
   │ │  │  │  CI provides gating
10 │ │  ├──┤  ┌─ Rung 4 (merge)
   │ │  │  │  │  Auto-merge passing
   │ └──┴──┴──┤  ┌─ Rung 5 (deploy)
 5 │          │  Direct to production
   │          └──── Requires 3+ mo evidence
 0 └──────────────────────────────
   0    10    20    30    40    50 (weeks of use)
```

## Diagram: Evidence Feedback Loop

```
┌─────────────────────────────────────────┐
│ Give agent task                         │
│ (spec must be clear)                    │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Agent suggests/edits (rung 1-2)          │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ YOU review change                       │
│ Questions:                              │
│  - Matches spec?                        │
│  - No scope creep?                      │
│  - Correct?                             │
└──────┬──────────────────────────────────┘
       │
       ├─ NO (spec unclear, agent erred)
       │  └─ Refine spec, give feedback
       │     (builds evidence for unlock)
       │
       └─ YES
          ├─ Merge with review (rung 2-3)
          │  └─ Wait: does CI catch it?
          │     └─ If yes consistently: advance to rung 4
          │
          └─ Later: does it break in prod?
             ├─ NO (good!)
             │  └─ Add to track record
             └─ YES (oops)
                └─ Stay at current rung
                   Investigate why check failed
```

## Worked Scenario: Premature Autonomy

**Setup:** You have a backend codebase with 50% test coverage. After 5 agent-written PRs (all reviewed by you, all correct), you unlock rung 3 (auto-run CI) and rung 4 (auto-merge).

**Week 1:** 20 agent PRs merge automatically. All good.

**Week 2:** Agent merges a PR that introduces a concurrency bug. It wasn't caught by CI because:
- No race condition tests in the suite
- The bug only manifests under load (integration test didn't trigger it)
- It shipped to production and caused a 10-minute outage

**Root cause:** You unlocked rung 4 based on insufficient evidence.
- Evidence you had: "5 PRs were correct"
- Evidence you needed: "test coverage is > 80%" and "integration tests cover async patterns"

**What to fix:**
1. Revert to rung 3 (auto-run CI, but human merge)
2. Before re-unlocking rung 4: add race condition tests
3. Re-evaluate: 20 more PRs with higher test coverage
4. Then unlock rung 4 again, with more evidence

**The lesson:** Autonomy isn't earned by PR count. It's earned by coverage and patterns. You unlocked rung 4 too early based on weak evidence (correct outputs on a few tasks), not strong evidence (comprehensive test coverage).

## Tradeoffs: When to Stay at Each Rung

| Rung | When to use | When NOT to use |
|------|-------------|-----------------|
| **Suggest** | Exploratory work, unfamiliar code, learning. New agent, unknown track record. | Routine work, high-volume tasks (too slow). |
| **Edit** | Routine changes, spec is clear, test coverage is good. Most day-to-day work. | Safety-critical code without tests. New patterns. |
| **Run** | Tasks with good CI gates and test coverage. Scaling repetitive work. | Expensive operations (GPU, production), unbounded time. |
| **Merge** | After 20+ PRs reviewed with < 5% issues. High-confidence patterns. | First month of a new project. Before monitoring is set up. |
| **Deploy** | After 3+ months evidence, proven rollback, strong monitoring. Autonomous maintenance. | New features, breaking changes. High-impact code paths. |

## Interview Q&A

**Recall 1:** Name the five rungs of the autonomy ladder.
*Must-say:* Suggest, Edit, Run, Merge, Deploy.

**Probe 1:** You unlock rung 3 (auto-run CI) for your agent. What's the maximum latency budget for a CI run before you should consider moving back down?
*Expected:*
- Depends on your tolerance for waiting (5 min? 15 min?)
- If CI takes 1 hour, you're back to 50+ minutes time-to-merge (defeating the purpose)
- Trade: faster feedback vs. cost of re-running failed CI

**Probe 2:** Your agent has been at rung 2 (edit, human merge) for 3 months. 98% of PRs are correct. Why wouldn't you unlock rung 4 (auto-merge) immediately?
*Expected:*
- High accuracy on *style* work doesn't mean high accuracy on *concurrency* or *data consistency*
- Evidence is domain-specific (correct on tests ≠ correct on migrations)
- Need to look at *what failed* in that 2%, not just fail rate

**Scenario 1:** You're building a new microservice. Should you start the agent at rung 1 or rung 2?
*Expected:*
- Rung 1 (suggest). New patterns, no track record, no established CI.
- Rung 2 (edit) is OK if: spec is exceptionally clear, you have test-first discipline
- After 10 PRs, if quality is good and CI passes: move to rung 3

**Scenario 2:** Your agent has unlocked rung 4 (auto-merge). A week later, it merges a PR that changes how errors are logged, adding 50% more log volume. Cost: $500/week extra. Why did this slip through, and what should you change?
*Expected:*
- CI gates didn't include a "cost regression" check (log volume, API calls, compute)
- Evidence you had (test passing) wasn't sufficient for behavior-changing PRs
- Solution: Add cost gates to CI before auto-merge, or demote rung 4 to rung 3 + human review for "behavioral" changes

**Exercise 1:** Map your current workflow to the autonomy ladder. Where are you today? Write the evidence you'd need to unlock the next rung. (5 min work)

---

## Checklist

- [ ] Identified your current rung (suggest/edit/run/merge/deploy)
- [ ] Clear on what metric you're optimizing (time-to-verified-merge)
- [ ] Defined evidence criteria for next rung (test coverage? spec clarity? track record?)
- [ ] Set up a feedback system (tracking failed specs, scope creep, regressions)
- [ ] Scheduled a quarterly "should we unlock the next rung?" review

## Common Mistakes

1. **Unlocking based on speed desire, not evidence.** "I want faster PRs" → unlock rung 4 → production bug. Start with evidence.
2. **Applying uniform evidence across all rung transitions.** "5 correct PRs unlocks rung 4" works for style changes, not concurrency bugs. Domain-specific evidence.
3. **Not tracking failure modes.** You review 50 PRs but don't log what was wrong with the 2 that had issues. Can't build evidence without tracking.
4. **Confusing agent accuracy with system safety.** Agent is 95% accurate, but that 5% is concurrency bugs. Not safe to auto-merge.
5. **Not documenting unlock criteria.** "We're at rung 3 now" → 6 months later, did you lock based on evidence or just drift?

