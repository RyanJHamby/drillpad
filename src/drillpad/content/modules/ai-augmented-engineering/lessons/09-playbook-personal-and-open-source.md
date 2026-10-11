# Playbook: Personal & Open-Source Projects — Disclosure, Provenance, Licensing

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Difference: You're Building Your Track Record

In a company: agents are a productivity tool. Invisible to the world.

In open-source: your code is your reputation. People will judge your work.

**The principle:** Be honest about where code came from. Transparency builds trust.

**The benefit:** Honest disclosure actually improves your reputation (shows you know how to use tools effectively), doesn't hurt it.

## Week One Setup: Honest AI Disclosure

### Day 1: Update Your README

Add a section about AI-assisted development:

```markdown
## How This Was Built

This project was built with AI-assisted development. The architecture,
design decisions, and most code are human-written. AI tools (Claude,
GitHub Copilot) were used for:
- Boilerplate code (tests, config files)
- Code review (linting, type checking)
- Documentation (docstrings, README)
- Refactoring suggestions

All code has been reviewed by humans and tested before shipping.

AI tool usage is part of the GitHub workflow (see .claude/CLAUDE.md for
agent usage guidelines).
```

**Why:**
1. **Honesty:** Readers deserve to know if AI wrote code they're reading
2. **Differentiation:** Shows you can use tools effectively (valuable skill)
3. **Trust:** "They're transparent" → builds credibility, not lost credibility
4. **Future hires:** "This person uses modern tools" is a good signal

### Day 2-3: Set Up Reproducibility

Your goal: someone can reproduce your build, test, and run the code.

```markdown
## Reproducibility

### Requirements
- Python 3.11+
- Dependencies: see requirements.txt
- Expected: tests pass with 100% success rate

### Verifying AI-Assisted Code
To verify that AI-generated code was properly tested:

1. Run tests: `pytest tests/`
2. Check coverage: `coverage report` (must be > 80%)
3. Type check: `mypy --strict src/`

If any step fails, the code is not production-ready.
```

**Include test fixtures:**
- Don't rely on external services
- Use seed data so results are deterministic
- Document: "Run `make test` to verify"

### Day 4: Contribution Guidelines

If others contribute to your project, tell them about AI:

```markdown
## Contributing

### Code Style
- See .claude/CLAUDE.md for guidelines

### Using AI Tools
Contributions with AI assistance are welcome. Please note:
1. All code must pass tests and type checking
2. If you use AI: mention it in the PR description
3. You (the human) are responsible for all code, even if AI wrote it
4. Reviewers assume you understood and vetted every line

Example: "Used Claude to draft the parser; I reviewed and tested."
```

### Day 5-7: Build Your Track Record

This is the long game. Over 3-6 months:

1. **Ship working code:** Users can download and run it
2. **Keep the README honest:** Explain your process
3. **Show test coverage:** "80% coverage" is a good signal
4. **Document edge cases:** Real code documents itself
5. **Respond to issues:** Shows you care about quality

**After 6 months:**
- Portfolio shows: you can ship, you use tools, you write quality code
- Interviewers see: "They used AI effectively, not blindly"
- Reputation: earned, not claimed

## Reproducibility: The Reproducible Artifact

What does reproducibility mean for AI-generated code?

```
Bad: "Here's my code, run it" (might not work, might be different each time)

Good: 
  1. Clear instructions (environment, dependencies)
  2. Seed data + fixtures (not random)
  3. Tests (prove code works)
  4. CI/CD (GitHub Actions runs same tests)
  5. Versioning (can reproduce old versions)
  6. Documentation (explain non-obvious choices)

Example repo structure:
  ├─ README.md (how to build)
  ├─ requirements.txt (dependencies)
  ├─ Makefile (commands: test, build, deploy)
  ├─ tests/ (fixtures, seed data)
  ├─ .github/workflows/ (CI runs tests)
  ├─ .claude/CLAUDE.md (agent guidelines)
  └─ docs/ (architecture, decisions)
```

## Provenance: Document Where Code Came From

For AI-assisted code, be clear about provenance:

