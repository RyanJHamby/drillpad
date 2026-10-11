# AI-Specific Unit Economics: Token Costs, Latency, Margin Constraints

## First Principles: Why AI Unit Economics are Different

**Traditional SaaS:**
```
Price: $100/month
Hosting cost: $5/month
Margin: 95%
Scaling: double customers = double revenue, same hosting cost
```

**AI SaaS:**
```
Price: $100/month
API costs (LLM queries): $30–$60/month per customer (variable!)
Hosting: $5/month
Margin: 35–70% (but variable based on usage)
Scaling: double customers = double API costs (linear with usage)
```

**The core problem:**

```
Your revenue comes from subscriptions (fixed monthly).
Your costs come from API calls (variable, per request).

Mismatch: If customer makes 10x more requests than expected → margin collapses.
```

**Why this matters:**

```
Company A: $99/month SaaS tool
  Customer makes 100 requests/month
  Cost per request: $0.50 (using GPT-4)
  Total API cost: $50/month per customer
  Margin: ($99 - $50) / $99 = 49%

Company B: Same tool, customer makes 1000 requests/month
  Total API cost: $500/month per customer
  Margin: ($99 - $500) / $99 = -405% (losing $400/month)
```

**The cliff:** If you price for average usage but customers use heavily, you lose money.

---

## Token Costs: The Variable Cost Structure

**What are tokens?**

LLM tokens are the units of text the model processes. Pricing is per 1000 tokens (k).

```
OpenAI pricing (as of 2024) [VERIFY: check latest]:
  GPT-4 (turbo): $0.01/1K input, $0.03/1K output
  GPT-3.5: $0.0005/1K input, $0.0015/1K output
  Claude 3 (Haiku): $0.25/1M input, $0.75/1M output
  Claude 3 (Opus): $15/1M input, $45/1M output

Comparison:
  Haiku: $0.00025 per input token, $0.00075 per output token
  GPT-4: $0.01 per input token, $0.03 per output token
  GPT-4 is 40–50x more expensive than Haiku
```

**How many tokens in a typical request?**

```
Example: Customer asks "Summarize this article"
  Input: article (500 words) + prompt (50 words) ≈ 700 tokens
  Output: summary (100 words) ≈ 150 tokens
  Total: 850 tokens

Cost per request:
  Using GPT-3.5: (700 * $0.0005) + (150 * $0.0015) = $0.35 + $0.225 = $0.575
  Using GPT-4: (700 * $0.01) + (150 * $0.03) = $7 + $4.50 = $11.50
  Using Haiku: (700 * $0.00025) + (150 * $0.00075) = $0.175 + $0.1125 = $0.2875

40x cost difference based on model choice.
```

**Diagram: Token Cost vs. Quality Trade-off**

```
Quality / Accuracy
       ↑
       | GPT-4 (best quality)
       | ├─ 40x cost vs Haiku
       | ├─ Use for: complex reasoning, high-stakes
       | │
       | Claude Opus (high quality)
       | ├─ 15x cost vs Haiku
       | ├─ Use for: nuanced tasks, code gen
       | │
       | GPT-3.5, Claude Sonnet (good quality)
       | ├─ 3–5x cost vs Haiku
       | ├─ Use for: most customer-facing
       | │
       | Claude Haiku (fast, cheap)
       | ├─ Use for: high-volume, low-stakes
       | │
       | Fine-tuned small models (cheapest)
       | ├─ $0.0001 per token (estimated)
       | ├─ Use for: specific domains (own trained model)
       |____________
       Low cost              High cost →

Your job: Find the lowest quality model that solves the problem.
If you can use Haiku instead of GPT-4, you save 40x on that request.
```

---

## The Margin Cliff: When Usage Exceeds Pricing

**Scenario: Subscription pricing with variable usage**

