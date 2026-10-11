# Customer Discovery & Validation: Problem/Solution Fit Before MVP

## First Principles: What is Problem/Solution Fit?

**Problem/solution fit** is the state where:
1. You've identified a **specific, painful problem** that:
   - Real customers face (not invented)
   - They're willing to pay to solve
   - You can solve better than alternatives
2. You've found a **minimum viable solution** that:
   - Solves that problem (not scope-creep)
   - Customers will use (not sit idle)
   - You can build in weeks, not months

**Why it matters:** Building something nobody wants is the #1 startup failure. Before writing code, talk to customers.

**The startup death sequence:**
```
Bad customer discovery
  → Build the wrong thing
    → Spend 6 months on features nobody uses
      → Run out of runway
        → Team disperses
```

**Successful path:**
```
Talk to 10 potential customers
  → Identify problem they mention unprompted 3+ times
    → Test whether they'd pay
      → Design MVP (NOT full product)
        → Build & measure
```

---

## The Problem: The "Build in Silence" Trap

Founders often skip customer discovery because:
- Fear of stealing the idea (it won't be)
- Confidence the idea is good (it might not be)
- Rushing to code (fastest way to fail faster)
- Not knowing how to talk to customers (fixable)

**What happens without discovery:**
- You build features customers don't care about
- You optimize for the wrong metric
- You discover problems months in, when pivoting costs runway
- Investors see no customer evidence

**Cost of delay:**
```
Timeline impact:

Scenario A: 4 weeks discovery → 12 weeks MVP → launch with traction
  Result: More likely to raise / acquire

Scenario B: 0 weeks discovery → 16 weeks "perfect" MVP → cold launch
  Result: No customers → pivot or die
```

The paradox: **Starting faster means talking to customers first, not skipping to code.**

---

## Discovery: Three Phases

### Phase 1: Problem Validation (Weeks 1–2)

**Goal:** Talk to 10–15 people with the problem. Confirm it's real and painful.

**What counts as validation:**
- Customer mentions the problem unprompted (don't lead them)
- They describe workarounds they're using today
- They'd prefer your solution if it existed
- They won't take a free version if it doesn't solve it

**What doesn't count:**
- "That's a cool idea" (meaningless)
- Hypothetical interest ("I'd use it if...")
- Your friends saying you're smart (survivorship bias)

**Diagram: The Discovery Funnel**

```
100 potential customers identified
  ↓
50 agree to a conversation
  ↓
30 describe the problem unprompted
  ↓
15 say they'd pay something to solve it
  ↓
5–8 become early customers

Each layer is a filter for real demand.
```

**Process:**
1. Find people with the problem (LinkedIn, Reddit, industry forums, referrals)
2. Ask open-ended questions:
   - "What's your biggest frustration with [domain]?"
   - "How do you solve this today?"
   - "Would you pay for a tool that did X?"
3. Listen, don't pitch
4. Take notes on exact words (quotes matter)

**Red flags:**
- "I don't have that problem, but someone else might"
- Vague endorsement ("sounds good")
- They have no current workaround (problem isn't real enough)
- They won't name a price (not serious)

---

### Phase 2: Solution Validation (Weeks 2–4)

**Goal:** Show a mockup or MVP. Do they want it enough to commit time or money?

**Solution concepts to test:**
- Wireframes (on paper or Figma)
- Video walkthrough
- Landing page with signup (conversion = interest)
- Prototype of key flow (Retool, Webflow, no-code)
- Minimum marketable feature (first 1–2 features only)

**Validation signals:**
- "I'd use that immediately"
- They offer to help test / provide data
- They ask about pricing (sign they're serious)
- They suggest features but acknowledge MVP is okay
- They commit: "Put me on the waiting list" + email

**Sample conversation:**
```
You: "Here's a mockup. After you organize reports, how would you use the results?"
Customer: "I'd export to a spreadsheet, then..."
You: "What if I added that export for you?"
Customer: "Then I'd save 2 hours every Monday"
You: "Would you pay $50/month for that?"
Customer: "I'd pay $200/month; it costs me $1000 in lost time"
```

That's strong signal.

**Diagram: Idea vs Reality**

```
Your theory:        "Busy engineers need a reporting tool"
  ↓
Customer reality:   "I copy reports 5x/week, error-prone, boss asks for
                     custom cuts I can't do fast"
  ↓
Solution fit:       "Auto-fetch reports + one-click custom filters"
                    (NOT: "AI-powered universal analytics platform")
  ↓
MVP scope:          "Manual report list + one filter + email"
                    (NOT: ML recommendations, collaboration, API)
```

---

### Phase 3: MVP Scope Definition (Weeks 4–6)

**Goal:** Define the smallest set of features that solve the core problem.

**Anti-pattern: Feature creep**
```
Day 1: "We'll build reports + export"
Day 10: "And dashboards, real-time alerts, and collaboration"
Day 30: "And integrations with 5 tools and custom branding"
Result: 6 months, no launch, money runs out
```

**MVP principle:**
- One core job: does one thing well
- Metrics: define how you'll measure success
- Scope: 4–8 weeks to launch (not "feature complete")

**Template:**

```
Core job: "Managers can see team bandwidth in one place"

Features (MVP):
  ✓ Calendar sync from Google Calendar
  ✓ Team view (list of people + hours available)
  ✓ Export to CSV
  ✓ Invite teammates

Features (NOT in MVP):
  ✗ Slack integration
  ✗ AI recommendations
  ✗ Forecasting
  ✗ Custom reports
  ✗ Mobile app

Success metric:
  "10 teams sign up, each person logs in 2x/week, 60% retention at day 30"

Launch timeline: 6 weeks
```

**Scope boundary decision:**

```
Feature request: "Can you integrate with Jira?"

Decision tree:
  Q: Is this core to solving the problem?
    NO → Don't do it in MVP
  Q: Would > 50% of customers not use it without this?
    NO → Don't do it in MVP
  Q: Is it < 1 day of work?
    NO → Don't do it in MVP

If all NOs → Save for v1.1
If any YES → Include only if it unblocks core feature
```

---

## Story Card: The Pivoted Expense Tool

**Setup:** Team of 2 founders, $50K runway, 12 weeks to raise or die.

**Hypothesis:** Employees waste time filling out expense reports. We'll build an AI expense reporter.

**Initial discovery (skipped):**
- Built for 8 weeks
- Fancy ML receipt scanning, multi-currency, policy engine
- Launched to crickets: 0 signups

**Post-mortem discovery:**
- Talked to finance teams (not employees)
- "We don't care how fast people fill forms. We care about approvals taking weeks."
- Real problem: expense reports stuck in limbo, CFO has no visibility

**Pivot:**
- New MVP: drag-and-drop approval workflow + spend dashboard
- No fancy scanning (let people paste amounts)
- One week to launch

**Result:**
- 3 warm intros: all signed up
- $1K/month MRR in week 2
- Raised $500K seed 6 months later

**Key:** The first 8 weeks were wasted because they didn't talk to customers first. The pivot would have been obvious in week 1 interviews.

---

## Reasoning Framework: "Do I Have Real Demand?"

When you think you have a product idea:

1. **Name 3 specific people with this problem**
   - Not "companies with big budgets"
   - Not "technical users"
   - Named individuals: "Sarah at Acme, VP of Ops, frustrated with X"

2. **Have you talked to them?**
   - If no: do it immediately
   - If yes: did they mention the problem unprompted?
     - If no: they don't feel the pain enough

3. **Would they pay?**
   - Ask directly: "Would you pay $X?"
   - Their answer: $0–$500/month is signal of true pain
   - If they won't name a price: they're not serious

4. **Can you solve it in 4–8 weeks?**
   - If not: either problem is too big or your solution is overcomplicated
   - Strip scope until yes

5. **Launch or iterate:**
   - Go build and measure
   - Week 1: 0 customers expected
   - Week 4: should have 5–10 early users
   - If not: wrong problem or wrong solution

---

## Q&A (Built on Fundamentals)

**Recall 1:** What's the difference between a solution customers will "try" vs. "pay for"?

*Must-say:*
- "Try" = curiosity, low commitment
- "Pay for" = they've quantified the problem cost and believe you'll solve it
- Signal: "Yes, I'd pay $X/month starting next month" is real
- Red flag: "Sounds interesting" is not

**Probe 1:** You talk to 10 potential customers. 8 say "cool idea," 2 say "I'd use it." Which signal matters more?

*Expected:*
- The 2 matter
- The 8 are polite, not customers
- Actionable feedback: ask the 2 what job they need done

**Probe 2:** A customer says, "I don't have this problem, but I know someone who does." Is that a qualified lead?

*Expected:*
- No. Second-hand problem reports are weak signal.
- Your job: find the person with the problem directly
- Why: problem isn't urgent enough for them to connect you, or they don't actually know the person well

**Numeric 1:** You have 12 weeks of runway ($50K) and a team of 2. You spend 4 weeks on discovery and launch with 8 qualified customers. What's your next move?

*Working:*
- 8 customers, assume $1K–$5K/month each = $8K–$40K MRR
- At $20K MRR, you're 2.5x burn rate
- You can survive and grow, or raise
- Comparison: launch with 0 customers after 12 weeks = $0 MRR = dead
- Decision: 4 weeks discovery is an investment, not a cost

**Numeric 2:** You talk to 30 people. 12 say they have the problem. Of those 12, 4 would pay. What's your confidence level?

*Working:*
- 40% problem validation (12 of 30) is moderate
- 33% willingness to pay (4 of 12) is concerning
- Combined: 13% of total addressable market engaged
- Signal: might be niche, or solution isn't clear
- Next: dig deeper with the 4 (what would make 8 of 12 pay?)

---

## Checklist: Am I Ready to Build?

- [ ] Named 3+ specific people with the problem (not generic segments)
- [ ] Talked to 10+ people; 5+ mentioned problem unprompted
- [ ] At least 2 said they'd pay for a solution
- [ ] Showed mockup or explained solution to 5+ customers; 3+ wanted to try
- [ ] Defined MVP scope in 1 sentence (e.g., "Approval workflow + dashboard")
- [ ] MVP has ≤ 5 core features
- [ ] Can build MVP in 4–8 weeks with current team
- [ ] Have metrics to measure success (e.g., "10 teams, 60% day-30 retention")
- [ ] Have a waiting list or pilot customers (not cold launch)
- [ ] Understand why existing solutions don't work (not feature gaps)

**Common wrong answers:**
- "My idea is too good to share; I'll stay stealth" → No, talk to customers
- "I'll perfect the product first, then get feedback" → No, feedback first
- "Investors will fund the idea alone" → No, without users you have just a guess
- "Market research is a waste of time" → It's the highest-ROI activity you can do
- "I know my target better than they know themselves" → No, ask them

---

## Questions for the Interviewer

- How did you identify your first 10 customers?
- What was the gap between your initial hypothesis and what customers actually wanted?
- How did you decide what to leave out of MVP 1?
- Have you had to pivot based on discovery? Walk me through that.
- How do you keep discovery conversations from becoming feature requests?
