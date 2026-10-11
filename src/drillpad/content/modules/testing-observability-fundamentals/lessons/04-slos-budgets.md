# SLOs, SLIs & Error Budgets: Defining Success

## Definitions

**SLI (Service Level Indicator):** Measured metric

Example: "99% of requests have latency < 100ms"

**SLO (Service Level Objective):** Target for the SLI

Example: "We commit to 99.9% availability"

**SLA (Service Level Agreement):** Contract with penalty

Example: "We guarantee 99.9% uptime, or you get $100 credit"

## Setting SLOs: The Right Level

Too strict: "100% uptime" → impossible, team burns out
Too loose: "90% uptime" → users get poor experience

### Rule of Thumb

```
99.0% uptime   = 3 days downtime per year    (uncommon)
99.9% uptime   = 9 hours downtime per year   (moderate)
99.95% uptime  = 4.5 hours downtime per year (strict)
99.99% uptime  = 52 minutes downtime per year (very strict)
```

### Choose by Impact

| Service | SLO | Reason |
|---|---|---|
| **Authentication** | 99.99% | If down, everything fails |
| **Core API** | 99.9% | Users can't access features |
| **Analytics** | 99.0% | Nice to have, not critical |
| **Search** | 99.9% | Users expect fast search |

## Error Budget: How Much Can You Break?

Error budget = (1 - SLO) * time period

```
SLO: 99.9% (0.1% allowed failures)
Month: 30 days = 2,592,000 seconds

Error budget = 0.001 * 2,592,000 = 2,592 seconds = 43 minutes

Team can afford 43 minutes of downtime this month.
```

### Error Budget Consumption

```
Week 1: Outage = 30 minutes
  Remaining budget: 43 - 30 = 13 minutes

Week 2: Deploy bug = 10 minutes  
  Remaining budget: 13 - 10 = 3 minutes

Week 3: Risky experiment (not allowed)
  Why? No budget left. Too risky.
```

### Budget Policies

**Strict (low risk tolerance):**
- Can't deploy if < 20% budget remaining
- All deploys require change advisory board approval
- Risky experiments forbidden

**Relaxed (high risk tolerance):**
- Can deploy if > 1% budget remaining
- Self-serve deployments
- Experiments encouraged

## SLI Examples

### Availability

```
Requests succeeded / Total requests
99.9% = 1 failure per 1000 requests
```

### Latency

```
Requests with latency < 100ms / Total requests
95% of requests must be < 100ms
```

### Error Rate

```
Non-5xx errors / Total requests
99% = < 1% errors per 1000 requests
```

## Monitoring SLOs

### SLO Tracking Dashboard

```
SLO: 99.9% availability (43 minutes budget)

Current month: 99.8% (61 minutes downtime)
Status: OVER BUDGET (used 61, allowed 43)

Budget exhausted? YES
Deployments allowed? NO
Risky experiments? NO
```

### Automated Alerts

```
Alert: "SLO at risk"
  Condition: Remaining budget < 5 minutes
  Action: Freeze deployments, investigate
  
Alert: "SLO violated"
  Condition: Monthly SLO < target
  Action: Post-mortem, adjust practices
```

## Interview Pattern: SLO Definition

```
Q: "Define SLOs for a payment system."

Weak answer:
  "99.99% uptime"
  (❌ No details, might be wrong level)

Strong answer:
  "Multi-tier SLOs:
  
  1. Authentication (critical):
     SLO: 99.99% availability (5 min downtime/month)
     Why: If auth is down, no transactions possible
     
  2. Payment API (core):
     SLO: 99.95% availability (22 min downtime/month)
     Why: Money is at stake, but brief outages acceptable
     
  3. Latency (core):
     SLO: P99 latency < 500ms
     Why: User expects sub-second payment feedback
     
  4. Error rate (core):
     SLO: < 0.1% errors (not user mistakes, system errors)
     Why: Trust is key in payments
  
  5. Error budget allocation:
     Authentication: 5 min/month
       - Deploy carefully (high risk = low budget)
       - No experiments
     
     Payment API: 22 min/month
       - Can afford some incidents
       - Test new features, learn fast
     
     Latency: Budget = time queries > 500ms
       - Trade off features vs speed
       - Optimize expensive queries first
  
  6. Monitoring:
     - Real-time SLO tracking dashboard
     - Alert if budget running low
     - Freeze deployments if budget exhausted
  
  7. Improvement:
     - Monthly post-mortem (what caused downtime?)
     - Tighten SLO if consistently beating it
     - Loosen SLO if impossible to hit (reset expectations)"

Why this signals good judgment:
  - You matched SLO to criticality
  - You calculated error budget
  - You had a deployment policy (based on budget)
  - You'd monitor progress
```

## Common SLO Mistakes

| Mistake | Impact | Fix |
|---|---|---|
| **SLO too strict** | Team can't ship features | Relax SLO |
| **SLO too loose** | Users unhappy | Tighten SLO |
| **No error budget** | Team risk-averse | Calculate budget, use it |
| **No monitoring** | Don't know if you're meeting SLO | Add dashboard + alerts |
| **Conflicting SLOs** | Latency vs Throughput tradeoff | Choose one priority |

## SLO Tiers (Realistic)

```
Tier 1 (Must-have): 99.9% (9 hours/year downtime)
Tier 2 (Should-have): 99.5% (44 hours/year downtime)
Tier 3 (Nice-to-have): 99.0% (88 hours/year downtime)

Don't try to hit Tier 1 for everything.
Choose strategically per component.
```

## What This Signals

- You understand SLO is about commitments (not just metrics)
- You allocate error budget strategically
- You use error budget to guide deployment policy
- You monitor progress (not just launch and forget)
