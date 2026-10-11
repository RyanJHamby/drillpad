# Playbook: Large Company Teams — Governance, Compliance, Adoption

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Challenge: Large Teams Have Constraints

In a startup, you can use new tools freely. In a large company:
- Security must approve new tools
- Data classification restricts what you can process
- Compliance rules (SOC2, HIPAA, PCI) limit scope
- Multiple teams with different policies
- Legal review takes time

**The trap:** You want to move fast with agents. Company wants to move slow and safely. Both are right.

**The lever:** Propose adoption with a clear governance model that satisfies both.

## Data Classification: What Data Agents Can Touch

Different data has different sensitivity levels. Before agents can work on code, classify the data:

```
Level 0: Public
  Example: marketing website code, open-source repo
  Agents: Full access, no restrictions

Level 1: Internal
  Example: internal tools, non-sensitive business logic
  Agents: Can modify, but no external API calls

Level 2: Confidential
  Example: user-facing code, payment processing
  Agents: Can read only, no modifications without review

Level 3: Restricted
  Example: auth systems, security code, financial calculations
  Agents: Cannot access (read-only in chat, no file access)

Level 4: Secrets
  Example: keys, credentials, PII
  Agents: Never access (block in .gitignore, use dummy values)
```

**For each level, define agent permissions:**

```
Level 0: RWX (read, write, execute, auto-merge)
Level 1: RWX (read, write, execute, human merge)
Level 2: R (read only)
Level 3: Blocked (chat context only, no file system)
Level 4: Blocked (never)
```

**Example classification (fintech):**

```
Code:
  /payment-service → Level 2 (Confidential)
    Agents can read, suggest changes, but must have human review
  /internal-admin → Level 1 (Internal)
    Agents can modify, human merge required
  /README.md → Level 0 (Public)
    Agents can auto-merge doc changes

Data:
  PII (user names, emails) → Level 4 (Secrets)
    Agents never see real data, use test fixtures
  User transaction history → Level 3 (Restricted)
    Agents can read code that accesses it, not the data itself
```

## Compliance: What the Company Cares About

Different companies have different requirements. Find out yours:

```
SOC2 Type II:
  - Audit trail (who changed what, when)
  - Implication: agent commits must be signed/attributed
  - Implication: agent access logged

HIPAA (health data):
  - No patient PII in logs or agent context
  - Implication: agents cannot see patient data
  - Implication: test data must be scrubbed

PCI-DSS (payment card data):
  - No card numbers or auth tokens in code
  - Implication: agents can't modify payment code that touches raw card data
  - Implication: vault/secrets access is blocked

GDPR (EU user data):
  - User data deletion on request
  - Implication: if agents train on user data, that blocks GDPR compliance
  - Implication: only use agents on anonymized data

Your company's custom policy:
  - Example: "No external APIs without InfoSec approval"
  - Implication: agents can't integrate new services
  - Implication: agents can modify code that uses approved services
```

**Action:** Ask your compliance/security team:
- "Which regulations apply to our code?"
- "What are the agent restrictions?"
- Write them down, include in CLAUDE.md

## Week One Setup: Bringing Agents to Your Team

**Goal:** Get agents approved and adopted in a large team without friction.

### Day 1: Get Leadership Buy-In

1. **Pitch:** "We can improve velocity by 20-40% with agent-assisted development."
   - Evidence: your personal benchmarks (lesson 05)
   - Cost: < 5% increase in compute costs
   - Risk: mitigated by verification (CI gates, human review)

2. **Propose pilot:** "Let's start with the internal-tools team (Level 1 data, lowest risk)."

3. **Outcome:** Approval to run a 4-week pilot

### Day 2-3: Set Up Governance

1. **Create CLAUDE.md** for the team (lesson 03)
   - Include data classification
   - Include compliance constraints
   - Include code style, test requirements
   - Include what agents can/cannot do

2. **Define review process** (build on lesson 12 from ai-skills-senior-swe: scaling review meetings)
   - Tier 1 (trivial): auto-merge if tests pass
   - Tier 2 (routine): human review, async
   - Tier 3 (high-risk): named reviewer, sync

3. **Set up audit logging**
   - Agent commits must have attribution
   - Use git signing, or CI logs agent activity
   - Company can audit: "Who made what change, and was it reviewed?"

### Day 4: Onboard First Users

1. **Run a workshop** (60 min):
   - Intro to agents (15 min)
   - Your CLAUDE.md (15 min)
   - How to write specs (15 min)
   - Q&A (15 min)

2. **Assign pilot projects:**
   - Project 1: internal tool (low risk, clear wins)
   - Project 2: test harness (mechanical work, easy wins)
   - Project 3: documentation (safe, visible progress)

