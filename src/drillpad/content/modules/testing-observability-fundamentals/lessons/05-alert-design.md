# Alert Design & On-Call: Automation, Fatigue Prevention

## The Alert Problem

On-call engineer gets paged 50 times per day. 49 false alarms, 1 real issue.

Result: Engineer ignores all alerts (alert fatigue).

Real issue goes unnoticed → downtime.

## Good Alerts vs Bad Alerts

### Bad Alert

```
Alert: "Memory usage > 50%"

Problem: 
  - Fires all the time (high baseline)
  - Often doesn't mean anything (50% ≠ problem)
  - Engineer ignores it (fatigue)
  - Real issue (98% memory) gets missed
```

### Good Alert

```
Alert: "Memory usage > 90% for 5 minutes"

Why good:
  - Only fires when real problem
  - Actionable (memory is actually a problem)
  - Engineer trusts it, investigates
  - Real issues don't go unnoticed
```

## Alert Design Framework

### Step 1: Measure What Matters

Good metrics for alerts:
- Error rate (5xx errors)
- P99 latency (user-facing)
- Database connection pool exhaustion
- Disk free space
- Queue depth (for async work)

Bad metrics for alerts:
- CPU usage (meaningless, varies with workload)
- Memory usage (mostly not a problem)
- Disk I/O (normal variation)

### Step 2: Set Right Thresholds

```
Method 1: Historical data
  - Measure P95 of metric over 30 days
  - Alert at P99 or higher
  
  Example: P99 latency = 200ms
           Alert if P99 > 200ms consistently

Method 2: Industry standard
  - Payment systems: <500ms latency
  - Search: <100ms
  - Analytics: <10 seconds
  
  Example: Use payment industry standard

Method 3: Business impact
  - What latency causes user complaints?
  - Alert just before that threshold
  
  Example: Users complain at 1000ms
           Alert at 800ms (early warning)
```

### Step 3: Avoid False Positives

**Duration requirement:**
```
Alert: "Error rate > 5%"
But: Only fire if true for 5 minutes

Why: Brief spike (1 error out of 20 requests) is normal
     Sustained error rate (5 min) is real problem
```

**Deduplication:**
```
Same alert fires 10 times in 1 minute
Only page engineer once
```

**Context:**
```
Alert: "API latency > 500ms"
But: Check if this is during batch job
     (batch jobs are normal, slow expected)

Add context to alert:
  "API latency > 500ms AND NOT batch_job_running"
```

## Runbooks: How to Fix

Every alert needs a runbook (step-by-step fix guide).

```
Alert: "Database connection pool > 90%"

Runbook:
1. Check: How many connections are active?
   SELECT count(*) FROM pg_stat_activity;
   
2. Check: Are they idle?
   SELECT count(*) FROM pg_stat_activity WHERE state='idle';
   
3. If mostly idle: Reduce pool_max_size (config)
   
4. If mostly active: Is there a slow query?
   SELECT * FROM pg_stat_statements WHERE total_time > 10000;
   
5. If slow query found:
   - Kill it: SELECT pg_terminate_backend(pid)
   - Or: Add index, optimize query
   - Deploy fix
   
6. Monitor: Check pool usage returns to normal
   
7. Post-mortem: Why did pool exhaust?
```

## On-Call Automation

### Rule 1: Don't Page for Known Issues

```
Alert: "API latency high"
But: We're in the middle of planned maintenance

Bad: Page engineer (wakes them up unnecessarily)
Good: Suppress alert during maintenance window
```

### Rule 2: Don't Page if Not Actionable

```
Alert: "Backup job failed"
But: Backup is redundant (daily automatic retry)

Bad: Page engineer at 3am for something that will fix itself
Good: Create ticket, engineer handles in morning
```

### Rule 3: Severity Levels

```
P1 (Page immediately):
  - Authentication down
  - Payments not processing
  - Data loss in progress

P2 (Page during business hours):
  - API latency > SLA
  - Search not working
  - Analytics delayed

P3 (Create ticket, no page):
  - Non-critical service slow
  - Low-impact feature broken
  - Warnings in logs
```

## Interview Pattern: Alert Strategy

```
Q: "You have 100 alerts configured. Engineers ignore 90%.
   How do you fix?"

Weak answer:
  "Remove the ones they ignore"
  (❌ Loses visibility into real issues)

Strong answer:
  "Audit and fix alerts:
  
  1. Categorize:
     - Real issues (engineers page): Keep + improve
     - False alarms (ignore): Remove or fix threshold
     - Unknown (unsure): Investigate
  
  2. For each alert:
     - Is it paging correctly? (P1 worth paging)
     - Is it accurate? (false positive rate < 1%)
     - Is there a runbook? (engineer knows what to do)
  
  3. Fix false alarms:
     - Example: 'CPU > 50%' → Too low threshold
       Fix: 'CPU > 85% for 10 minutes'
     - Example: 'Memory leak detected' → No real metric
       Fix: Use actual memory trend: 'Memory +10MB/hour'
  
  4. Add automation:
     - Auto-recover: Restart service if it crashes
     - Self-healing: Clear old logs if disk full
     - Batch: Don't page for things that fix themselves
  
  5. Runbooks:
     - For each alert: Write 5-minute fix guide
     - Include: diagnosis, common causes, quick fix
     - Update based on real incidents
  
  6. Metrics:
     - Alert fatigue: Track pages-per-day
     - Alert accuracy: Track false-positive rate
     - MTTR: Average time to resolve per alert
  
  7. Process:
     - Monthly: Review alert accuracy
     - Remove alerts with >50% false positive rate
     - Add alerts for recent incidents
  
  Expected result:
    Before: 100 alerts, 90% ignored
    After: 20 alerts, 95% actionable, high trust"

Why this signals good judgment:
  - You understood alert fatigue problem
  - You had systematic approach (audit, fix, measure)
  - You added automation (self-healing)
  - You measured progress (false positive rate, MTTR)
```

## Checklist: Alert Design

- [ ] Each alert has a runbook (step-by-step fix)
- [ ] Alert severity matches impact (P1 = pages)
- [ ] Threshold set to actual problem (not noisy)
- [ ] Duration requirement (avoid brief spikes)
- [ ] Context checked (don't alert during maintenance)
- [ ] False positive rate < 1%
- [ ] Engineer can fix in < 15 minutes
- [ ] Weekly: Track alert accuracy, remove false alarms
- [ ] Monthly: Update runbooks based on real incidents

## Common Alert Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| **Too many alerts** | Alert fatigue, ignored | Audit, remove false positives |
| **No runbook** | Engineer panics, slow fix | Write 5-min fix guide |
| **Wrong threshold** | False positives or misses | Use historical data or business impact |
| **No automation** | Manual fixes at 3am | Auto-recover, self-heal |
| **Severity mismatch** | Non-issues page, real issues don't | Align severity to impact |

## What This Signals

- You've been on-call (experienced alert fatigue)
- You understand severity levels (not all issues are equal)
- You have runbooks for every alert (not just hope)
- You measure alert accuracy (data-driven improvements)
