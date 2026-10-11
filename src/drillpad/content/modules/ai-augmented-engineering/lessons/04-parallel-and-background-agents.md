# Parallel and Background Agents: Worktrees, Subagents, Isolation, Coordination

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Agents Block Each Other

You have two tasks:
1. Add logging to the auth module (30 min)
2. Refactor the cache layer (45 min)

**Sequential approach:**
- Start task 1 (agent A)
- Wait 30 min for task 1 to finish
- Start task 2 (agent B)
- Wait 45 min for task 2 to finish
- Total: 75 minutes

**Parallel approach:**
- Start task 1 (agent A) and task 2 (agent B) at the same time
- Both finish in ~45 min (time of longest task)
- Total: 45 minutes

**But agents conflict.** If both modify the same file, you get merge conflicts or lost changes. The question is: **How do you run agents in parallel safely?**

## The Isolation Model: Worktrees

A **worktree** is a separate copy of your git repo on disk, branched from main. Each agent gets its own worktree.

```
Project root: ~/myapp/

  main/
    ├─ src/
    ├─ tests/
    └─ .git

  worktree-auth/ (isolated copy, branched from main)
    ├─ src/
    ├─ tests/
    └─ .git/worktrees/auth

  worktree-cache/ (isolated copy, branched from main)
    ├─ src/
    ├─ tests/
    └─ .git/worktrees/cache
```

**Each agent works independently:**
- Agent A modifies auth in worktree-auth
- Agent B modifies cache in worktree-cache
- They never touch the same files
- No merge conflicts

**After both finish:**
- Agent A's PR (auth changes) merges to main
- Agent B's PR (cache changes) merges to main
- Parallel 45 min instead of sequential 75 min

## Diagram: Worktree Isolation

```
Time ───────────────────────────────────────────

Sequential:
  Agent A: [────────── task 1 (30 min) ──────────]
                                                  Agent B: [────── task 2 (45 min) ──────]
  Total: 75 min

Parallel (with worktrees):
  Agent A: [────────── task 1 (30 min) ──────────]
  Agent B: [────────── task 2 (45 min) ──────────]
  Total: 45 min (speedup = 1.67x)
```

## Diagram: Conflict-Free Merging

```
main branch: ──●────────────────────
              │
              ├─ worktree-auth
              │  └─ "add logging" ──→ Merge back to main
              │
              └─ worktree-cache
                 └─ "refactor cache" ──→ Merge back to main

Result: No conflicts (different files changed)
```

## Subagents: Delegation with Isolation

A **subagent** is an agent running in a separate thread or process, with its own context. You use subagents to:

