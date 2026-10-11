# Repo Setup for Agents: CLAUDE.md, Permissions, Hooks, Safe Defaults

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: Agents Need Instructions, Not Just Ability

You invite an agent into a new codebase. The agent doesn't know:
- Which files can be modified (vs. read-only)
- What the naming conventions are
- When to run tests vs. when to skip
- Whether this is a monorepo with multiple services
- What the commit message format should be
- Whether this project has security constraints

**Result:** Agent makes reasonable-but-wrong decisions. You spend 10 min reviewing, finding issues, asking for revisions.

**With clear setup:** Agent has written instructions, knows the constraints, makes right decisions. You spend 2 min reviewing.

## The Instruction File: CLAUDE.md

Every repo that uses agents should have a `CLAUDE.md` file at the root. This is the agent's "team manual."

**What goes in CLAUDE.md:**

```markdown
# Claude in This Repo

## What This Project Is

[2-3 sentences about the project, primary language, main patterns]

## Constraints and Guardrails

### Read-Only Files
- README.md (don't edit)
- CHANGELOG.md (only append via agent-created commit message)
- docs/architecture/ (don't edit, proposals go in ADRs)

### Code Style
- Python: [version], type hints required (mypy --strict)
- Naming: snake_case for functions, CAPS for constants
- Max line length: 100 (enforced by lint)
- No copy-paste; factor out to shared utility

### Testing
- All new code requires tests
- Test file naming: test_*.py (not *_test.py)
- Run: `pytest -xvs tests/` before committing
- Coverage minimum: 80%

### Commit Message Format
- Style: conventional commits (feat:, fix:, refactor:, etc.)
- Example: `feat: add user caching with 5-min TTL`
- Don't sign off with commit message; CI does that

### Security Constraints
- No credentials in code (use .env, not hardcoded)
- No SQL injection: use parameterized queries, never string interpolation
- No arbitrary code execution (validate input before eval)

### When to Ask for Clarification
If the task:
  - Could affect payment/auth flow
  - Could affect 3+ existing features
  - Has ambiguous acceptance criteria
Then ask before starting work.

## How This Project Uses Agents

- Agents can edit code and open PRs
- Agents can NOT merge without human approval
- Agents can NOT run deploy commands
- Expected: agent will ask for clarification on ambiguous specs
```

**Key principle:** CLAUDE.md is a contract between you and the agent. It's checked into git, versioned, and applies to every agent session.

## Diagram: Instruction Flow

```
┌─────────────────────┐
│  Agent joins repo   │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ Read CLAUDE.md                  │
│ ├─ Code style (naming, format)  │
│ ├─ Read-only files              │
│ ├─ Test requirements            │
│ ├─ Security constraints         │
│ └─ When to ask for clarification│
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ Understand repo structure        │
│ ├─ How many services?           │
│ ├─ Where are tests?             │
│ └─ CI/CD pipelines?             │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────┐
│ You give task spec              │
│ Agent knows:                    │
│ ├─ What files to modify         │
│ ├─ What tests to write          │
│ ├─ Naming conventions           │
│ └─ When to ask for help         │
└─────────────────────────────────┘
```

## Permission Design: What Agents Can Touch

Different repos have different risk levels. Match permissions to risk.

**Low-risk** (agents can edit freely):
- Utility libraries, internal tools, test code
- Agent can: create files, modify anything, commit

**Medium-risk** (agents can edit, but with review gates):
- Core application code (UI, API)
- Agent can: create files, modify code, open PRs
- Agent cannot: merge without human approval

**High-risk** (agents read-only or strictly bounded):
- Security, payment processing, compliance code
- Agent can: read, maybe suggest
- Agent cannot: modify, commit, merge

**Critical-risk** (no agent access):
- Crypto, key management, financial calculations
- Agent can: read (for context)
- Agent cannot: edit, even in a PR

**Example permission matrix:**

```
File/Path              | Low-risk | Medium | High | Critical
─────────────────────────────────────────────────────────────
src/api/user.py        |   RWX    |  RWX   |  RO  |   RO
src/auth/login.py      |   RWX    |  RWX   |  R   |   RO
src/payment/stripe.py  |   RWX    |  RW    |  RO  |   --
src/crypto/hash.py     |   RWX    |  RO    |  RO  |   RO
tests/**               |   RWX    |  RWX   |  RWX |  RW
README.md              |   RO     |  RO    |  RO  |   RO
CLAUDE.md              |   RO     |  RO    |  RO  |   RO

RWX = Read/Write/Execute
RW = Read/Write
RO = Read-Only
-- = No access
```

## Hooks: Automation as Guard Rails

A **hook** is an automated check that runs on agent actions. Examples:

