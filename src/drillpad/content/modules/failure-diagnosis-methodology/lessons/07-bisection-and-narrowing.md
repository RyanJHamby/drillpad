# Bisection and Narrowing: Pinpointing Root Cause Across Dimensions

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: "Which Commit Broke This?"

You have 100 commits between last known good and now. Which one broke the test?

**Brute force:** Try each commit (100 builds, 10 min each = 16 hours).
**Smart:** Binary search commits (log_2(100) = 7 builds = 70 minutes).

This chapter covers systematically narrowing the root cause across multiple dimensions: commits, config, data, time, requests, and environments.

## Git Bisect: Finding the Bad Commit

```
Symptom: Test passes on commit ABC123, fails on HEAD

Process:
  git bisect start
  git bisect bad HEAD          # Current commit is broken
  git bisect good ABC123       # That commit was good
  
Git checks out midpoint:
  Commit XYZ789 (between good and bad)
  
You test it:
  - If it fails: git bisect bad XYZ789
  - If it passes: git bisect good XYZ789
  
Git repeats (binary search)
  
After ~7 tests: Found the exact commit that broke it
```

**Real example:**

```
Last known good: 2 days ago
Current (broken): Today
Commits: 47 total

Bisect sequence:
  Test commit 24 (midpoint): FAIL → search older half
  Test commit 12: FAIL → search older half
  Test commit 6: PASS → search newer half (between 6 and 12)
  Test commit 9: FAIL → narrowed to 9-12
  Test commit 10: PASS → narrowed to 10-12
  Test commit 11: FAIL → FOUND IT (commit 11 is the culprit)

Total time: 5 builds * 2 min = 10 minutes (vs. 47 * 2 = 94 minutes)
```

## Beyond Commits: Bisecting Other Dimensions

Not all bugs are caused by recent commits. Bisect over:

**1. Configuration** (which config flag breaks it?)

```
Flags: feature_flag_A, feature_flag_B, feature_flag_C
       feature_flag_D, feature_flag_E (5 flags = 2^5 = 32 combinations)

Symptom: Works with all OFF, fails with some ON

Binary search:
  Test A,B,C on / D,E off: Works
  Test A,B,C on / D,E on: Fails
  → Problem is in D or E
  
  Test A,B,C,D on / E off: Fails
  → Problem is in D
  
  Isolate: feature_flag_D is the culprit
```

**2. Data / Input** (which data triggers the bug?)

```
Data: 100,000 rows in a table
Symptom: Query slow (expected 10ms, actual 5000ms)

Binary search over data:
  Test with rows 1-50,000: Query is fast (10ms)
  Test with rows 50,001-100,000: Query is fast (10ms)
  Test with all rows: Query is SLOW (5000ms)
  
  → Problem is in the combination, not individual ranges
  
  Test with rows 1-50,000 + 75,000-100,000 (skip middle):
  → Still slow!
  
  → Not about data size, but about specific rows
  → Find which rows cause slowness (delta debug individual rows)
```

**3. Time** (which period does it happen?)

```
Symptom: Database query slow between 9am-11am, fast otherwise

Hypothesis: Nightly batch job overlap?

Binary search over time:
  9:00-9:30: Slow
  9:30-10:00: Slow
  10:00-10:30: Slow
  10:30-11:00: Slow
  11:00-11:30: Fast
  
Narrowed: Starts at 9:00, ends at 11:00
Check: Batch job runs 9:00-11:00?
Result: CONFIRMED
```

**4. Requests / Call Path** (which API call is slow?)

```
System: Multi-service architecture
Symptom: P99 latency spike for user requests

Trace a single request:
  Frontend → API gateway → Service A → DB (100ms)
                      ↓
                    Service B (1000ms)  ← SLOW
                      ↓
                    Service C → Cache (10ms)

Bisect path (where does time accumulate?):
  Is it Service B's code? (add timing around each function)
  Is it Service B's dependency? (remove dependency, mock it)
  Is it network to Service B? (ping, latency)
  
Found: Service B calling slow external API (1000ms per call)
```

