# PnL & Risk Basics: Greeks, VaR, Sharpe Ratio, Mark-to-Market

## PnL Calculation

```
Position: Long 100 shares of SPY @ $400

Market price moves to $410:
  P&L = (410 - 400) × 100 = $1,000 profit

Mark-to-market (daily):
  Day 1: Buy @ $400, close @ $405
    Unrealized P&L = +$500
  Day 2: Hold, close @ $410
    Unrealized P&L = +$1,000 (cumulative)
  Day 3: Sell @ $410
    Realized P&L = +$1,000 (locked in)
```

---

## Greeks: Option Sensitivity

For option traders, Greeks measure risk exposure:

```
Delta: Price sensitivity
  Call option on SPY, strike=$410
  Delta = 0.6 (if SPY moves +$1, call moves +$0.60)
  
  Hedge: Short 60 shares of SPY
  If SPY +$1: call +$60, short stock -$60, net = $0 (delta-neutral)

Gamma: Delta's sensitivity
  Measures risk from large moves
  High gamma = delta changes rapidly
  Risky in volatile markets

Vega: Volatility sensitivity
  Call worth more when volatility ↑
  Vega = 0.05 (per 1% volatility change)
  
Theta: Time decay
  Call loses value as expiration approaches
  Theta = -0.02 per day
  Cost of holding long option
```

---

## Value at Risk (VaR)

**Definition:** Worst-case loss at confidence level.

```
Portfolio P&L distribution (daily):
  95% chance: loss < $100K
  5% chance: loss > $100K
  
VaR(95%) = $100K

Interpretation: 95% of days, losses ≤ $100K
               5% of days, losses > $100K (expect ~1 day/month)
```

**Calculation (simplified):**

```
Historical returns: [-2%, -1%, +0.5%, +1%, +1.5%, -0.5%, ...]

Sort returns from worst to best
95% VaR = 5th percentile (5% worst outcomes)

Typical equity portfolio: VaR(95%) = 1-3% of portfolio value
Typical options book: VaR(95%) = 5-10% (higher due to gamma)
```

---

## Sharpe Ratio

**Definition:** Return per unit of risk.

```
Sharpe Ratio = (Return - Risk-Free Rate) / Volatility

Example:
  Strategy return: +10% annually
  Risk-free rate: 2% (Treasury)
  Volatility (std dev): 8%
  
  Sharpe = (10% - 2%) / 8% = 1.0
  
Interpretation:
  Every 1% of volatility, earn 1% of excess return
  Sharpe < 0.5: Poor
  Sharpe 0.5-1.0: Okay
  Sharpe > 1.0: Good
  Sharpe > 2.0: Excellent (rare)
```

---

## Mark-to-Market Risk

```
Position: Long 1M barrel crude oil futures @ $70
         Oil price now $60
         
Unrealized loss: $1M × ($60-$70) = -$10M

Daily settlement:
  Brokerage: "You owe us $10M"
  Due: End of day
  If you can't pay: LIQUIDATED (forced sell)

This is real risk, not theoretical
```

---

## Interview Pattern: Risk Calculation

```
Q: "You have a $100M portfolio.
   Daily volatility: 1%.
   What is your expected daily loss on bad days?
   What should your daily risk limit be?"

Strong answer:
  "Expected loss calculation:
  
  Daily volatility = 1%
  Typical 99% VaR ~= 2.3 × σ = 2.3% (for normal distribution)
  
  Expected loss on 1% bad days: 2.3% × $100M = $2.3M
  
  Risk limit strategy:
    Conservative: 1% of portfolio = $1M daily limit
    (Accept 1M max loss per day, expected to hit it ~1x/month)
    
    Aggressive: 2% of portfolio = $2M daily limit
    (Expected to hit it ~1x/week)
  
  Recommendation: $1M limit (1% VaR)
    - Monitor: If losses approach $1M intraday, halt trading
    - Stress test: What if market drops 3%? ($3M loss possible)
    - Hedge: Buy protective puts if concerned about tail risk
"
```

---

## Checklist: Risk Management

- [ ] Daily VaR calculated
- [ ] Position limits enforced (size, Greeks)
- [ ] Liquidity buffer (can exit in crisis)
- [ ] Stress testing (market shocks)
- [ ] Concentration monitoring (not 80% in one stock)
- [ ] Greeks monitored (especially gamma, vega)
- [ ] Mark-to-market daily (know true P&L)
- [ ] Counterparty risk assessed

## Common Wrong Answers

1. **"Past returns = future returns"**
   - Volatility changes, regimes shift

2. **"Ignore tail risk (black swans)"**
   - 2008, COVID happened, will happen again

3. **"Greeks are optional"**
   - Critical for options / derivatives

4. **"VaR is worst-case loss"**
   - No, it's 5th percentile (worse losses happen ~1x/month)

5. **"Sharpe ratio > 0.5 is good enough"**
   - For systematic strategies, expect > 1.0
   - For alpha strategies, > 0.5 acceptable (harder)
