# Pricing Models & Unit Economics: CAC, LTV, Margins, Expansion Loops

## First Principles: What is Unit Economics?

**Unit economics** describes the cost and revenue of serving a single customer.

**Core equation:**

```
LTV (Lifetime Value) = ARPU (Average Revenue Per User) × Retention (months) - CAC (Customer Acquisition Cost)

Profit per customer = LTV - CAC

If LTV < CAC, you're losing money on each customer (no matter how many you acquire).
If LTV > 3x CAC, you're building a scalable business.
```

**Simple example:**

```
SaaS tool: $50/month subscription

CAC = $500 (cost to acquire: sales + ads + onboarding)
Monthly churn = 5% (customers leave after 20 months on average)

ARPU = $50 (revenue per user per month)
Average customer lifetime = 20 months
Total revenue per customer = $50 × 20 = $1000

LTV = $1000
LTV/CAC ratio = $1000 / $500 = 2.0x

Verdict: Breakeven ratio is 1.0x, profitable ratio is 3.0x+
This is marginal. You need either lower CAC or higher retention.
```

**Why it matters:**

```
Founder A: "We have 1000 customers!"
Founder B: "What's your LTV/CAC?"
Founder A: "...?"

If LTV/CAC < 1.5x, growth is a mistake (every new customer costs more than they earn).
If LTV/CAC > 3x, you can spend to scale.
```

---

## The Problem: Pricing Without Economics

Founders often price by:
- Gut feeling ("$99/month sounds reasonable")
- Competitor pricing ("Our rival charges $50")
- Cost-plus ("Costs $5 to serve, so $15 SRP")

**None of these are wrong, but they don't guarantee profitability.**

Imagine:
```
You charge $99/month for a tool.
Sales person costs $60K/year, closes 1 customer/month.
CAC = $60K / 12 = $5K per customer.

LTV = $99 × 20 months = $1980.
LTV/CAC = 1980 / 5000 = 0.4x

Verdict: You lose $3020 on each customer.
Scaling makes it worse.
```

**The fix:**

Either increase LTV (price higher, improve retention) or decrease CAC (land inbound, use product-led growth).

---

## Pricing Models: Trade-offs

### Model 1: Per-Seat Pricing

```
Formula: Price per user × number of users

Example: $30/user/month

Pros:
  + Easy to understand
  + Revenue scales with customer growth
  + Transparent (customers know what they pay)

Cons:
  - Incentivizes customers to share login (churn risk)
  - Large teams pay more, may self-select out
  - No expansion loop if they reduce headcount

CAC/LTV dynamic:
  Base LTV (day 0): $30/month
  Expansion LTV (if customer grows from 5 to 20 users): additional $450/month
  Risk: customer contracts from 20 to 5 users, revenue drops
```

**When to use:** Developer tools, communication platforms, HR software (natural scaling vector is team size).

---

### Model 2: Usage-Based Pricing

```
Formula: Cost per unit × volume

Example: $0.10 per API call, $1 per GB stored

Pros:
  + Revenue aligns with value (customer success = your success)
  + No seat-count friction (unlimited users)
  + Expansion loop if customer usage grows

Cons:
  - Unpredictable monthly spend (customer frustration)
  - CAC stays high (no land-and-expand)
  - Requires transparent metrics (API, storage, compute)

CAC/LTV dynamic:
  Customer 1: Light user, $100/month × 12 months = $1200 LTV
  Customer 2: Heavy user, $2000/month × 12 months = $24000 LTV
  Same CAC, 20x revenue variance
```

**Example: AWS-style pricing**

```
Data storage: $0.023 per GB/month
Compute: $0.0116 per CPU-hour

Customer usage:
  Month 1: 10 GB = $0.23, 100 CPU-hours = $1.16, total = ~$1.40
  Month 6: 500 GB + 10K CPU-hours = $11.60 + $116 = ~$127.60

LTV sensitivity: usage is unpredictable for long-term planning.
But for customer: pay for only what they use.
```

**When to use:** Infrastructure (AWS, Stripe, Twilio), APIs, storage where usage naturally varies.

---

### Model 3: Fixed Tier Pricing

```
Formula: Fixed price per tier; tiers have feature limits or usage caps

Example:
  Starter: $29/month, 1000 API calls/month
  Growth: $99/month, 50K API calls/month
  Enterprise: $499+/month, unlimited

Pros:
  + Predictable revenue (fixed contracts)
  + Clear expansion path (upgrade to next tier)
  + Discourages over-consumption (usage-based can spiral)

Cons:
  - Customer might be underutilized (paying for features they don't need)
  - Tier boundaries can create friction ("I'm 5% over Starter limits")
  - Requires you to predict customer behavior

CAC/LTV dynamic:
  Base LTV: $29 × 24 months = $696
  Expansion LTV: 40% of customers upgrade to Growth (+$70 × 24 = +$1680)
  Average LTV ≈ $696 + (0.4 × $1680) ≈ $1,368
```

