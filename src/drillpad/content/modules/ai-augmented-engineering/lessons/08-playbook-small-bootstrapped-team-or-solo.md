# Playbook: Small/Bootstrapped Teams & Solo — Speed with Guardrails

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Difference: You Can Move Fast, But You Can't Afford Mistakes

Large companies have process overhead but institutional memory. Small teams have speed but fragility.

**Your constraint:** One person (or 2-3) must maintain everything. One bad deploy breaks the product.

**Your advantage:** You can move 10x faster if you reduce risk per unit of work.

**The strategy:** CI gates (automated safety) + feature flags (safe rollbacks) + cost discipline (don't burn cash) + clear docs (onboard fast).

## Week One Setup: Getting Agents to Work for You

### Day 1: Risk Assessment

1. **Identify critical paths:**
   - What breaks the product? (auth, payment, data integrity)
   - What's easy to rollback? (UI, docs, non-critical features)

2. **Classify work:**
   - Tier A (high-risk): payment, auth, data migrations → you or trusted reviewer only
   - Tier B (medium-risk): API features, database schema → agent with CI gates
   - Tier C (low-risk): UI, tests, docs → agent with light review

3. **Write CLAUDE.md** (lesson 03):
   ```markdown
   # Claude in This Repo

   ## This Project
   [Small fintech app. Single person + part-time contractor.]

   ## High-Risk Code (You only)
     - /src/payment/
     - /src/auth/
     - Database migrations

   ## Medium-Risk Code (Agent, CI gates required)
     - /src/api/
     - /src/models/

   ## Low-Risk Code (Agent, light review)
     - /src/frontend/
     - /tests/
     - /docs/

   ## CI Requirements
     - All tests must pass (coverage > 80%)
     - Types must check (mypy --strict)
     - No secrets in code (scan enabled)
     - Performance: no > 10% latency regression

   ## Rollback Strategy
     - Feature flags for everything > low-risk
     - If deploy breaks: revert last commit + disable flag
     - No manual intervention needed
   ```

### Day 2-3: Set Up Safety Nets

1. **CI/CD pipeline (GitHub Actions, GitLab CI, etc.):**
   ```yaml
   # On every commit:
   - Tests pass
   - Types check
   - Lint passes
   - No secrets
   - Performance benchmarks (if regression, warn)
   - Deploy to staging
   
   # On merge to main:
   - All above + deploy to production
   - Rollback available (last 3 versions)
   ```

2. **Feature flags:**
   - All Tier B/C features behind flags
   - Deploy with flag off
   - Enable flag after verification in prod
   - If issues: kill flag, revert behavior

   ```python
   # Example (Python)
   if feature_flag('new_caching'):
       response = cached_get_user(user_id)
   else:
       response = db.get_user(user_id)
   ```

3. **Error budget + alerting:**
   - Set up logging (CloudWatch, Datadog, etc.)
   - Alert on: errors > 1%, latency > 200ms, downtime
   - Gives you 10 min to catch and rollback after deploy

### Day 4: Set Agent Autonomy Level

From lesson 01:
- **Tier A code:** Rung 1 (suggest only, you decide merge)
- **Tier B code:** Rung 2-3 (agent edits, CI gates, you review)
- **Tier C code:** Rung 3-4 (agent edits, CI gates, auto-merge if green)

```
Day 4 setup:
  ├─ Tier A: agent suggests, you review and decide
  ├─ Tier B: agent commits to branch, CI gates it, you review
  └─ Tier C: agent commits to branch, CI gates it, auto-merge if green
```

### Day 5-7: Automate High-ROI Tasks

**Start here (easy wins, high impact):**

1. **Documentation:** Agent keeps docs in sync with code (Tier C)
   - ROI: 10 min per week saved

2. **Tests:** Agent writes tests for new code (Tier B)
   - ROI: you catch bugs faster, confidence in deploy

3. **Boilerplate:** Agent scaffolds new features (Tier C)
   - ROI: 1 hour per feature

4. **Refactoring:** Agent cleans up obvious issues (Tier C)
   - ROI: 30 min per week

5. **Secrets/config management:** Agent helps but never touches (Rung 1)
   - ROI: prevents security errors

**Don't automate yet:**
- Payment processing (Tier A, too risky early)
- Auth logic (Tier A)
- Database migrations (Tier A, needs verification)

## Cost Discipline: Running Lean

Agents cost money:
- API calls: $0.001–0.01 per task (usually < $1/day for 1 person)
- Compute (CI): $10–100/month
- Infrastructure (servers, DB): your main cost

**Set a budget:**

```
Monthly AI budget: $50
  ├─ Agent API: $20 (generous)
  ├─ CI compute: $20
  └─ Headroom: $10

If you hit $50: pause agents, audit costs
```

**Cost reduction:**

```
Before agents:
  Your time: $100/hour
  1 hour of code review per day = $2,400/month in your time
  
With agents:
  Your time: $100/hour
  30 min of review per day = $1,200/month in your time
  Agent API cost: $20/month
  Net savings: $1,180/month

Even paying for agents, you save money.
```

## Cheap Rollbacks: How to Survive Mistakes

You (solo founder) deploy agent code. It breaks production. You have 5 minutes to fix it.

**Without rollback:**
- Diagnose (10 min)
- Fix (20 min)
- Deploy (5 min)
- Downtime: 35 min
- Cost: lost users, lost revenue, lost trust

**With rollback:**
- See error (1 min)
- Revert to last good commit (30 sec)
- Deploy (2 min)
- Downtime: 3.5 min
- Cost: much less, can debug later

**How to enable rollbacks:**

1. **Keep version history:**
   - Deploy with git commit hash: `v123_abc123` (commit hash in tag)
   - Last 5 versions kept in production
   - Can revert to v123_abc0 if v123_abc1 is bad

2. **Feature flags:**
   ```python
   # In code
   if feature_flag('new_feature'):
       use_new_feature()
   else:
       use_old_feature()
   
   # On alert: disable flag in config
   # No deploy needed, just config change
   # Reverts production instantly
   ```

3. **Database rollbacks:**
   - Never write-once-can't-undo migrations
   - Always make migrations reversible
   - Test rollback path before deploy

   ```sql
   -- Good: reversible
   ALTER TABLE users ADD COLUMN last_login TIMESTAMP DEFAULT NOW();
   -- Can rollback: ALTER TABLE users DROP COLUMN last_login;

   -- Bad: irreversible
   DELETE FROM users WHERE created_at < '2020-01-01';
   -- Can't rollback: data is gone
   ```

## Docs: Onboarding Agents AND Humans

Your CLAUDE.md should be clear enough that:
1. An agent can understand it and make right decisions
2. A new human hire can onboard in 30 minutes
3. You don't have to re-explain the rules every time

```markdown
# Development Guide

## Code Style
- Python: 3.11+, type hints required (mypy --strict)
- Max line length: 100
- Format: `black --line-length 100 .`

## Testing
- All code requires tests
- Run: `pytest -xvs tests/`
- Coverage: must be > 80%

## Deployment
- Push to main → CI runs → auto-deploy to prod (if green)
- Feature flags for all new features (deploy dark, enable later)
- Rollback: `git revert COMMIT_HASH`, push to main, auto-deploys

## What's High-Risk (Don't Touch)
- /src/payment/ (manual review required)
- /src/auth/ (manual review required)
- Database migrations (manual testing)

## High-ROI Tasks for Agents
- Write tests for new features
- Update docs when code changes
- Refactor obvious issues (long functions, naming)
- Add type hints to old code

## When to Ask For Help
- Anything in high-risk code
- Anything that could lose data
- Anything with external API calls (check approved list)
```

## Worked Example: Solo Founder with Agent

**Setup:** You're a solo founder, 20 hours/week on the product.

**Before agents:**
- Mon: 2 hours planning + bug fixes
- Tue-Wed: 8 hours on new feature
- Thu: 8 hours on new feature + code review
- Fri: 4 hours deploy + monitoring
- Total: 22 hours (over budget)
- Features shipped: 1/month

**With agents (week 1-2):**
- Mon: 1 hour planning, 1 hour starting agent tasks
- Tue-Wed: Agent works on feature while you work on design
- Thu: 2 hours reviewing agent work, 2 hours your own code
- Fri: 2 hours deploy + monitoring, 2 hours next week planning
- Total: 16 hours (under budget)
- Features shipped: 2/month
- Bonus: agent caught a bug you would have missed

## Interview Q&A

**Recall 1:** Name 3 ways to make deployments safe in a small team.
*Must-say:* CI gates (tests pass before merge), feature flags (deploy dark), cheap rollbacks (revert commit, auto-deploy).

**Probe 1:** An agent's PR passes all CI gates. Should you auto-merge?
*Expected:*
- Depends on Tier (Tier C: yes, Tier B: you review, Tier A: never)
- Even if Tier C, spot-check occasionally (is CI catching real issues?)
- If CI starts missing things, reduce autonomy

**Probe 2:** Your product is down because of agent code. How do you recover?
*Expected:*
- Identify last good commit (before the bad PR merged)
- `git revert <bad-commit>`
- Push to main
- CI runs, auto-deploys
- Should take 5 min total
- Investigate root cause later

**Scenario 1:** You have 10 hours/week for your side project. Agent can do 8 hours of work per week. What do you prioritize?
*Expected:*
- Agent: boilerplate, tests, docs, refactoring (Tier C)
- You: design decisions, code review, deployment, customer feedback
- Don't automate your thinking or your judgment

**Exercise 1:** Design a feature-flag strategy for your project. (10 min work)

---

## Checklist

- [ ] Classified code into Tier A/B/C by risk
- [ ] Set up CI pipeline (tests, types, lint, secrets scan)
- [ ] Enabled feature flags for all new features (deploy dark)
- [ ] Set up cheap rollbacks (git revert + auto-deploy)
- [ ] Set monthly AI agent budget
- [ ] Wrote clear CLAUDE.md (agent + human readable)
- [ ] Identified high-ROI tasks to automate first
- [ ] Set up error alerting (catch issues fast)

## Common Mistakes

1. **No CI gates.** Agent code commits directly, breaks production.
2. **No rollback strategy.** When agent code breaks, takes 30 min to fix.
3. **Automate the wrong things first.** Start with payment logic instead of docs.
4. **No feature flags.** Can't deploy safely without blocking users.
5. **Automating your judgment.** Agent can't decide architecture, data schema, etc.