```
Product: Email writing assistant
Pricing: $20/month (unlimited requests)

Cost structure:
  Using Claude Sonnet: ~$0.005 per email
  Hosting: $0.50/month per customer
  Total fixed + variable: $0.50 + (usage * $0.005)

Customer profiles:
  Light user: 10 emails/month → Cost $0.50 + $0.05 = $0.55 → Margin: 97%
  Heavy user: 500 emails/month → Cost $0.50 + $2.50 = $3.00 → Margin: 85%
  Power user: 2000 emails/month → Cost $0.50 + $10 = $10.50 → Margin: -47% ⚠️

Average margin depends on customer mix. If power users are 20% of base:
  Blended: (0.6 * 97%) + (0.2 * 85%) + (0.2 * -47%) = 58% + 17% - 9.4% = 65.6%
```

**The danger: Customer acquisition bias**

```
You attract power users because they get the most value.
But power users cost you the most to serve.

Ad targeting: "Get 10x more ideas"
  → Attracts heavy users
  → Heavy users cost 10x to serve
  → You make less margin on the people who need you most
```

**The fix: Usage-capped tiers**

```
Instead of "unlimited," offer:

Tier 1: $10/month, 50 email generations/month
Tier 2: $30/month, 500 email generations/month
Tier 3: $100/month, unlimited

Margin breakdown:
  Tier 1: $10 - ($0.50 + 50*$0.005) = $10 - $0.75 = $9.25 = 92.5%
  Tier 2: $30 - ($0.50 + 500*$0.005) = $30 - $3 = $27 = 90%
  Tier 3: Assume 2000 uses = $100 - ($0.50 + $10) = $89.5 = 89.5%

Result: Margins stay above 85% across tiers.
```

---

## Latency as a Cost Multiplier

**The problem: Slow models cost more at scale**

```
Two strategies for the same task:

Strategy A: Use GPT-4 (best quality)
  Time per request: 2 seconds
  Users tolerate latency, okay to use live
  Infrastructure: simple (just call API)
  Cost: $0.01/request

Strategy B: Use Haiku (fast, cheap)
  Time per request: 0.3 seconds
  5x faster, users feel snappy
  Cost: $0.0001/request
  Infrastructure: cache responses to avoid re-running

Cost-latency tradeoff:
  If you can cache 80% of requests (reuse old answers):
    Actual cost = 20% * $0.0001 = $0.00002/request (100x cheaper)
  With caching, you've traded latency (fast is good) for cost (cheap is good)
```

**Diagram: Latency vs. Token Cost Matrix**

```
Latency (time to response)
       ↑
       | GPT-4          (slow, expensive)
       | ~2 sec         $0.01/req
       |
       | Claude Sonnet  (medium, medium cost)
       | ~1 sec         $0.005/req
       |
       | Haiku          (fast, cheap)
       | ~0.3 sec       $0.0001/req
       |
       | Cached result  (instant, almost free)
       | ~0.01 sec      $0/req (cached hit)
       |____________
       Low cost              High cost →

Your optimization: Move right and down.
Use Haiku + caching to approach the bottom-right corner.
```

---

## Revenue vs. Cost Sensitivity Analysis

**Question: How sensitive is my margin to model choice?**

```
Product: Coding assistant ($50/month subscription)
Assumption: 100 customers, 50 code generations/month per customer = 5000 total/month

Cost scenario A (GPT-4): $0.01/request
  Monthly token cost: 5000 * $0.01 = $50
  MRR: 100 * $50 = $5,000
  Margin: ($5,000 - $50) / $5,000 = 99% ✓

Cost scenario B (Claude Sonnet): $0.005/request
  Monthly token cost: 5000 * $0.005 = $25
  Margin: ($5,000 - $25) / $5,000 = 99.5% ✓

Cost scenario C (Haiku): $0.0001/request
  Monthly token cost: 5000 * $0.0001 = $0.50
  Margin: ($5,000 - $0.50) / $5,000 = 99.99% ✓

Wait, all three show high margin?

Reality check: You've underestimated usage.
```

**More realistic scenario:**

```
Same product, but customers use 10x more (500 gen/month per user = 50K total/month):

Scenario A (GPT-4): $0.01/request
  Monthly cost: 50,000 * $0.01 = $500
  Margin: ($5,000 - $500) / $5,000 = 90%

Scenario B (Haiku): $0.0001/request
  Monthly cost: 50,000 * $0.0001 = $5
  Margin: ($5,000 - $5) / $5,000 = 99.9%

Impact: 10x usage changes margin from 90% to 99.9%.
Model choice becomes critical.
```

