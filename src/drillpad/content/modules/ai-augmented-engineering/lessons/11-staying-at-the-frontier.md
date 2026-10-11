# Staying at the Frontier: Benchmarking, Routine, Rules, Track Record

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Hype vs. Reality

AI tooling changes fast. New models every 3 months. New tools every month. New claims every week.

**The trap:** You chase every new thing, spend time evaluating, get distracted, ship nothing.

**The alternative:** Have a repeatable routine that keeps you at the frontier without consuming your life.

## The Routine: Not Hype, Just Discipline

**Weekly (30 min, Friday):**
- Read changelogs of tools you use
- Note any breaking changes or new features
- Mark anything that might affect your workflow

**Monthly (1 hour, first Friday):**
- Run your personal benchmark (lesson 05)
- Compare results to last month
- If quality dropped: investigate why
- If new tool seems better: test it on benchmark

**Quarterly (2 hours, first week):**
- Review "scaffolding you can delete" (see below)
- Update DECISIONS.md with new learnings
- Teach one thing (write a blog post, talk, memo)
- Plan next quarter's tech choices

**Yearly (half day):**
- Full retrospective: what worked, what didn't?
- Identify patterns (which tool mistakes did you make?)
- Set next year's learning goals
- Update resume/portfolio with progress

## Benchmark Template: 10-15 Real Tasks

These are your regression detectors. Use them to evaluate new tools/models.

```markdown
# Personal Benchmark Tasks

## Task 1: Add logging to payment module (Tier: Easy, Type: Mechanical)
**Spec:** Add debug logging to payment processing, 50-100 lines, 2 tests
**Success criteria:** 
  - Diff < 100 lines
  - No scope creep
  - Tests pass
  - Type checking passes
**Expected time:** 10 min
**Metric to track:** Time taken, whether I needed to review/fix

## Task 2: Fix off-by-one pagination bug (Tier: Medium, Type: Bug)
**Spec:** Users can't see last page of results. Debug and fix.
**Success criteria:**
  - Root cause identified (off-by-one in loop)
  - Test added (passes before fix, fails after)
  - Fix is minimal (< 5 lines changed)
**Expected time:** 15 min
**Metric to track:** Did agent find the bug? Did it add extra changes?

## Task 3: Refactor auth module for testability (Tier: Hard, Type: Design)
**Spec:** Current auth module is hard to test. Refactor to inject dependencies.
**Success criteria:**
  - Testability improves (can unit test without mocking DB)
  - No behavior changes (still works the same)
  - Tests are added
**Expected time:** 45 min
**Metric to track:** Design quality, whether refactor was appropriate

## Task 4: Implement exponential backoff retry logic (Tier: Medium, Type: Algorithm)
**Spec:** API client retries failed requests with exponential backoff.
       Max 3 retries, start at 100ms, cap at 10s.
**Success criteria:**
  - Tests cover: success case, retry case, max retries exceeded
  - Code is < 50 lines
  - Matches spec exactly
**Expected time:** 20 min
**Metric to track:** Did it match spec? Any edge cases missed?

## Task 5: Write a personal knowledge base capture system (Tier: Hard, Type: Exploratory)
**Spec:** Design a system to capture learning (decisions, patterns, failure modes)
       so you can reference it later. Simple, not fancy.
**Success criteria:**
  - Something works and you've used it for 1 week
  - Captures real learnings
  - Format is portable (markdown, not proprietary)
**Expected time:** 90 min
**Metric to track:** Is it useful? Does it reduce duplicate decisions?

... (10-15 tasks total, mix of difficulties and types)
```

## How to Use Benchmark Results

```
Baseline (Tool A, Model V1):
  Task 1: 10 min, no fixes needed ✓
  Task 2: 15 min, 1 fix needed (off-by-one) ✓
  Task 3: 45 min, design was OK ✓
  Task 4: 20 min, no issues ✓
  Task 5: 90 min, useful system ✓
  
  Total: 180 min, 1 fix
  Quality: 95%
  
Month later (Tool B, Model V2):
  Task 1: 8 min, no fixes ✓
  Task 2: 12 min, caught bug instantly ✓
  Task 3: 40 min, better design ✓
  Task 4: 18 min, with comments ✓
  Task 5: 75 min, also good ✓
  
  Total: 153 min, 0 fixes
  Quality: 98%
  
Conclusion: Tool B is 15% faster and higher quality. Worth switching.
```

## Primary-Source Reading: Weekly 30 Min

Don't trust marketing claims. Read actual documentation.

```
Every Friday, 15-30 min:

Tool A changelog (Jan version release notes):
  - Feature X added
  - Bug Y fixed
  - Breaking change: parameter Z renamed
  → You: note that Z rename affects your workflow

Tool B docs (new pattern page):
  - New capability
  - When to use, when NOT to use
  → You: maybe relevant to my work? Test next month

Conference talk (watch 15 min segment):
  - New technique
  → You: seems interesting, add to backlog

Twitter/Discord/Slack (skim 10 min):
  - Hype about new tool
  → You: probably not production-ready, wait 6 months
```

**Goal:** Stay informed about what exists, decide deliberately what to use. Not chase every shiny thing.

## Quarterly Scaffolding Review: What Can You Delete?

Every 3 months, ask: "What abstractions or tools can I delete?"

```
Q1 review:
  - Started using caching library (seemed necessary)
  - 3 months in: could be replaced with native code (5 lines)
  - Decision: remove library, simplify
  
  - Added linting tool (thought we needed it)
  - 3 months in: it catches 2 issues per month (not worth the overhead)
  - Decision: remove tool, rely on CI tests instead

This is the opposite of "add stuff" and equally important.
```