3. **Establish check-ins:**
   - Daily standup: any agent blockers?
   - Weekly: review, metrics, blockers

### Day 5-7: Measure and Iterate

1. **Metrics to track:**
   - Time to PR (spec to merge): goal is 50% reduction
   - Code quality: regressions in production?
   - Team velocity: total features shipped?
   - Review time: does agent code get reviewed faster?

2. **First week results:**
   - Goal: ship 3-5 agent-assisted PRs
   - Measure: no production issues
   - Feedback: what worked, what didn't?

3. **Iterate CLAUDE.md:**
   - Based on feedback, tighten or loosen rules
   - Example: "We thought agents couldn't modify payment code, but with strict CI gates, it's safe. Let's expand scope."

## Diagram: Large-Team Rollout

```
Week 1: Setup
  Mon: Leadership pitch
  Tue-Wed: Governance (CLAUDE.md, review tiers, audit logging)
  Thu: Onboard pilots
  Fri: First agents start work

Week 2-4: Pilot (internal-tools team)
  ├─ Run agents on low-risk tasks
  ├─ Measure: velocity, quality, time-to-merge
  └─ Weekly check-ins

Week 5: Evaluate
  ├─ Results: 25% velocity increase, no regressions
  ├─ Team feedback: "Agents are great for boilerplate"
  └─ Decision: expand to another team

Week 6+: Expand
  ├─ Onboard api-server team (higher risk, but proven model)
  ├─ Continue governance, measure
  └─ Iterate based on learnings
```

## Proposing Adoption Without Friction

**The pitch (to manager/leadership):**

```
"We can increase velocity by 20-40% with agent-assisted development.
We've run a personal benchmark [show evidence].
We propose a 4-week pilot with the internal-tools team.
Risks are mitigated by [data classification, CI gates, review process].
Cost: < $1000/month in compute.
Success metric: 30% reduction in time-to-merge for pilot tasks."
```

**The governance document (for company):**

```markdown
# Agent Usage Governance

## Scope
Agents are approved for:
  ✓ Internal tools (Level 1 data)
  ✓ Test code
  ✓ Documentation
  ✗ Payment code (Level 2, restricted)
  ✗ Auth/secrets (Level 3, never)

## Controls
  - All commits are signed and attributed
  - All PRs have human review before merge
  - Tier 3 PRs (high-risk) require 2 reviewers
  - Audit: git log shows agent + reviewer names

## Metrics
  - Time-to-merge (goal: 50% reduction)
  - Code quality (zero new production regressions)
  - Team satisfaction (survey after 4 weeks)

## Review
  - Week 4: evaluate results
  - Month 2: expand scope if successful
```

## Interview Q&A

**Recall 1:** What are the 5 levels of data classification?
*Must-say:* Public, Internal, Confidential, Restricted, Secrets.

**Probe 1:** Your company is HIPAA-regulated. Can agents modify code that processes patient data?
*Expected:*
- No, agents cannot access patient data
- Agents can modify code that uses data, but only with test fixtures (no real PII)
- Compliance constraint: de-identification required

**Probe 2:** You want to propose agents to your manager. What's the one metric that will get approval?
*Expected:*
- Velocity improvement (time-to-merge reduction), backed by evidence
- Cost is low (<  5% increase)
- Risk is mitigated (CI gates, review process, pilot scope)

**Scenario 1:** Your company blocks external APIs. Can agents integrate a new service?
*Expected:*
- Agents cannot approve new services (not their decision)
- Agents can modify code that uses approved services
- To use a new service: get security approval, add to approved list, then agents can modify

**Exercise 1:** Create a governance document for your team. (15 min work)

---

## Checklist

- [ ] Classified your codebase by data sensitivity level
- [ ] Listed compliance constraints (SOC2, HIPAA, PCI, etc.)
- [ ] Created CLAUDE.md with agent permissions
- [ ] Defined review tiers (Tier 1-3)
- [ ] Set up audit logging (commits signed/attributed)
- [ ] Pitched to leadership with evidence
- [ ] Defined pilot scope (which team, which code)
- [ ] Scheduled week-one onboarding

## Common Mistakes

1. **Over-classifying data.** "Everything is confidential, agents can't touch anything." → Agents never get to help.
2. **No governance document.** Company distrusts what agents can do, blocks adoption.
3. **Pilot is too ambitious.** Starting with payment code (Level 2) instead of internal tools (Level 1).
4. **No metrics.** Can't prove agents are working, hard to expand scope.
5. **Not getting compliance buy-in early.** Build governance with security/compliance, not against them.