**When to use:** SaaS, developer platforms, or B2B where you can segment by use case.

---

## Diagram: CAC/LTV Axes and Business Viability

```
        High LTV
        ↑
        |
        | [ZONE 1: Scalable]  | [ZONE 2: Premium]
        | LTV/CAC > 3x        | High margin, niche
        | Growth = profit     | growth = selective
        |
        | [ZONE 3: Marginal]  | [ZONE 4: Broken]
        | LTV/CAC 1.5-3x      | LTV/CAC < 1x
        | Possible, risky     | Don't scale
        |________________________
        Low CAC            High CAC →

        Ideal position: High LTV + Low CAC = top-left

        Common mistakes:
        - Zone 4: High CAC + Low LTV (venture-backed, unsustainable)
        - Zone 3: Betting on CAC decline (might not happen)
```

---

## Retention and Churn: The Silent Killer

**Churn is the #1 brake on LTV.**

```
Monthly churn rate (MRR): percentage of customers who leave each month

Example: 100 customers, 5% churn
  Month 1: 100 customers
  Month 2: 95 customers (5 left)
  Month 3: 90 customers (5% of 95 = 4.75)
  Month 12: 54 customers

LTV calculation:
  At 5% churn: average customer lifetime = 20 months
  At 10% churn: average customer lifetime = 10 months

At $100/month price:
  5% churn: LTV = $2000
  10% churn: LTV = $1000

Same price, 2x LTV difference based on retention.
```

**Where does churn come from?**

```
Rule of thumb (typical SaaS):
- Involuntary: 1-2% (failed credit card, company shutdown)
- Voluntary: 3-8% (found better solution, not using it)
- Poor product: 10%+

Target by maturity:
- Startup MVP: < 10% acceptable
- Growth stage: < 5% targeted
- Mature: < 3% expected

[VERIFY: These are industry guidelines; varies by vertical]
```

**Expansion revenue: the fix for churn**

```
If you can get existing customers to spend more, you offset churn:

Model: Per-seat SaaS
  Starting: 100 customers, $1000/month each = $100K MRR
  Churn: 5% monthly = 5 customers lost
  Revenue loss: $5K/month

  Expansion (land-and-expand):
  + 30% of existing customers add 5 new seats/year = extra revenue
  + Each added seat = $200/month (lower than new CAC)
  Result: +$60K/year extra from existing base

  Net: Churn -$60K/year, expansion +$60K/year = net zero, but customer happy
```

**Expansion revenue from upgrades:**

```
Tier system: Starter $29, Growth $99, Enterprise $499

Customer journey:
  Month 0: 100 customers on Starter ($2900/month)
  Month 6: 40 upgrade to Growth (net new: $2800/month + $1160 upgraded = $3,960)
  Year 1: 50% total base on Growth, 10% on Enterprise

Expansion revenue contribution:
  Year 1 growth from upgrades: 60% of new MRR
  (This assumes new CAC accounts for the other 40%)
```

---

## Story Card: The Overpriced Startup

**Setup:** AI email tool for sales teams, $100K seed, 6-month runway.

**Pricing strategy:** $199/month based on competitor pricing.

**Acquisition:** Sales-heavy (founder calls 30 people/month).
  CAC = $2000/customer (salary + time + closes 1/month)

**Customer profile:** Early adopters with 5-person teams.
  Average LTV = $199 × 15 months (projected) = $2,985

**LTV/CAC = $2,985 / $2,000 = 1.49x → Marginal, risky**

**Month 4 reality:**
- 8 customers acquired
- Churn kicks in: 2 customers left (problems with email delivery)
- Revenue: 6 customers × $199 = $1,194/month
- Burn: $18K/month
- Runway: 1 month left