---

## Story Card: The Chatbot That Lost Money

**Setup:** Founders built a customer service chatbot for small businesses. Pricing: $500/month.

**Architecture:** Uses GPT-3.5 for all queries. No caching or fine-tuning.

**Customer profile:** Customer has 1000 support tickets/month.

**Unit economics (estimated):**
```
Price: $500/month
Tickets per month: 1000
Cost per ticket (GPT-3.5): ~$0.001
Monthly API cost: 1000 * $0.001 = $1
Margin: ($500 - $1) / $500 = 99.8%

Looks profitable!
```

**Reality (Month 3):**
```
Actual tickets per customer: 5000/month (they used it way more)
Actual cost per ticket: $0.005 (higher quality needed, took more tokens)
Monthly API cost: 5000 * $0.005 = $25
Margin: ($500 - $25) / $500 = 95%

Still okay, but...
```

**Reality (Month 6):**
```
Customer requested higher quality (avoid support escalations)
Upgraded to GPT-4: $0.01/request
Tickets: 5000/month
Cost: 5000 * $0.01 = $50
Margin: ($500 - $50) / $500 = 90%
```

**Crisis (Month 9):**
```
Customer success realized: support tickets are correlated with product bugs
As product improves, tickets should decrease
Instead, ticket volume increased 2x (10K/month) due to more users signing up

Cost: 10,000 * $0.01 = $100
Revenue: $500
Margin: 80%

With 100 customers, company now makes:
  Revenue: 100 * $500 = $50K
  Costs: 100 * $100 = $10K (+ $10K infrastructure) = $20K
  Profit: $30K

But growth kills margin:
  If customers add up (volume compounds), costs scale linearly
  Hiring customer support (fix the root cause) is better than AI chatbot
```

**Pivot (Month 12):**
1. Implement caching (80% of tickets are repeats) → reduce token cost 5x
2. Fine-tune a small model on customer's FAQ → cost drops to $0.0001/request
3. Implement escalation: only send hard tickets to GPT-4, others to fine-tuned model
4. New blended cost: $0.002/request

**Result:**
```
Blended cost: 10,000 * $0.002 = $20/month per customer
Margin: ($500 - $20) / $500 = 96%
```

**Key:** The business model doesn't work unless you optimize model selection, caching, and fine-tuning. Assuming "API cost is negligible" is dangerous.

---

## Reasoning Framework: "Will My AI Product Margins Hold?"

When you've priced your AI product:

1. **Estimate token usage per customer**
   ```
   How many LLM calls per customer per month?
   How many tokens per call?
   Total tokens = calls × average tokens/call
   
   Example: 500 calls/month × 2000 tokens/call = 1M tokens/month
   ```

2. **Choose a model and calculate cost per customer**
   ```
   Cost = (tokens / 1000) × (price per 1K tokens)
   
   Using Claude Sonnet ($5/1M input):
   Cost = (1M / 1000) × ($5 / 1000) = 1000 × $0.000005 = $5
   
   Using GPT-4 ($0.01 per input token):
   Cost = 1M × $0.00001 = $10
   ```

3. **Calculate margin**
   ```
   Margin = (Price - Cost) / Price
   
   Price = $50/month
   Cost = $10
   Margin = $40 / $50 = 80%
   ```

4. **Stress test: What if usage is 3x?**
   ```
   New cost = $30
   Margin = $20 / $50 = 40% (still viable, but risky)
   
   What if usage is 10x?
   Cost = $100 (exceeds price!)
   Margin = negative (you lose money)
   ```

5. **Optimization levers**
   ```
   If margin is < 70%, explore:
   - Cheaper model (Haiku vs. Sonnet)
   - Caching or semantic dedup (reuse results)
   - Fine-tuning on domain-specific tasks
   - Usage caps (tier pricing with limits)
   - Hybrid model (easy queries = small model, hard = GPT-4)
   ```

---

## Q&A (Built on Fundamentals)

**Recall 1:** Your product costs $20/month. Using Claude Sonnet, each customer makes 50 requests/month with 500 tokens/request. What's your margin?

