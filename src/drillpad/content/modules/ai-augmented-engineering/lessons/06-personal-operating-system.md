# Personal Operating System: Capture, Weekly Review, Triage, Async Queuing

Drafted: 2026-10-11 (not yet verified; replace with "Last verified: YYYY-MM-DD" after checking against sources)

## The Problem: AI Agents Accelerate Context Switching

Before agents: You work on one task, context switches cost time.
- Start task: 10 min ramp-up
- Work: 30 min
- Switch: 10 min lost productivity
- Next task: 10 min ramp-up
- Result: High cost of switching, so you batch tasks

After agents: Agents can work on tasks while you do something else.
- You start task A with agent (no wait needed)
- You start task B with agent (parallel work)
- You answer questions from agents (short interrupts)
- Context switches are now constant, unpredictable

**Problem:** Constant interrupts destroy deep work. You need a **personal operating system** to manage the flow.

## The Capture System: From Interrupt to Queue

Every new task, question, or idea should go into a **capture system**. Don't start it immediately. Capture and triage later.

```
Interrupt arrives (Slack, email, brain):
  "Can you fix the payment bug?"
  
Your response (while in deep work):
  "Captured. I'll prioritize it in my review."
  
Capture → Task list/queue (not starting immediately)
  ↓
Weekly review (Friday afternoon):
  "Triage and queue for next week"
  ↓
Monday: Work through prioritized queue
  "This week: payment bug (P1), feature X (P2), refactoring (P3)"
```

**Tools for capture:**
- Markdown file: `~/todo.md` (simplest)
- Note app (Obsidian, Notion)
- Issue tracker (GitHub Issues, Linear)
- Task manager (Todoist, Asana)

**Key property:** Capture is quick (< 30 sec). You write 1 line, not a detailed spec.

```
✓ "Fix payment bug — user can't refund orders"
✗ "Payment bug: User reports that when they try to refund an order,
   the system returns a 500 error. This affects ~0.1% of users..."
   (Too detailed, breaks capture flow)
```

## The Weekly Review: Triage and Queue Work

Once a week (Friday afternoon, 30 min):

1. **Inbox zero:** Move all new items into backlog
   - New issues from alerts
   - Slack DMs asking for work
   - Brain dumps of ideas
   → Move to backlog

2. **Prioritize:**
   - P0: Breaks production, or was promised
   - P1: Important, ship this week
   - P2: Nice to have, can defer
   - P3: Backlog (may never do)

3. **Estimate:**
   - Quick (< 30 min, can do in a flow session)
   - Medium (30 min–2 hr, batch with others)
   - Slow (> 2 hr, might split into subtasks)

4. **Queue for agents:**
   - Which of these can agents do?
   - Which must you do?
   - Which are blocked on others?

5. **Plan:**
   - Monday-Thursday: agent tasks (they work in parallel)
   - Friday: review their work, catch-up on manual tasks

## Diagram: Interrupt → Capture → Triage → Queue → Execute

```
┌──────────────────────────────────────────────────┐
│ Daily: New interrupts arrive                    │
│ ├─ Slack: "Can you review this?"               │
│ ├─ Email: "We need a feature for X"            │
│ ├─ Brain: "I should refactor that module"      │
└──────────────────────────────────────────────────┘
              │
              ↓ (1 line each, quick capture)
┌──────────────────────────────────────────────────┐
│ Weekly review (Friday 2pm, 30 min)              │
│ ├─ Inbox: [6 new items]                        │
│ ├─ Backlog: [40 items]                         │
│ ├─ Priority: P0 (1), P1 (5), P2 (20), P3 (20) │
│ ├─ Estimate: Quick (3), Medium (2), Slow (1)  │
│ └─ Queue: [Tasks for next week]                │
└──────────────────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────────────────┐
│ Monday-Thursday: Execute queue                  │
│ ├─ Agent task 1 (start Monday)                 │
│ ├─ Agent task 2 (start Tuesday)                │
│ ├─ Your deep work (protected block, 10am-12pm)│
│ └─ Answer agent questions (15 min blocks, 2pm)│
└──────────────────────────────────────────────────┘
              │
              ↓
┌──────────────────────────────────────────────────┐
│ Friday: Review and wrap                         │
│ ├─ Review agent PR output                      │
│ ├─ Merge good work                             │
│ └─ Capture new items for next week             │
└──────────────────────────────────────────────────┘
```

## Context Switching: Protecting Your Deep Work

Agents make interrupt management critical.

**Without management:**
- Agent asks question → you context switch → 10 min lost
- 5 agents asking questions per day → 50 min lost per day
- Week: 4 hours of lost productivity

