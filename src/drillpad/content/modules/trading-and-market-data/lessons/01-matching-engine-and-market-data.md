# Matching Engines & Market Data: Order Matching, Feed Handling, Snapshot Recovery

## The Problem

You submit a buy order. Market data shows a price, then drops. Did you get filled at the shown price? Or did it execute at a worse price?

```
Matching engine receives:
  10:00:00.000 BUY 100 shares @ $50
  10:00:00.001 ASK $49.50 (someone else's ask)
  
What happens?
  Option A: Fill at $49.50 (better for us!)
  Option B: Fill at $50 (our limit price)
  Option C: No fill (our order was too late)

Depends on order-matching semantics (price-time priority)
```

**Why this matters:** Trading systems must understand matching semantics, feed latency, and data integrity. A microsecond delay = missed profit or unexpected loss.

---

## Order Matching Semantics

**Price-Time Priority (most exchanges):**

```
Order book (sell side):
  ASK $50.00 (100 qty) - arrived t=1000
  ASK $50.01 (200 qty) - arrived t=1002
  ASK $50.05 (50 qty)  - arrived t=1001

Sorted by:
  1. Price (ascending)
  2. Time (ascending)

Result:
  ASK $50.00 (100 qty) - t=1000 → matches first
  ASK $50.05 (50 qty)  - t=1001 → matches second
  ASK $50.01 (200 qty) - t=1002 → matches third
```

**Aggressive buy order:**
```
BUY 200 @ market

Matches against:
  1. 100 @ $50.00 (fulfilled)
  2. 50 @ $50.05 (fulfilled)
  3. 50 @ $50.01 (partially fulfilled)

Execution: 100@$50.00 + 50@$50.05 + 50@$50.01
Avg price: (100×50 + 50×50.05 + 50×50.01) / 200 = $50.024
```

---

## Market Data Feed: Sequence Gaps & Recovery

**Challenge:** Market data arrives out-of-order or with gaps.

```
Time | Event
-----|------
10:00:00 | QUOTE EURUSD $1.0850 / $1.0851
10:00:01 | QUOTE EURUSD $1.0851 / $1.0852
10:00:02 | [NETWORK DROP - packet loss]
10:00:03 | QUOTE EURUSD $1.0854 / $1.0855
10:00:04 | QUOTE EURUSD $1.0853 / $1.0854

Question: Is $1.0854 the true price at 10:00:03?
Or did it spike to $1.10 between 10:00:02-10:00:03?
```

**Solution 1: Sequence Numbers**

```
Time | SeqNum | Event
-----|--------|-------
10:00:00 | 100 | QUOTE $1.0850
10:00:01 | 101 | QUOTE $1.0851
10:00:02 | 102 | [LOST]
10:00:03 | 103 | QUOTE $1.0854
10:00:04 | 104 | QUOTE $1.0853

Detect: 102 is missing
Action: Request snapshot recovery (get all data from 102 onwards)
```

**Solution 2: Snapshot vs Incremental**

```
Approach A: Full snapshot every second
  t=10:00:00 SNAPSHOT: All 10,000 securities + prices
  t=10:00:01 SNAPSHOT: All 10,000 securities + prices
  Cost: 10K × 8 bytes = 80KB per snapshot
  Throughput: 80KB/sec for snapshots alone

Approach B: Incremental updates
  t=10:00:00 SNAPSHOT: All 10,000 securities
  t=10:00:00.100 UPDATE: EURUSD $1.0851
  t=10:00:00.105 UPDATE: GBPUSD $1.2650
  t=10:00:00.200 UPDATE: EURUSD $1.0852
  Cost: 1-2 updates per second on average
  Throughput: ~100 bytes/sec (much more efficient)

Tradeoff:
  Snapshots: Simple, bulletproof, high bandwidth
  Incremental: Complex, requires maintaining state, low bandwidth
```

---

## Feed Outage & Recovery

```
Diagram: Snapshot recovery flow

Data stream interrupted:

   Incremental feed
   ▲
   │ EURUSD $1.0850
   │ EURUSD $1.0851
   │ [OUTAGE - 5 seconds]
   │ [System has old prices in memory]
   │
   └─→ Request SNAPSHOT at SeqNum 150
   
   Snapshot Response:
   │ EURUSD $1.0854 SeqNum=150
   │ GBPUSD $1.2650 SeqNum=150
   │ JPYUSD $0.0093 SeqNum=150
   │
   └─→ Continue with incremental
       EURUSD $1.0855 SeqNum=151
       GBPUSD $1.2651 SeqNum=151
```

---

## Failure Scenario: Duplicate Fills

```
Order: BUY 100 @ $50 (order_id=123)

Normal path:
  Sent to exchange t=0
  Matched t=1ms
  Confirmation t=5ms

Network issue:
  Sent to exchange t=0
  Matched t=1ms (execution on exchange)
  Confirmation lost (network down)
  
Trader doesn't see fill
Retransmits same order t=100ms

Exchange receives duplicate:
  First transmission: MATCHED (already filled)
  Second transmission: NEW ORDER, MATCHES AGAIN
  
Result: DOUBLE FILL (200 shares instead of 100)
```

**Detection:** Check order_id + venue for duplicates

**Prevention:** Idempotent order submission (unique order_id)

---

## Interview Pattern: Feed Handling

```
Q: "Market data feed drops for 2 seconds.
   Your strategy relies on real-time prices.
   What do you do?"

Strong answer:
  "Graceful degradation:
  
  1. Detection: Monitor sequence numbers
     Gap detected → alert
  
  2. Recovery options:
     a) Pause trading (safest)
        Stop new orders until feed recovered
     b) Use stale prices + buffer
        Trade with 2-second-old data (risky)
     c) Request snapshot immediately
        Catch up to latest prices (faster)
  
  3. Execution:
     Request snapshot for all symbols
     Apply pending updates from buffer
     Resume trading with recovered prices
  
  4. Risk management:
     Halt all positions until recovery
     Post-recovery: verify all fills matched expectations
  
  Trade-off: 2s of lost volume vs data corruption
  Better to miss opportunity than misplaced risk."
```

---

## Checklist: Market Data Systems

- [ ] Sequence numbers in feed
- [ ] Snapshot mechanism implemented
- [ ] Gap detection (missing sequence numbers)
- [ ] Replay buffer for out-of-order events
- [ ] Duplicate detection (order_id deduplication)
- [ ] Feed health monitoring (latency, gaps)
- [ ] Graceful degradation (pause on feed loss)
- [ ] Time synchronization (NTP, sub-millisecond)

## Common Wrong Answers

1. **"Just use the latest price"**
   - Stale price = wrong position sizing

2. **"Network is reliable, no need for recovery"**
   - Networks drop packets regularly

3. **"Deduplicate on client side"**
   - Must happen at exchange level (idempotent keys)

4. **"Snapshots are too expensive"**
   - Small overhead for reliability
