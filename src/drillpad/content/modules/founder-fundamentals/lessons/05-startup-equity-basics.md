# Startup Equity Basics

**Disclaimer: General education only. Not legal or financial advice. Consult a lawyer.**

## Equity Types

```
Options (employee):
  ├─ Right to buy shares at strike price (usually lower than market)
  ├─ Vest over 4 years (1-year cliff)
  │  └─ After 1 year: 25% vested. After 4 years: 100% vested
  ├─ If employee leaves: vested options keep, unvested forfeit
  └─ Tax: favorable (long-term capital gains if held >1 year)
  
RSU (Restricted Stock Units, big tech):
  ├─ Right to receive shares (no strike price, free)
  ├─ Vest over 4 years
  ├─ At vesting: taxed as income (vesting_price * shares)
  └─ Shares then appreciated (additional capital gains)

Common stock (founder):
  ├─ Ownership percentage (100M shares total, founder has 20M = 20%)
  ├─ No vesting (already own)
  └─ Capital gains on exit (sale or IPO)

Preferred stock (investor):
  ├─ Liquidation preference: get paid before common stock
  └─ Example: Series A investor: if sold for $10M, investor gets $5M (50%)
```

## Valuation & Dilution

```
Example:

Founding: founder 100% (1M shares)
  └─ Value: $1M valuation

Series A: investor puts in $5M at $5M valuation
  ├─ Investor gets: $5M / $5M = 1M shares (50% of 2M total)
  ├─ Founder now: 50% (diluted from 100%)
  └─ Post-money valuation: $10M

Series B: investor puts in $20M at $20M valuation
  ├─ Investor gets: $20M / $20M = 1M shares (25% of 4M total)
  ├─ Series A: still 1M (25%)
  ├─ Founder: still 1M (25%)
  └─ Post-money valuation: $40M

Exit (sale for $100M):
  ├─ Founder: 25% = $25M
  ├─ Series A: 25% = $25M (but liquidation pref might apply)
  ├─ Series B: 25% = $25M
  └─ Employees: options worth ~$25M / employee count (split)
```

## Vesting & Cliffs

```
Offer: 1M options, 4-year vest, 1-year cliff

Timeline:
  ├─ Day 1: 0 vested (all locked)
  ├─ Year 1: 0 vested (cliff not met)
  ├─ Year 1 + 1 day: 250K vested (25%, cliff met)
  ├─ Year 2: 500K vested (25%)
  ├─ Year 3: 750K vested (25%)
  ├─ Year 4: 1M vested (25%)

If you leave after 1.5 years:
  ├─ Vested: 500K options
  ├─ Unvested: 500K options (forfeited)
  ├─ You keep: 500K options (exercisable)
  
Strike price impact:
  ├─ Options strike: $0.10 (seed round)
  ├─ Current price: $1.00 (Series B)
  ├─ Intrinsic value per option: $0.90
  ├─ 500K options = $450K unrealized gain
  └─ Tax: on exercise, you pay ordinary income tax on gain
```

## Common Terms

```
Vesting: schedule for earning equity

Cliff: must stay N years before any vesting (1 year typical)

Strike price: price you pay to buy options

Dilution: your % ownership decreases as company raises

Liquidation preference: investor priority in exit

Anti-dilution: investor protection if future rounds cheaper

Founder vesting: even founders should have vesting (4 years)
  └─ Protects if co-founder leaves early
```

---

## Interview Checklist (General Education)

- [ ] Options vs RSUs vs common stock
- [ ] Vesting: 4-year standard, 1-year cliff
- [ ] Dilution: each round reduces your %
- [ ] Strike price: affects post-tax value
- [ ] Liquidation preference: investors get paid first

## Common Wrong Assumptions

- ❌ "100% means I get 100% of exit" — likely diluted by future rounds
- ❌ "Vesting doesn't matter" — loss of 50% if you leave year 2
- ❌ "Options are free" — you pay strike price + taxes to exercise
- ❌ "Cliff is bad" — actually protects founders too (mutual safety)