```
Ideal: "I wrote this architecture, used Claude to draft the parser,
reviewed and tested it, shipped it."

Not OK: "I don't know if Claude wrote this or me"

Too much detail: Every line attributed to AI
  (Nobody cares about the granular attribution)

Right level: Feature-level attribution
  "Payment processor written by me, heavily reviewed by AI tools"
  "Dockerfile scaffolded by Claude, I tuned for production"
```

**Good practice: Add comments where AI helped significantly**

```python
# Parser logic: scaffolded by Claude, reviewed and tested by hand
# Edge cases: handled based on test failures
def parse_config(text: str) -> Config:
    ...
```

## Licensing: What Happens to AI-Generated Code?

This is a legal gray area, but here's the practical guidance:

```
Your LICENSE (MIT, Apache 2.0, etc.):
  Applies to all code you ship, regardless of origin

Your copyright:
  You own code you ship (even if Claude drafted it)
  You're responsible for ensuring no licensing issues

No need to:
  - List "Claude" as a co-author
  - Add "AI-generated" as a license condition
  - Do anything special legally

Just be:
  - Honest in your README
  - Clear about dependencies (if you use GPL code, mention it)
  - Thoughtful about attribution (if you use OSS heavily, credit them)
```

## Worked Example: Honest AI Disclosure in Action

**Your README (before):**
```markdown
# UserService — Fast user management

Built from scratch, hand-written code, fully tested.
```

**Reality:** You used Claude for 40% of the code (parsing, serialization, tests).

**Your README (honest):**
```markdown
# UserService — Fast user management

Built with human design and AI-assisted development.

## How This Was Built

Core architecture and API design: hand-written.
Parser, serialization, test scaffolding: drafted by Claude, reviewed and tested.
All code passes tests (100% unit coverage) and type checking (mypy --strict).

See .claude/CLAUDE.md for agent usage guidelines and test procedures.
```

**Result after shipping:**
- Recruiter sees: "They use modern tools" (good)
- User sees: "This is well-tested" (good)
- Competitor sees: "They're honest" (good)
- Interviewer asks: "How do you use AI in your workflow?" (can explain clearly)

## Interview Q&A

**Recall 1:** Should you disclose AI-assisted code in your README?
*Must-say:* Yes. Honesty builds trust. Interviewers appreciate transparency and tool fluency.

**Probe 1:** Someone says, "Admitting AI wrote code makes you look lazy." How do you respond?
*Expected:*
- Distinction: "Claude drafted the boilerplate, I wrote the logic and tests"
- Demonstration: ship working code with tests and docs
- Reality: effective tool use is a skill, not laziness

**Probe 2:** Your open-source code has a bug. A user files an issue. Are you responsible?
*Expected:*
- Yes, 100%. You shipped it, you're responsible.
- If AI drafted it: still your responsibility (you reviewed it)
- If you shipped without testing: that's on you

**Scenario 1:** You're building a portfolio project. Should you use AI?
*Expected:*
- Yes, if you learn from it
- Use AI for boilerplate, tests, docs
- You: architecture, hard logic, edge cases
- Result: shipped code is your evidence, not Claude's
- Benefit: interviewers see you can use tools effectively

**Exercise 1:** Write a README "How This Was Built" section for a project. (10 min work)

---

## Checklist

- [ ] README has "How This Was Built" section with honest disclosure
- [ ] Code is reproducible (tests, fixtures, deterministic)
- [ ] Tests pass locally and in CI
- [ ] Type checking passes (mypy/rustc/tsc)
- [ ] .claude/CLAUDE.md documents agent usage
- [ ] CONTRIBUTING.md mentions AI tool use is OK
- [ ] License is clear (MIT/Apache/etc.)
- [ ] Provenance is documented (feature-level, not granular)

## Common Mistakes

1. **Hiding AI use.** "I wrote this entirely" when you didn't. Dishonest, backfires if found out.
2. **Over-disclosing.** "Line 1 by Claude, line 2 by me..." Nobody cares at that level.
3. **No tests.** "Here's my AI-written code" with no evidence it works.
4. **No reproducibility.** "Run it, it works" → doesn't work on someone else's machine.
5. **Blaming AI for bugs.** "Claude wrote this, not my fault." No. You shipped it.