1. Run multiple agents in parallel
2. Run expensive operations in the background (don't block your session)
3. Run scheduled tasks (e.g., "check for regressions every hour")

**Example workflow:**

```
You: "I need two things done:
  1. Add logging to auth module
  2. Refactor the cache layer"

System:
  Fork subagent A (for task 1)
  Fork subagent B (for task 2)
  
  Subagent A: Works in worktree-auth/
    Write code
    Run tests
    Open PR
    Report: "PR #234 ready for review"
  
  Subagent B: Works in worktree-cache/
    Write code
    Run tests
    Open PR
    Report: "PR #235 ready for review"

Both finish in parallel.
You review both PRs.
```

## Coordination Limits: When Parallel Breaks Down

Parallel only works if tasks are **independent**. If tasks depend on each other, parallelism creates coordination overhead.

```
Independent tasks (good for parallel):
  ✓ Task 1: Add logging to auth module
  ✓ Task 2: Refactor cache layer
  → No dependencies, can run in parallel

Dependent tasks (bad for parallel):
  ✗ Task 1: Add new cache API
  ✗ Task 2: Update auth module to use new cache API
  → Task 2 depends on Task 1
  → If you parallelize, Task 2 will conflict with Task 1
  → Better to do sequentially or split carefully
```

**Coordination cost formula:**

```
If tasks are independent:
  Parallel time = max(task1_time, task2_time)
  Speedup = (task1_time + task2_time) / max(task1_time, task2_time)

If tasks depend on each other:
  Parallel time = task1_time + task2_time + merge_conflict_resolution_time
  Speedup < 1 (slower than sequential!)
```

## Worked Example: Good Parallelism vs. Bad

**Good parallelism (independent tasks):**

Task 1: Add metrics to payment processing
Task 2: Add metrics to order processing

Both are isolated (different code paths). Can run in parallel. Both agents finish in 45 min. You get 2x speedup.

**Bad parallelism (dependent tasks):**

Task 1: Migrate database schema (add new column)
Task 2: Update service to use new column

Both touch the same files (schema migration and service code). If you parallelize:
- Agent 1 modifies migration script
- Agent 2 modifies service code to use new column
- But Agent 2 doesn't know about Agent 1's migration yet
- Merge conflict when Agent 2's PR is rebased on Agent 1's

Result: You spend 20 min resolving conflicts. Slower than sequential.

**Better approach:**
- Task 1: Migrate schema (15 min, simple)
- Wait for merge
- Task 2: Update service (30 min, now Agent 2 knows the migration is done)
- Total: 45 min sequential (vs. 20 min merge resolution cost)

## Scheduled Agents: Background Work

Some work doesn't need human input. You can schedule agents to run on a timer:

```
Every 6 hours: Check for dependency updates
  Agent: Run `cargo outdated`, open PR for major updates
  You: Review once a day, merge if safe

Every Monday 8am: Generate weekly report
  Agent: Aggregate metrics, write summary, commit to repo
  You: Review in standup

On new feature branch: Lint and format
  Agent: Run on every commit, fix formatting issues automatically
  You: Never think about formatting again
```

**Cost-benefit analysis:**

```
Manual format checking:
  - You: run `black .` manually → 2 min per commit
  - Over month: 50 commits × 2 min = 100 min wasted

Automated format fixing:
  - Setup: 10 min (configure hook)
  - Ongoing: 0 min (automatic)
  - Savings: 100 min per month
  - ROI: pays for itself in first week
```

## Interview Q&A

**Recall 1:** What is a worktree, and why does it prevent merge conflicts?
*Must-say:* A worktree is a separate copy of the repo. Each agent gets its own worktree, so they work on different files simultaneously without conflicts.

**Probe 1:** You have 5 independent tasks. Should you run 5 agents in parallel?
*Expected:*
- Depends on resources (CPU, memory, quota)
- If you have quota for 5 agents: yes
- If you have quota for 2 agents: run in batches
- Real constraint: how many concurrent agents can your setup handle?

**Probe 2:** Task A depends on Task B. Can you parallelize?
*Expected:*
- No, not efficiently
- Task B produces an output that Task A needs
- If you parallelize, Task A will be waiting for Task B anyway
- Better to sequence them or split the dependency (Task A uses intermediate output from Task B)

**Scenario 1:** You want to run 3 agents in parallel, but your CI system only supports 1 concurrent run. How do you handle it?
*Expected:*
- Use worktrees to isolate agents locally
- Agents 1-3 work in parallel on different worktrees
- When each agent finishes and opens a PR, CI runs sequentially (can't avoid that)
- Tradeoff: local work is parallelized, CI testing is sequential

**Exercise 1:** List 3 tasks in a project you know. Which are independent? Which are dependent? How many agents could you run in parallel? (5 min work)

---

## Checklist

- [ ] Understand worktree model (isolation without conflicts)
- [ ] Know when tasks are independent vs. dependent
- [ ] Can estimate coordination costs (merge conflict resolution)
- [ ] Identified a good use case for background agents in your workflow
- [ ] Know the limits of your setup (max concurrent agents, CI bandwidth)

## Common Mistakes

1. **Parallelizing dependent tasks.** "Both are important, so let's run them in parallel." → Merge conflicts, wasted time.
2. **Ignoring coordination costs.** "Parallel always faster!" → If merge resolution costs 30 min, parallelism is slower.
3. **Not cleaning up worktrees.** After task 1 finishes, its worktree takes up disk space. Delete it.
4. **Assuming CI can handle N agents.** Just because you can run 10 agents doesn't mean CI can test 10 PRs concurrently.
5. **Over-parallelizing.** 100 agents in parallel is fun in theory, but CI bandwidth, quota limits, and your review capacity will bottleneck.

