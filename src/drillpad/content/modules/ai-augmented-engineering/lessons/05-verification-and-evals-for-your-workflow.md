# Verification & Evals for Your Workflow: Tests, Types, CI, Review Tiers

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Trusting Without Verifying

You review an agent PR. It looks good. You merge it. A week later, a user reports a bug that the code didn't handle.

**What went wrong?**
- Code looked fine (syntax is correct)
- Tests passed (but didn't cover the edge case)
- You didn't notice the missing edge case in review

**Root cause:** You trusted the code's *appearance*, not the evidence.

**The lever:** Verification is not about reviewing code carefully. It's about building systems that catch problems automatically, before they reach production.

## Verification Hierarchy: What You Can Trust at Each Level

```
Level 0: Code appearance (UNRELIABLE)
  Looks good, but could be wrong
  Example: function name is clear, but logic is inverted

Level 1: Syntax (RELIABLE but limited)
  Code compiles/runs without errors
  Catches: typos, import errors, undefined variables
  Doesn't catch: logic errors, edge cases, performance issues

Level 2: Types (RELIABLE for whole-class bugs)
  Static type checking (mypy, TypeScript, Rust)
  Catches: wrong types passed to functions, API contract violations
  Doesn't catch: logic errors within correct types, edge cases

Level 3: Lint (RELIABLE for style, some correctness)
  Style enforcement, naming conventions, complexity checks
  Catches: unused variables, too-long functions, anti-patterns
  Doesn't catch: logic errors, missing edge cases

Level 4: Unit tests (RELIABLE for unit behavior)
  Tests that each function works in isolation
  Catches: function-level bugs
  Doesn't catch: integration bugs, concurrency issues, real-world scenarios

Level 5: Integration tests (RELIABLE for subsystems)
  Tests that multiple components work together
  Catches: integration bugs, data consistency issues
  Doesn't catch: performance issues, failure modes, edge cases

Level 6: End-to-end tests (RELIABLE for workflows)
  Tests complete user workflows
  Catches: missing features, wrong user experience
  Doesn't catch: performance at scale, rare edge cases, production failure modes

Level 7: Production monitoring (RELIABLE for real-world behavior)
  Metrics, logs, alerting from running production code
  Catches: performance issues, real user bugs, unexpected load
  Doesn't catch: future problems not yet encountered
```

**Key insight:** No single level catches all problems. You need multiple levels, each specializing in what it can verify.

## The CI Verifier: Automate Everything Before Code Review

Before a human ever sees a PR, automated checks should have run:

```
Agent writes code
  ↓
Agent commits to branch
  ↓
CI starts (automated):
  ✓ Tests run (unit + integration)
  ✓ Type checker runs (mypy, rustc, tsc)
  ✓ Linter runs (style, complexity, patterns)
  ✓ Security scan (secrets, SAST, dependency audit)
  ✓ Performance regression check
  ✓ Coverage check (must be > 80%)
  ↓
All pass? → PR is reviewable
Some fail? → Block review, agent gets feedback and fixes

After all pass:
  ↓
Human reviews (now focused on logic and design, not mechanics)
  ├─ Are the tests actually good?
  ├─ Does the design make sense?
  ├─ Any edge cases not covered?
  ↓
Merge (confidence backed by evidence)
```

**Cost reduction:**
- Without CI: you manually check for tests, types, formatting (15 min per PR)
- With good CI: you focus on logic only (5 min per PR)
- Savings: 10 min per PR × 100 PRs/mo = 16 hours/mo

## Personal Benchmarks: Verify Agent Quality Over Time

A **personal benchmark** is a set of 10-15 real tasks that you re-run on each new model/tool version. It's your regression detector.

**Example benchmark (Python project):**

```
Task 1: Add logging to the payment module
  Spec: [from lesson 02]
  Metric: Did agent match spec? (< 100 lines, tests pass, no scope creep)
  Expected result: ✓ (high confidence task)

Task 2: Fix a subtle off-by-one error in pagination
  Spec: [specific scenario]
  Metric: Did agent find the bug? Did it introduce new bugs?
  Expected result: ✓ (medium confidence task)

Task 3: Implement a distributed transaction with retries
  Spec: [complex scenario]
  Metric: Did agent handle all failure modes? Race conditions?
  Expected result: Sometimes (low confidence task)

Task 4: Refactor the auth module for testability
  Spec: [design task, not mechanical]
  Metric: Did agent understand the design intent? Good tradeoffs?
  Expected result: Inconsistent (agent judgment task)

... (10-15 tasks total)
```

**How to use it:**

1. **Baseline run:** Run all 15 tasks on your current agent/model. Time each, note failures.
   - Result: Agent A takes 120 min, 2 failures, output quality = 85%

2. **Later:** New model version available. Re-run the 15 tasks.
   - Result: Agent B takes 100 min, 0 failures, output quality = 92%
   - Conclusion: Agent B is better. Safe to upgrade.

3. **Or:** Different model, different performance.
   - Result: Agent C takes 90 min, 5 failures, output quality = 60%
   - Conclusion: Agent C is worse at your use case. Don't use.

**Why this matters:**

Most people say: "Model A is better than Model B" based on marketing claims or a single task. Your personal benchmark gives *evidence*, specific to your workflow.

## Diagram: Verification Layers

```
Code written by agent
    ↓
┌─────────────────────────────────┐
│ Syntax check (compiler)          │ ← Catches: typos, imports
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Type check (mypy, rustc, tsc)   │ ← Catches: type errors
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Lint (style, patterns)           │ ← Catches: anti-patterns
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Unit tests                       │ ← Catches: function bugs
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Integration tests                │ ← Catches: integration bugs
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ E2E tests                        │ ← Catches: workflow bugs
└─────────────────────────────────┘
    ↓
┌─────────────────────────────────┐
│ Production monitoring            │ ← Catches: real-world bugs
└─────────────────────────────────┘
    ↓
All pass → Code is ready for production
```

## Worked Scenario: Insufficient Verification

**Setup:** Agent writes a feature. Tests pass. You review and merge.

**Code:**
```python
def process_order(order_id: int, quantity: int) -> Order:
    order = db.get_order(order_id)
    order.quantity = quantity
    order.save()
    return order
```

**Tests:**
```python
def test_process_order():
    order = process_order(1, 10)
    assert order.quantity == 10
```

**What passed:**
- Syntax: ✓ (valid Python)
- Types: ✓ (correct types)
- Tests: ✓ (test passes)

**What failed:**
- Edge case: What if quantity < 0? (not tested)
- Concurrency: Two requests update the same order (not tested)
- Integration: After save(), do webhooks fire? (not tested)

**Real bug:** In production, someone sends quantity = -5. System allows negative quantities, breaks inventory system.

**Why it wasn't caught:**
- Unit test only checked happy path
- No integration test with webhooks
- No validation (should reject quantity < 1)

**How to fix:**
1. Add type check: `quantity: PositiveInt` (catches invalid input at type level)
2. Add unit test for invalid input
3. Add integration test with webhook firing
4. Add E2E test simulating user order flow

**Result:** All levels of verification catch the problem, not just tests passing.

## Interview Q&A

**Recall 1:** Name 5 levels of verification (from lowest to highest confidence).
*Must-say:* Syntax, types, lint, unit tests, integration tests. (Can also include E2E, production monitoring.)

**Probe 1:** A test passes, but code has a logic error. Which verification level would have caught it?
*Expected:*
- Unit test level: if the test is comprehensive (tests the edge case)
- Integration test level: if the error is in how systems interact
- If no test covers it: need a better test, not a better verification level

**Probe 2:** You're building a payment system. Which verification levels are non-negotiable?
*Expected:*
- Type checking (no amount passed as string)
- Unit tests (transaction logic)
- Integration tests (payment gateway interaction)
- E2E tests (full order-to-confirmation flow)
- Production monitoring (catch real-world failures)
- Security scan (secrets not in code)

**Scenario 1:** An agent's PR has 95% test coverage, all tests pass, types check. A user reports a bug. What went wrong?
*Expected:*
- Tests might not cover real-world scenarios
- Or: integration with external service isn't tested
- Or: concurrency/race condition not in unit tests
- Lesson: coverage % isn't the same as real-world verification

**Exercise 1:** Create a 10-task personal benchmark for your project. For each task, define success criteria. (15 min work)

---

## Checklist

- [ ] All code requires tests before merge (no exceptions)
- [ ] Type checking is enforced in CI (no skipping)
- [ ] Integration tests cover multi-component flows
- [ ] Personal benchmark defined (10-15 representative tasks)
- [ ] Regression detection in place (benchmark re-run monthly)
- [ ] Security scan runs before merge
- [ ] Coverage requirement set (> 80% minimum)
- [ ] E2E tests cover critical user workflows

## Common Mistakes

1. **Trusting test passing = code is correct.** Tests can be wrong too. You must review tests.
2. **Skipping verification layers.** "Types check, so we don't need tests." → Both are needed.
3. **No personal benchmark.** "Model X seems better" is opinion, not evidence.
4. **Coverage % without quality.** "We have 90% coverage" but tests are shallow (assert True, don't test behavior).
5. **Verification only at merge time.** CI should catch issues before human review. Fix at the boundary, not in review.