**Root causes:**
1. Pricing too high for product quality
2. CAC too high for this market size
3. Churn too high (product wasn't ready)

**Pivot (Week 20):**
1. Lower price to $99/month to improve LTV retention (customers less price-sensitive to cheap product)
2. Stop sales calls, launch freemium instead (reduce CAC)
3. Focus on product reliability (reduce churn)

**Result (Month 7+):**
- 30 freemium signups
- 8 paying customers
- Churn drops to 2% (product stability improved)
- CAC: $0 (inbound from free trial)
- LTV: $99 × 30 months = $2,970
- LTV/CAC = profitable

**Key:** Better to have 30 customers at a lower price with strong retention than 8 customers at high price with weak retention.

---

## Reasoning Framework: "Is My Unit Economics Viable?"

When you've set a price and know your CAC:

1. **Calculate LTV**
   ```
   LTV = (Monthly Price) × (Average Customer Lifetime in Months)
   
   Average customer lifetime = 1 / Monthly churn rate
   If 5% monthly churn: lifetime = 1 / 0.05 = 20 months
   ```

2. **Calculate LTV/CAC**
   ```
   Ratio = LTV / CAC
   
   < 1.0 = unsustainable
   1.0–1.5 = risky (leverage on churn or CAC reduction)
   1.5–3.0 = marginal (possible, tight margins)
   > 3.0 = scalable (can fund growth with revenue)
   ```

3. **Identify your constraint**
   ```
   If LTV/CAC < 1.5, which lever is broken?
   
   Option A: LTV too low
     - Price higher? (test with customers)
     - Improve retention? (product quality, customer success)
     - Expand per-customer? (land-and-expand, upsell)
   
   Option B: CAC too high
     - Product-led growth? (freemium, self-serve)
     - Reduce sales cost? (inbound instead of outbound)
     - Better targeting? (sell to easier cohorts first)
   ```

4. **Test your assumptions**
   ```
   Never trust Day 1 churn rate. Run for 12 months.
   Never assume CAC stays constant. Track:
     - Sales + marketing budget / customers acquired
     - Separates channel efficiency
   ```

---

## Q&A (Built on Fundamentals)

**Recall 1:** Your product costs $50/month. CAC is $300. What monthly churn rate makes this business sustainable (LTV/CAC > 2)?

*Must-say:*
- LTV > $600 (2x CAC)
- LTV = $50 × (months), so need > 12 months lifetime
- If monthly churn is M%, lifetime = 1/M
- Need: 1/M > 12, so M < 8.3% monthly churn
- Verdict: < 8% churn required; typical SaaS is 5%, so viable

**Probe 1:** A customer signs up on day 1 but doesn't log in after week 1. Retention looks good on day 30, but you realize they're churning at month 3. Why does day-30 retention lie?

*Expected:*
- Day-30 retention captures early-stage users who haven't had time to churn
- You need 90-day or 180-day cohort retention to see true churn
- Signal: if week-2 engagement is zero, month-3 churn is likely
- Metric: measure "day-1, day-7, day-30, day-90" separately per cohort

**Probe 2:** You're trying to lower CAC by switching from sales to freemium. Initial freemium conversion is 2% (100 signups = 2 paying customers). Is this good?

*Expected:*
- Depends on your price and cost of acquiring the free user
- If free user costs $10 (ad spend), CAC = $10 / 0.02 = $500
- If you had sales CAC at $300, this is worse
- But: freemium usually improves LTV (free users stick longer, graduate)
- Verdict: test for 6 months; conversion should improve as product is better understood

**Numeric 1:** You have 100 customers at $100/month. 5% monthly churn. You run a $10K campaign that acquires 10 customers. What's the payback period?

*Working:*
- Base MRR: 100 × $100 = $10K
- Churn loss: 5% × $100 × 100 = $500/month
- New customer MRR: 10 × $100 = $1K/month
- CAC: $10K / 10 = $1K per customer
- Payback: $1K / $100/month = 10 months
- Verdict: If customer lifetime > 10 months, break even; > 30 months, highly profitable

**Numeric 2:** An enterprise customer spends $10K/month. Churn is 10% (12-month lifetime). What's LTV?

*Working:*
- LTV = $10K × 12 months = $120K
- Even with CAC of $30K (enterprise sales), LTV/CAC = 4x
- Highly profitable per customer, but CAC is high, so needs careful growth

---

## Checklist: Unit Economics Validation

- [ ] Defined pricing model (per-seat, usage, tiered, or hybrid)
- [ ] Calculated CAC from actual data or conservative estimate
- [ ] Estimated customer lifetime from churn rate or industry benchmark
- [ ] Calculated LTV and LTV/CAC ratio
- [ ] LTV/CAC > 1.5 (at minimum) for your model to be viable
- [ ] Know which cohort has best LTV/CAC (e.g., "inbound customers retain 2x vs sales")
- [ ] Tracked retention by cohort for at least 90 days
- [ ] Identified expansion/upsell mechanisms (seat growth, tier migration, add-ons)
- [ ] Know your voluntary churn drivers (top 3 reasons customers leave)
- [ ] Have a path to improve LTV/CAC if currently marginal

**Common wrong answers:**
- "I'll lower churn by building more features" → No, retention comes from solving the core problem
- "Enterprise customers have infinite LTV" → No, they churn too; enterprise sales just lowers initial churn
- "More customers = lower CAC" → No, CAC is cost per customer acquired, not total cost
- "My freemium will convert 30% like Slack did" → No, Slack is an outlier [VERIFY: actual conversion rates]
- "I don't need to worry about churn; I'll just acquire more" → This is how startups die

---

## Questions for the Interviewer

- How did your pricing evolve from launch to now?
- What was your Day-1 churn rate vs. steady-state? Why did it change?
- Have you tested price elasticity? (Changed price, measured impact on volume/LTV)
- Where does your highest-LTV customer cohort come from?
- If your LTV/CAC dropped to 1.2x, what would you do first?