**With management:**
- Queue: "Agent questions answered 2pm daily"
- Agents: wait for 2pm (< 1 hour wait)
- You: protected deep work 10am-12pm (no interrupts)
- Loss: 0 min (batched context switches)

**Calendar blocking:**

```
Monday:
  9am-10am: Review/plan (check agent status)
  10am-12pm: Deep work (email/Slack off, do not disturb)
  12pm-1pm: Lunch
  1pm-2pm: Meetings/admin
  2pm-3pm: Answer agent questions, review PR
  3pm-5pm: Deep work

Tuesday-Thursday: Same pattern

Friday:
  9am-11am: Review all agent work
  11am-12pm: Merge/cleanup
  12pm-1pm: Lunch
  1pm-3pm: Weekly review + triage
  3pm-5pm: Wrap up + plan for next week
```

## Knowledge Base: Capture Decisions

Every decision you make becomes institutional knowledge. Agents will repeat your decisions (good and bad).

**Keep a DECISIONS.md file in your project:**

```markdown
# Decisions Made

## 2026-10-01: Why we use Redis, not Memcached
- Reason: persistence (Memcached loses data on restart)
- Implication: agent tasks should use Redis, not propose Memcached

## 2026-09-28: Why we don't use ORM in this project
- Reason: low-level control over queries (N+1 detection)
- Implication: agents writing database code should write raw SQL, not ORM

## 2026-09-15: Why we use async/await, not threading
- Reason: GIL contention, easier reasoning
- Implication: concurrency should use asyncio
```

**Agents read this and make better decisions.**

## Worked Example: Unmanaged vs. Managed

**Unmanaged workflow:**

Monday 9am:
- You're in deep work (designing a new API)
- Agent A asks: "Should I add error handling to the logging module?"
- You context switch, answer (5 min)
- Back to design (10 min ramp-up)

Monday 10am:
- Agent B asks: "What format for the cache key?"
- Context switch again (5 min)
- Ramp-up (10 min)

Monday 11am:
- Agent C: question (5 min + 10 min ramp-up)

Monday 12pm:
- Agent D: question (5 min + 10 min ramp-up)

Result: You've been interrupted 4 times. 40 min lost to context switches. 2 hours of deep work done (instead of 4).

**Managed workflow:**

Monday 9am:
- You: "All agent questions queued until 2pm."
- You do deep work 9am-12pm (uninterrupted)
- Agents wait for 2pm feedback

Monday 2pm:
- 30 min: Answer all queued questions (1 context switch)
- Agents get feedback, can continue work

Result: 1 context switch (not 4). 10 min lost (not 40). 4 hours of deep work done. 5x more productive.

## Interview Q&A

**Recall 1:** What's the capture system, and why is speed important?
*Must-say:* Capture is writing down new tasks/ideas quickly (< 30 sec) so you don't lose them and don't start them immediately. Speed matters because context switching is costly.

**Probe 1:** How often should you do a weekly review?
*Expected:*
- Once a week is the minimum (usually Friday)
- More frequent (daily triage) works, but weekly is the baseline
- If you skip it, backlog grows, priorities drift

**Probe 2:** An agent asks you a question. You're in deep work. What's your response?
*Expected:*
- Not: drop everything and answer (context switch)
- Not: ignore the agent (leaves them blocked)
- Answer: "Captured. I'll answer at 2pm along with other Qs."
- This is deferral, not avoidance (you will answer, just scheduled)

**Scenario 1:** You have 15 tasks in your queue. How do you decide which ones to give to agents?
*Expected:*
- Quick, mechanical tasks (add logging, update config): agents
- Strategic decisions (architecture, design): you
- Exploratory work (new technology): you
- Routine work (refactoring, tests): agents

**Exercise 1:** Create a weekly review template for your workflow. (10 min work)

---

## Checklist

- [ ] Have a capture system (file, app, or tracker)
- [ ] Do a weekly review (Friday, 30 min minimum)
- [ ] Have calendar blocks for deep work (protected time)
- [ ] Have a scheduled time for agent questions (e.g., 2pm daily)
- [ ] Have a DECISIONS.md or similar (institutional knowledge)
- [ ] Know how to defer interrupts gracefully ("I'll review this at 2pm")

## Common Mistakes

1. **No capture system.** Ideas/tasks stay in your head, you lose them.
2. **Starting tasks immediately.** Every interrupt becomes top priority, no batching.
3. **No deep work protection.** Available for every agent question, can't focus.
4. **Weekly review done, but no triage.** Backlog grows unbounded, priorities are unclear.
5. **Not sharing decisions.** Agents (and future you) repeat the same decision-making.

