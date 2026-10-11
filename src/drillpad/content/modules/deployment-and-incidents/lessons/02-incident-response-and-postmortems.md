# Incident Response & Blameless Postmortems

## The Incident Reality

Your system goes down. Pager goes off at 3am.

Two things matter:
1. **Stop the bleeding** (fix it in minutes)
2. **Learn and prevent** (fix the cause forever)

Most teams are good at 1, bad at 2. Postmortems fix that.

## Severity Classification

Not all incidents are equal. Triage by impact.

```
P1 (Page immediately):
  - Service unavailable
  - Data loss happening
  - Security breach active
  - Financial impact
  
  Response: Drop everything, fix now
  Target: < 15 min

P2 (Page, can wait a few hours):
  - Degradation (slower, not down)
  - Partial outage (some users affected)
  - Feature broken
  
  Response: Urgent, but not emergency
  Target: < 1 hour

P3 (Create ticket, fix in next sprint):
  - Single-user impact
  - Non-critical feature
  - Workaround available
  
  Response: Business as usual
  Target: Next sprint
```

## Incident Playbook: What to Do Right Now

### P1 Incident (Service Down)

```
T=0s: Pager alert
  - Who: On-call engineer (you)
  - What: Acknowledge pager (don't snooze)
  - How: Go to incident channel (Slack, war room)

T=1m: Assess situation
  - Is service down? (can you hit the API?)
  - How many users affected? (check monitoring)
  - Is data safe? (check database, backups)
  - Severity: Really P1? (escalate if unsure)

T=5m: Triage
  - Is it infrastructure? (database, network, cloud)
  - Is it code? (recent deployment?)
  - Is it external? (dependency down)

T=10m: Quick fix
  - Revert last deploy (if code issue)
  - Restart service (if frozen)
  - Failover to backup (if infrastructure)
  - Scale up (if overloaded)

T=15m: Check metrics
  - Is service recovering? (latency, errors dropping)
  - Are users happy? (traffic returning to normal)

T=30m: Root cause
  - Why did this happen?
  - Document for postmortem
```

### Incident Commander Role

One person owns the incident (not everyone shouting):

```
Incident Commander:
  - Owns timeline
  - Assigns tasks (database expert, network expert)
  - Makes decisions (revert? rollback? escalate?)
  - Keeps team focused
  - Communicates to leadership

Other roles:
  - Investigator: "What's the root cause?"
  - Fixer: "What's the fix?"
  - Communicator: "Update customers"
  - Logger: "Document everything"
```

## Blameless Postmortem: Learning from Incidents

**Goal:** Prevent it from happening again, not blame someone.

### Postmortem Structure

```
Timeline:
  T=0: Alert triggered (latency >1s)
  T=5: On-call acknowledged
  T=10: Identified database connection pool exhausted
  T=15: Restarted database service
  T=20: Traffic recovered
  T=30: Monitoring metrics normal

Root Cause:
  - New feature added connection pooling bug
  - Under load, connections leaked
  - Pool exhausted after 30 min of traffic
  - Service started rejecting requests

Contributing Factors:
  - No load test before deployment (would have caught it)
  - No alert on connection pool usage >80%
  - Code review missed the leak (leak was subtle)

What Went Well:
  - On-call responded in 5 minutes
  - Identified cause quickly (good logging)
  - Restart fixed it (temporary workaround)

What Could Be Better:
  - Better load testing in staging
  - Alert on connection pool
  - Code review checked for resource leaks

Action Items (Fixes):
  1. Add load test to CI (catch leaks before deploy)
  2. Add alert: connection_pool_usage > 80%
  3. Code review checklist: review for resource leaks
  4. Team training: connection pool best practices

Prevent:
  - Same bug won't happen again (load test, alert)
  - Similar bugs caught earlier (checklist, training)
```

### The Anti-Pattern: Blame

```
WRONG:
  "Engineer deployed without testing, caused outage.
   Punishment: no deployment rights for 1 week."

RIGHT:
  "Bug in deployment made it to production.
   Why? No load test caught it.
   Fix: Add load test to CI.
   Why deploy without testing? Time pressure.
   Fix: Add automatic load test, not manual step."
```

**Blameless means:** Focus on systems, not people.

## Postmortem FAQ

**Q: Who writes it?**
A: The fixer (person who fixed it) or on-call engineer. Owes the learning.

**Q: When?**
A: Within 24 hours while fresh. P1 incidents get postmortem same day.

**Q: Who reads it?**
A: Whole team. Everyone learns from others' incidents.

**Q: What if we don't fix root cause?**
A: Document it. "We can't add load test (time), so accepting risk for now."

**Q: What if we find multiple root causes?**
A: List them all. "Leak + no alert + no test all contributed."

## Interview Pattern: Incident Ownership

```
Q: "You had a major outage last year. Walk me through it."

Weak answer:
  "It was bad, we fixed it quick"
  (❌ No details, no learning)

Strong answer:
  "We had a cascading failure:
  
  1. Timeline:
     - T=0: API latency spiked (P99 = 5s)
     - T=5: Database overloaded (connection pool 95%)
     - T=10: New service crashed (couldn't get connection)
     - T=15: Service restarted, retried connections
     - T=20: Thundering herd (all requests hit once)
     - T=25: Downtime (everything overloaded)
  
  2. Root cause:
     - New service deployed without backoff
     - Each retry retried immediately
     - No exponential backoff = thundering herd
     - Database can't keep up
  
  3. What we fixed:
     a) Immediate: Restart with exponential backoff
     b) Long-term: 
        - Add backoff library to all services
        - Add alert: latency > SLA (catch early)
        - Load test (would have caught before deploy)
        - Code review: check for retry logic
  
  4. Prevention:
     - Same bug won't happen (backoff everywhere)
     - Similar bugs caught (code review, load test)
     - Culture: blameless (focus on systems)
  
  5. Impact:
     - 20 min downtime
     - Learned: exponential backoff is non-negotiable
     - Trained team: all services now have backoff
     - Monitor: alert on latency
  
  6. If it happened again:
     - We'd catch it in load test
     - Or catch with latency alert at 1% slow (before overload)
     - Not the same mistake twice"

Why this signals good judgment:
  - You owned the incident (didn't blame others)
  - You had a root cause (not "just happened")
  - You learned from it (prevented future)
  - You documented it (postmortem culture)
  - You showed resilience (bounced back, improved)
```

## Postmortem Checklist

- [ ] Write within 24 hours
- [ ] Include timeline (when each thing happened)
- [ ] List root causes (not just immediate cause)
- [ ] List contributing factors (conditions that made it worse)
- [ ] Document what went well (celebrate)
- [ ] Document what could be better (learn)
- [ ] Create action items (specific fixes)
- [ ] Assign owners to action items
- [ ] Track completion (actually fix things)
- [ ] Share with whole team (transparency)

## What This Signals

- You've been on-call (experienced incidents)
- You own your mistakes (blameless culture)
- You learn from incidents (not just fix and move on)
- You prevent repeat incidents (long-term thinking)
