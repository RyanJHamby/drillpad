# Task Specs Agents Can Finish: Acceptance Criteria, Test-First, Scope Boundaries

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Ambiguous Specs Lead to Out-of-Scope Work

You say: "Add caching to the user endpoint."

Agent might interpret this as:
1. Add Redis to the user endpoint (what you meant)
2. Add Redis + update all user endpoints (scope creep)
3. Add Redis + refactor the auth layer while we're here (even worse)
4. Add Redis to user endpoint, but then optimize the DB query too (well-intentioned, but wrong rung)

**The cost:**
- You spend 10 min writing a spec
- Agent spends 30 min exploring options
- You spend 30 min reviewing scope-creep changes
- Total: 70 minutes (+ context switches)

**With a clear spec:**
- You spend 15 min writing a spec (clear acceptance criteria)
- Agent spends 10 min implementing
- You spend 5 min reviewing (focused diff)
- Total: 30 minutes

## First Principles: Scope is a Constraint, Not a Feature

A good spec is **prescriptive about scope**, not aspirational about features.

**Bad spec:** "Improve the checkout flow."
- Does this mean: faster? Fewer clicks? Lower error rate? Better UX?
- How will you know it's done?

**Good spec:** "Make the checkout flow handle network timeouts gracefully. When POST /checkout times out, show 'Please refresh' with a retry button. Don't change the happy path. Add a test for timeout + retry."

**In the good spec:**
- Acceptance criteria (timeout handling)
- Out-of-scope (happy path unchanged)
- Test requirement (verifiable)
- Definition of done (exactly what you need)

## The Spec Template

Every spec should answer these five questions:

```
TASK: [One-sentence goal]

ACCEPTANCE CRITERIA:
  ✓ [Specific, measurable outcomes]
  ✓ [Exactly what success looks like]

OUT OF SCOPE (critical — prevents scope creep):
  ✗ [Refactoring adjacent code]
  ✗ [Performance optimizations not in the criteria]
  ✗ [Changing behavior of related features]

TEST REQUIREMENT:
  - Test: [What must be tested]
  - Test: [Edge cases]

DEFINITION OF DONE:
  - Diff is under [X] lines (forces small changes)
  - Code compiles and types check
  - New tests pass
  - Linked existing tests still pass
```

## Worked Example: The Caching Task

**Vague version (causes trouble):**
> Add caching to the user endpoint. It's slow.

**Clear version:**
```
TASK: Cache GET /users/{id} responses for 5 minutes.

ACCEPTANCE CRITERIA:
  ✓ GET /users/{id} returns cached response if cache hit
  ✓ Cache is invalidated 5 min after write
  ✓ Cache is invalidated on POST /users/{id} (user updates)
  ✓ P95 latency drops from 200ms to < 50ms for cache hits

OUT OF SCOPE:
  ✗ Caching other endpoints (they have different cache strategies)
  ✗ Refactoring the user service itself
  ✗ Changing the API contract
  ✗ Adding observability/metrics (separate task)

TEST REQUIREMENT:
  - Test: cache hits return data within 10ms
  - Test: cache expires after 5 min
  - Test: POST invalidates cache
  - Test: concurrent requests to same user don't race

DEFINITION OF DONE:
  - Diff is under 200 lines (Redis config + cache logic + tests)
  - Latency benchmark shows P95 < 50ms (cache hit case)
  - All new tests pass
  - Integration tests still pass
```

**What this prevents:**
- Agent adding Redis observability (out of scope)
- Agent refactoring the user service (out of scope)
- Agent optimizing the DB query (out of scope)
- Agent adding cache invalidation webhooks (too ambitious)

**Result:** Agent writes exactly what you need, 150 lines, done in 15 min.

## Diagram: Spec Clarity vs. Agent Scope Creep