**Why:**
- Every tool has friction (setup, config, learning)
- If tool isn't paying for itself: delete it
- Result: simpler, faster, fewer dependencies

## Measuring Outcomes: Merged and Not Reverted

Don't measure: "How many PRs did I merge?"
Measure: "How many PRs did I merge that are still in production?"

```
Bad metric: Merged 50 PRs
  Could be 50 bad PRs that were reverted

Good metric: Merged 50 PRs, 48 still in production
  Only 2 reverted (4% revert rate)

Revert rate is the truth metric.
  < 1% = you're shipping high quality
  1-5% = acceptable
  > 5% = something is broken (process, tooling, verification)
```

**Track this:**
```
Monthly report:
  Merged: 50 PRs
  Reverted: 2 PRs
  Revert rate: 4%
  
  (Revert rate stayed stable = quality is stable)
```

## Staying Sharp: Keep Fundamentals

Agents are good at many things, but they hallucinate subtly.

**Example:** Agent-generated code looks right but has a subtle off-by-one error that only manifests in production.

**Defense:** Keep fundamentals sharp so you can spot subtle wrong output.

```
Monthly:
  - Write one function from scratch (no agent)
  - Fix one production bug manually (understand the pattern)
  - Review one architecture decision (can you explain tradeoffs?)
  
Result: You stay sharp, can spot when agent output is subtly wrong
```

## Teaching: Solidify Your Own Understanding

Every quarter, teach something:

```
Month 1: Blog post: "How I use agents without losing my skills"
Month 4: Talk at meetup: "AI-augmented engineering at my company"
Month 7: Memo: "Lessons learned: 10 mistakes we made with agents"
Month 10: Thread: "Personal benchmark results: which tool is best?"
```

**Why:** Teaching forces clarity. You notice gaps in your own understanding. Plus, you build a track record (good for interviews, hiring, reputation).

## Worked Example: 1 Year at the Frontier

**Jan - Dec:**

Jan-Feb:
- Setup routine (weekly reads, monthly benchmarks)
- Tool A (baseline benchmark): 180 min total

Mar-Apr:
- New Tool B released
- Read docs: "Looks promising"
- Run benchmark on Tool B: 160 min, 2% quality improvement
- Decision: keep Tool A, watch Tool B

May-Jun:
- Tool A makes breaking change
- Affects your workflow (parameter Z renamed)
- Takes 30 min to update code
- Lesson: lock version, don't auto-upgrade

Jul-Aug:
- Tool C released (new category of capability)
- Benchmark Tool C: time is same, but opens new possibilities
- Write blog post: "Tool C for X use case"
- Decision: use Tool C for new projects, not existing ones

Sep-Oct:
- Full retrospective
- Tools used: A (80%), B (5%), C (15%)
- Revert rate: 2% (good)
- Skill sharpness: still writing code weekly (good)
- Lessons: deleting unnecessary scaffolding saved 5 hours

Nov-Dec:
- Plan next year: maybe Tool B becomes primary (do a migration)
- Update resume: "1 year of AI-augmented development"
- Update portfolio: ship something new that showcases your skills

## Interview Q&A

**Recall 1:** What's the difference between staying at the frontier and chasing hype?
*Must-say:* Frontier = systematic routine (benchmarks, primary-source reading). Hype = reacting to marketing claims.

**Probe 1:** A new AI tool is released. How do you decide if you should use it?
*Expected:*
- Not: immediately try it (hype)
- Not: ignore it (stuck in past)
- Yes: run benchmark on it, compare to current tools
- Only switch if it's better at something you care about

**Probe 2:** Your agent's code quality dropped. How do you detect it?
*Expected:*
- Personal benchmark (re-run monthly, watch for degradation)
- Revert rate (track PRs that had to be reverted)
- Spot checks (review 5% of auto-merged PRs)

**Scenario 1:** You've been using agents for 1 year. You're interviewing for a new role. How do you explain it?
*Expected:*
- "I've measured the impact: 20% velocity increase, 2% revert rate"
- "I keep skills sharp: write code weekly, review agent output, maintain benchmarks"
- "I learned: this tool is good at X, bad at Y, so I use it for X"
- Shows: intentional, measured, learning-oriented

**Exercise 1:** Design a personal benchmark for your project. Plan how you'll measure over 3 months. (15 min work)

---

## Checklist

- [ ] Have a weekly routine (30 min reading/review)
- [ ] Have a monthly routine (run benchmark)
- [ ] Have a quarterly routine (scaffolding review, teaching)
- [ ] Personal benchmark defined (10-15 tasks)
- [ ] Track revert rate (metric of quality)
- [ ] Keep fundamentals sharp (write code weekly)
- [ ] Teaching plan (blog post, talk, memo quarterly)
- [ ] Yearly retrospective scheduled

## Benchmark Running Template

```
Tool: [Name]
Model version: [Version]
Date: [YYYY-MM-DD]

Task results:
  Task 1: [Time] min, [Fixes needed] fixes, [Notes]
  Task 2: ...
  
Aggregate:
  Total time: [XXX] min
  Fixes needed: [N]
  Quality: [X]%
  
Compared to last run:
  [Faster/slower], [Better/worse] quality
  
Decision:
  [Keep, Evaluate more, Switch, Deprecate]
```

## Common Mistakes

1. **Chasing hype.** New tool released → immediately switch. Result: always switching, never shipping.
2. **No benchmark.** "Tool B seems better" is opinion, not evidence.
3. **Revert rate ignored.** You're shipping bugs, don't notice.
4. **Stop writing code.** Agent does everything, you lose skills, can't debug.
5. **No teaching.** You learn things, don't consolidate. Forget in 3 months.

