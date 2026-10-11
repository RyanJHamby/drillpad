# Backtesting Pitfalls: Lookahead Bias, Survivorship, Data Quality, Realism

## The Problem

Your backtest shows 50% annual returns. You deploy. Real returns: -5%. What happened?

```
Common pitfalls:

1. Lookahead bias: Used tomorrow's price to decide today's trade
2. Survivorship bias: Only tested on stocks that didn't go bankrupt
3. Data quality: Used dirty data (missing fills, wrong timestamps)
4. Overfitting: Tuned parameters to historical data (doesn't generalize)
5. Slippage: Assumed instant fills at market prices (reality: worse)
```

---

## Lookahead Bias

**Classic mistake:**

```python
# WRONG: Lookahead bias
for t in range(len(prices)):
    future_price = prices[t+1]  # <-- LOOKING AHEAD!
    if future_price > prices[t] * 1.02:
        BUY()
    
# This assumes you know tomorrow's price TODAY
# Backtest: 50% returns
# Live: -5% (can't actually see the future)
```

**Correct approach:**

```python
# RIGHT: Only use information available at time t
for t in range(len(prices)):
    current_price = prices[t]
    past_prices = prices[:t]  # Only historical data
    
    # Indicator: 20-day moving average
    ma20 = mean(past_prices[-20:])
    
    if current_price > ma20 * 1.02:
        BUY()
```

---

## Survivorship Bias

**Problem:**

```
Backtest universe: All S&P 500 stocks
But: Some were delisted during backtest period
  Lehman Brothers: delisted Sep 2008
  Enron: delisted Dec 2001

Backtest uses: Only survivors at end of period
Result: Never traded against bankruptcies (they're removed)

Real trading: Must handle bankruptcies
  Stock goes to zero
  Your position: -100% loss (but backtest assumes you exited)
```

**Fix:**

```
Use HISTORICAL constituents:
  Jan 2000: S&P had 500 stocks (set A)
  Jan 2010: S&P had 500 stocks (set B)
  
  Sets A and B overlap ~85%
  
  Backtest must include:
    - Stocks that were IN S&P but delisted
    - Stocks that entered S&P during period
  
  Do NOT filter to "survivors in Jan 2010"
```

---

## Data Quality Issues

**Missing data:**

```
Stock ABC, closing prices:
  Jan 1: $50
  Jan 2: $51
  Jan 3: [MISSING]
  Jan 4: $49
  Jan 5: $50

Backtest with naive interpolation:
  Jan 3: Assume $50.33 (average of Jan 2 & Jan 4)
  Trade at $50.33
  
Reality:
  Jan 3 was a holiday, market closed
  OR Jan 3 had a news event, real price was $45

If you assume $50.33 but reality was $45:
  Backtest profitable trade
  Live: Losing trade

Fix: Check for holidays, news events, corporate actions
```

**Dividend/split adjustments:**

```
Stock had 2:1 split on Mar 15

Historical prices (before split):
  Mar 14: $100
  Mar 15: $50 (post-split, adjusted price)
  
If backtest doesn't adjust:
  Thinks price dropped 50% (actually just split)
  Triggers false sell signal

Must use ADJUSTED prices from reliable source
```

---

## Overfitting

```
Parameters: Moving average window = N days

Backtest many N values:
  N=5: +5% return
  N=10: +12% return
  N=15: +18% return ← PICK THIS (best in backtest)
  N=20: +8% return
  ...
  N=100: -2% return

Deploy with N=15 → Live returns: -3%

Problem: N=15 was optimal for THIS historical period
But doesn't generalize to new data

Fix: Use train/test split
  Train (1990-2009): Fit N=15
  Test (2010-2020): Validate N=15
  If test results suck, model overfit
```

---

## Slippage & Latency

```
Backtest assumption:
  BUY order executes at market price = $50.00
  Instantly
  
Reality:
  Place order at t=0
  Order reaches exchange at t=1ms
  Fills at current ask (now $50.05)
  Confirmation back at t=2ms
  Slippage: $0.05 (0.1% of price)
  
Backtest P&L: +$1000
Live P&L: +$500 (half, due to slippage)
```

**Fix:**

```
Add slippage model:
  Slippage = 0.1% × order_size_in_$
  
  Or empirical:
  Measure actual fill prices vs mid-price
  Add typical observed slippage to backtest
```

---

## Interview Pattern: Backtest Validation

```
Q: "You built a backtest with 100% annual returns.
   How would you validate it before risking real money?"

Strong answer:
  "Validation checklist:
  
  1. Check for lookahead
     - Audit code: any use of future prices?
     - Run with random future data → should perform badly
  
  2. Check for survivorship
     - Use historical constituents (not survivors)
     - Include delisted securities
     - Measure: do backtest returns match reality?
  
  3. Data quality
     - Check for missing data (gaps)
     - Verify splits/dividends adjusted
     - Compare prices to external source
  
  4. Overfitting
     - Train/test split (separate periods)
     - Walk-forward validation (rolling window)
     - If test results << train, overfit
  
  5. Realistic assumptions
     - Add slippage (0.05-0.1% per trade)
     - Add commissions
     - Add market impact (large orders)
  
  6. Out-of-sample test
     - Test on data NEVER seen before
     - If backtest: +100%, but OOS: +10%, OVERFIT
  
  7. Stress test
     - Test on crisis periods (2008, COVID)
     - Does strategy still work? Or blow up?
  
  If all pass: Might be real
  If any fail: Back to drawing board"
```

---

## Checklist: Backtesting Quality

- [ ] No lookahead (only use info available at decision time)
- [ ] Historical constituents (not survivors)
- [ ] Data quality checked (missing data, splits, dividends)
- [ ] Slippage modeled (0.05-0.1% typical)
- [ ] Train/test split (separate historical periods)
- [ ] Walk-forward validation (rolling window)
- [ ] Out-of-sample test (unseen data)
- [ ] Stress tested (crisis periods)
- [ ] Live vs backtest correlation measured

## Common Wrong Answers

1. **"High backtest returns = guaranteed profit"**
   - Usually indicates hidden bias

2. **"Backtest 10 years, deploy on day 1"**
   - Need out-of-sample validation first

3. **"Use all available data for training"**
   - Need holdout test set

4. **"Slippage doesn't matter"**
   - Often 50% of P&L in live

5. **"Backtest on survivor-biased data"**
   - Will overestimate returns (exclude bankruptcy losses)