```
Spec Clarity (left = vague, right = clear)

High scope │
creep      │  ╱─────────────────
           │ ╱     "Add caching"
           │╱                    
           │ ╲    "Add caching to
           │  ╲   /users/{id} with
           │   ╲  5-min TTL, invalidate
  Moderate│    ╲ on POST, add tests"
           │     ╲
           │      ╲_______________
  Low      │
scope      └──────────────────────
creep         Vague    Clear

Result: Clear specs = small, focused diffs = fast review = happy agent
```

## Diagram: Test-First as Acceptance Criteria

```
Traditional flow:
  Code → Test → Review → Maybe fix

Test-first flow (agents):
  Spec (with test plan)
  → Agent writes test
  → Agent writes code to pass test
  → Review (test proves correctness)
  → Merge

Why it works for agents:
  - Test is the spec (no ambiguity)
  - Agent can't cheat (code must pass test)
  - You review test first (if test is wrong, everything is wrong)
```

## Scope Boundaries: The Diff Size Forcing Function

**Rule: Prefer many small PRs over one large PR.**

- Small PR: 50 lines, 10 min review, easy to reason about
- Large PR: 500 lines, 90 min review, easy to miss issues

**For agents, use diff size as a constraint in the spec:**

```
TASK: Add JWT token validation to the auth middleware.

DEFINITION OF DONE:
  - Diff is under 100 lines total
  - New code only (no refactoring existing middleware)
  - Tests demonstrate token validation works
  - If diff > 100 lines, break into subtasks
```

**If the agent needs 300 lines, that's a signal:** The task is too big, or the spec is wrong. Better to fail fast (agent says "this needs 300 lines, can we split it?") than to create technical debt.

## Interview Q&A

**Recall 1:** What are the five questions every good spec must answer?
*Must-say:* Goal, acceptance criteria, out-of-scope, test requirement, definition of done.

**Probe 1:** You're asking an agent to "refactor the auth module for clarity." Why is this a bad spec?
*Expected:*
- "Clarity" is subjective
- Agent might refactor more than needed
- No acceptance criteria (how do you know it's done?)
- No test requirement (how do you verify clarity?)
- Better spec: "Rename auth_token to jwt_token and update all references. Add a test that the renamed variable is used correctly."

**Probe 2:** Your agent's PR is 800 lines when you expected 100. What went wrong?
*Expected:*
- Either: spec was too big (should have been split)
- Or: agent went out of scope (refactoring other things)
- Or: agent didn't understand "definition of done" constraint
- Response: review the diff, give feedback, add tighter bounds in next task

**Scenario 1:** You want to add error handling to an API endpoint. Write a clear spec.
*Expected answer (structure):*
```
TASK: Add 500 error handling to POST /orders.

ACCEPTANCE CRITERIA:
  ✓ If DB write fails, return 500 with structured error
  ✓ Error includes error ID (for support tickets)
  ✓ No sensitive info in error message

OUT OF SCOPE:
  ✗ Handling other 4xx errors (separate task)
  ✗ Adding retry logic (belongs in client)
  ✗ Refactoring error middleware

TEST REQUIREMENT:
  - Test: DB failure returns 500
  - Test: Error ID is present in response

DEFINITION OF DONE:
  - Diff under 80 lines
  - New tests pass
  - Existing tests still pass
```

**Exercise 1:** Take a recent task you gave an agent that had scope creep or was unclear. Rewrite it using the spec template. (5 min work)

---

## Checklist

- [ ] Every task has acceptance criteria (not just a goal)
- [ ] Every spec explicitly lists out-of-scope items
- [ ] Test requirements are in the spec, not left to agent discretion
- [ ] Definition of done includes diff size limits
- [ ] Used the spec template for your last 3 tasks

## Common Mistakes

1. **Writing aspirational specs instead of prescriptive ones.** "Make it faster" vs. "Add caching with 5-min TTL."
2. **Assuming agent knows what NOT to do.** Always list out-of-scope items explicitly.
3. **No test requirement.** Agent guesses what to test; you get untested code.
4. **Scope creep as a feature, not a bug.** "Agent was so helpful, it refactored the whole module!" = agent at wrong autonomy rung.
5. **Forgetting the diff size constraint.** No upper bound on lines = no enforcement of scope.