## Differential Debugging: Good vs. Bad Environment

What's different between working and broken?

```
Symptom: Feature works on staging, fails on production

Good (staging):
  - DB: PostgreSQL 12
  - Python: 3.9
  - Memory: 8GB
  - Concurrency: 4 workers
  
Broken (production):
  - DB: PostgreSQL 14
  - Python: 3.11
  - Memory: 64GB
  - Concurrency: 16 workers

Bisect by changing one variable:
  Prod config, but Python 3.9: Still fails?
  → Python version not the issue
  
  Prod config, but DB Postgres 12: Still fails?
  → Database version might be issue
  
Keep narrowing until you find the variable.
```

## Last-Known-Good (LKG): Regression Identification

A feature worked 3 weeks ago. Now it doesn't. But you've deployed 200 times since.

```
LKG identification:
  3 weeks ago: Feature worked (test: deploy_ABC.v123)
  Today: Feature broken (test: deploy_XYZ.v789)
  
Binary search:
  Test deploy.v450 (midpoint): Works
  Test deploy.v650: Works
  Test deploy.v750: Fails
  Test deploy.v700: Fails
  Test deploy.v675: Works
  Test deploy.v688: FAILS  ← Found it
  
Regression committed in deploy.v688
What changed? Just 5 commits. Check each one.
```

## Narrowing by Layer: Where in the Stack?

```
System: Frontend → API → Service → DB

Symptom: Users report slow searches

Narrow by layer:
  1. Is it frontend? (time from click to server)
     Monitor: navigator.sendBeacon() timing
     Result: 50ms (fast) → not frontend
     
  2. Is it API latency?
     Request: GET /search?q=foo
     Response time: 100ms (normal)
     Result: Not API
     
  3. Is it service code?
     Profile service: Most time in loop (line 42)
     Result: Service code is slow
     
  4. Is it database?
     Timing inside service:
       Query: 90ms
       Processing: 5ms
       Return: 5ms
     Result: DB is slow
     
  5. Is it the index?
     Test: EXPLAIN PLAN for query
     Result: Full table scan (no index!)
     
  6. Is it table size?
     Table rows: 100M (grew from 1M last month)
     Result: Query plan changed due to table size
     
Root cause: Table grew, query plan fell back to full scan
```

## Interview: Demonstrating Bisection

**Q: "How would you find which commit broke a flaky test?"**

Strong answer:
```
"Bisect over commits:

1. git bisect start
2. Mark current as bad, known-good 1 week ago as good
3. Git checks out midpoint
4. I run test 10x (to account for flakiness)
5. Based on pass/fail, git narrows search
6. After ~7 iterations: Found the commit

Once found, review that commit:
  - What did it change?
  - Does it introduce timing assumptions?
  - Race condition?
  
Fix: Either revert or fix the root cause.
Verify: Regression test with original flaky seed."
```

## Checklist

- [ ] Binary search strategy chosen (commits, config, data, time)
- [ ] Search space defined (good vs. bad bounds)
- [ ] Test for discriminating (can tell if hypothesis good/bad)
- [ ] Stopping condition (when is root cause found?)
- [ ] Results logged (which commit/config/data is culprit)

## Common Mistakes

1. **Not defining good/bad clearly.** "It's slow" is vague. "GET /api/search takes 1000ms when it should be 100ms" is clear.
2. **Linear search instead of binary.** Testing each commit sequentially (50 commits = 50 tests) instead of binary search (50 commits = ~6 tests).
3. **Not accounting for flakiness.** Flaky test: Run it once, seems good, but it fails 5% of time. Run 10x to be sure.
4. **Forgetting to check other dimensions.** "Commit looks fine." But maybe config changed, or data changed, or load changed.
5. **Not narrowing far enough.** Found the commit, but it has 50 line changes. Narrow further: which function? Which line?