*Must-say:*
- Total tokens = 50 * 500 = 25,000 tokens
- Claude Sonnet: $5 per 1M input tokens = $0.000005 per token
- Cost = 25,000 * $0.000005 = $0.125 per customer per month
- Margin = ($20 - $0.125) / $20 = 99.4% ✓

**Probe 1:** You're considering switching from GPT-4 ($0.01/token input) to Haiku ($0.00025/token input). Your average request is 1000 input tokens + 500 output tokens. What's your savings?

*Expected:*
- GPT-4: 1000 * $0.01 + 500 * $0.03 = $10 + $15 = $25
- Haiku: 1000 * $0.00025 + 500 * $0.00075 = $0.25 + $0.375 = $0.625
- Savings: ($25 - $0.625) / $25 = 97.5% cost reduction
- Risk: Haiku might fail on complex tasks
- Signal: A/B test Haiku on subset of requests first

**Probe 2:** A customer is generating 10x more requests than you expected. Your margin drops from 85% to 40%. Is this a product problem or a pricing problem?

*Expected:*
- Both. Pricing problem: you underestimated usage (forecast error).
- Product problem: customer is using it inefficiently (lots of redundant requests).
- Solutions:
  a) Implement caching to reduce API calls
  b) Add usage limits / tier customer up to plan with higher cap
  c) Implement rate limiting to cap costs
  d) All three

**Numeric 1:** You have 100 customers at $50/month. Average cost per customer is $3 (API + hosting). What's your contribution margin, and can you afford to spend $20/month on customer acquisition?

*Working:*
- Revenue per customer: $50
- Cost per customer: $3
- Contribution margin: $50 - $3 = $47
- If you spend $20 on CAC: net margin = $47 - $20 = $27
- Payback = $20 / $47 ≈ 4.3 months
- Verdict: Sustainable if customer LTV > 12 months (4.3 months payback + margin)

**Numeric 2:** Your AI product has a 40% API cost (token cost is 40% of revenue). You're considering a 20% price reduction to acquire more customers. How much must customer usage stay the same for breakeven?

*Working:*
- Original: $100 price, $40 cost, $60 margin
- New price: $80
- For margin to stay $60: cost must stay $40
- But cost is usage-dependent; if usage increases 25%, cost becomes $50
- At $80 price, $50 cost = $30 margin (50% decline)
- Verdict: Price cut only works if you also reduce usage (caching, better model) or attract lower-usage customers

---

## Checklist: AI Unit Economics Health

- [ ] Know your average API cost per customer per month
- [ ] Model choice is explicitly chosen (Haiku, Sonnet, GPT-4) with reasoning
- [ ] Calculated margin assuming 3x expected usage (stress test)
- [ ] Margin is > 70% in stress case (room for errors)
- [ ] Have identified 2+ ways to reduce token costs (caching, fine-tuning, better model)
- [ ] Understand where API costs are highest (which features burn the most tokens)
- [ ] Have usage cap or tier system to prevent margin collapse at scale
- [ ] Tested API cost impact of offering higher quality (e.g., GPT-4 vs Haiku)
- [ ] Know the latency impact of your model choice on user experience
- [ ] Have a plan if customers use 10x more than projected

**Common wrong answers:**
- "API cost is negligible" → It's not; it's often 30–50% of revenue for AI products
- "I'll optimize later" → No, you need margins now to reinvest in quality
- "I'll use the best model (GPT-4)" → Best ≠ cheapest; use cheapest that works
- "Unlimited requests will drive adoption" → Yes, but it'll also collapse your margins
- "Caching adds complexity I don't need" → If margins are tight, caching is essential
- "My customers won't use it that much" → Every founder underestimates usage 2–5x

---

## Questions for the Interviewer

- Walk me through how you estimated API costs vs. actual costs at scale.
- Have you had to make model choice trade-offs (quality vs. cost)? How did you decide?
- What's been your biggest surprise about customer usage patterns vs. estimates?
- How do you handle customers who generate much more usage than average?
- If your API costs suddenly increased 3x (price hikes), would your product still be viable?