```
Hook 1: Pre-commit hook
  Trigger: Before agent commits
  Check: Lint, type check, security scan
  If fails: Commit is blocked, agent gets feedback

Hook 2: Post-PR-open hook
  Trigger: After agent opens PR
  Check: Is this PR < 200 lines?
  If fails: Leave a comment ("This looks large, splitting into subtasks...")

Hook 3: Cost budget hook
  Trigger: Before agent runs expensive operation
  Check: Will this cost exceed budget?
  If yes: Ask user for approval

Hook 4: Security scan hook
  Trigger: After agent modifies any file
  Check: Secrets in code? Hardcoded credentials?
  If yes: Reject, point out issue
```

**Real example (Python project):**

```bash
#!/bin/bash
# .git/hooks/pre-commit (runs before agent commits)

echo "Running checks..."
python -m pytest -q tests/
if [ $? -ne 0 ]; then
  echo "Tests failed. Commit blocked."
  exit 1
fi

python -m mypy --strict .
if [ $? -ne 0 ]; then
  echo "Type errors. Commit blocked."
  exit 1
fi

echo "All checks passed. Proceeding."
exit 0
```

Agent commits → hook runs → tests/types pass → commit succeeds.

## Worked Example: Repo Setup Failure

**Setup:** New repo, no CLAUDE.md. Agent starts working.

**Task:** "Add caching to the user endpoint."

**Agent's assumptions:**
- Code style: assumes PEP8 (reasonable, but maybe you use different line length)
- Tests: writes tests with pytest (good, but maybe you use unittest)
- Commit message: writes "Add caching" (simple, but you use conventional commits)
- Scope: includes refactoring the user model (not in spec, but agent thought it helpful)

**Result:** You review, find:
- Line length is 120, not 100 (not a big deal, but inconsistent)
- Tests are in tests/unit/, not tests/api/ (your pattern)
- Commit message isn't conventional (ci/cd expects it)
- Scope included refactoring (you said not to)

**Time to fix:** 20 min of back-and-forth.

**With CLAUDE.md:**
- Agent reads: "Max line length: 100"
- Agent reads: "Test file naming: test_*.py in tests/api/"
- Agent reads: "Commit message: conventional commits"
- Agent reads: "Out-of-scope: refactoring adjacent code"

**Result:** First PR is correct. Review: 5 min.

## What Belongs in CLAUDE.md vs. Task Spec

**CLAUDE.md (repo-wide, permanent):**
- Code style rules (naming, formatting, line length)
- Test patterns (where to put tests, how to name them)
- Read-only files
- Security constraints
- Commit message format
- Repo structure (monorepo, services, etc.)

**Task spec (per-task, temporary):**
- Specific feature requirements
- Acceptance criteria
- Out-of-scope for THIS task
- Test requirements for THIS feature
- Diff size limits

**In a spec, you can reference CLAUDE.md:**
```
TASK: Add caching to user endpoint.

ACCEPTANCE CRITERIA:
  ✓ GET /users/{id} returns cached response
  ✓ Cache TTL is 5 minutes

TEST REQUIREMENT:
  - See CLAUDE.md for test location and naming
  - Add test_cache_hit and test_cache_expiry

DEFINITION OF DONE:
  - Follow CLAUDE.md code style (line length: 100, type hints required)
  - Diff under 150 lines
```

## Interview Q&A

**Recall 1:** What should CLAUDE.md contain?
*Must-say:* Code style, test patterns, read-only files, security constraints, commit message format, when to ask for clarification.

**Probe 1:** You're setting up a payment processing service. What constraints would you put in CLAUDE.md?
*Expected:*
- Security: no hardcoded credentials, all payment logic must use parameterized queries
- Testing: all payment operations must have integration tests (not just unit tests)
- Review: payment code is high-risk, mention in "when to ask"
- Scope: agent can modify payment flow only if spec is explicit about it

**Scenario 1:** An agent opens a PR that modifies a read-only file. How should you handle it?
*Expected:*
- Hook should catch it and reject the commit
- If hook didn't catch it: point out in review, ask agent to revert
- Check CLAUDE.md: is the file listed as read-only? If not, add it

**Exercise 1:** Create a CLAUDE.md for a project you're working on. (10 min work)

---

## Checklist

- [ ] Created CLAUDE.md with code style, test patterns, and constraints
- [ ] Listed read-only files explicitly
- [ ] Defined security constraints (credentials, queries, etc.)
- [ ] Set up pre-commit hooks (tests, lint, type check)
- [ ] Wrote "when to ask for clarification" section
- [ ] Shared CLAUDE.md with agents at start of session

## Common Mistakes

1. **CLAUDE.md is too long or aspirational.** Keep it to essentials. If you're explaining WHY you use PEP8, that's too much. Just say "PEP8 style."
2. **No read-only files listed.** Agents will edit files they shouldn't. Be explicit.
3. **Hooks are too strict.** If pre-commit hook takes 5 min to run, agents will find ways to skip it. Keep hooks fast (< 2 min).
4. **Security constraints are vague.** "Don't do anything unsafe" → "No SQL injection: use parameterized queries, never string interpolation."
5. **CLAUDE.md isn't versioned.** Once you write it, commit it. It's part of the repo.

