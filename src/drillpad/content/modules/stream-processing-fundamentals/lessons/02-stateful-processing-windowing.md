# Stateful Processing & Windowing - Aggregations, Late Data

## The Stateful Problem

```
Events arriving: user clicks
  T=0s: click_user1
  T=1s: click_user2
  T=2s: click_user1
  T=3s: click_user3

Question: How many clicks per user in the last 10 seconds?
  T=10s: user1=2, user2=1, user3=1

To answer: Need to remember (state):
  - Which user clicked
  - How many times
  - When (to expire old clicks)

This is stateful processing.
```

## Windowing: Grouping Events by Time

### Tumbling Window (Fixed, Non-Overlapping)

```
Window 1: T=0-10s  → [click_0, click_1, ..., click_9]
Window 2: T=10-20s → [click_10, click_11, ..., click_19]
Window 3: T=20-30s → [click_20, click_21, ..., click_29]

Results:
  Window 1: user1=5, user2=3, user3=2
  Window 2: user1=4, user2=1, user3=4
  Window 3: user1=2, user2=6, user3=1

Use case: Hourly aggregations, daily metrics
```

### Sliding Window (Overlapping)

```
Window size: 10s, Slide: 5s

Window 1: T=0-10s   → [click_0, click_1, ..., click_9]
Window 2: T=5-15s   → [click_5, click_6, ..., click_14]  (overlaps with 1)
Window 3: T=10-20s  → [click_10, click_11, ..., click_19]

Result: More frequent updates, smoother transitions

Use case: Real-time monitoring (minute-by-minute latency)
```

### Session Window (Event-Based)

```
Session = burst of activity, gap = inactivity

User clicks:
  T=0s: click
  T=1s: click
  T=2s: click
  [gap: 30 seconds, no clicks]
  T=32s: click
  T=33s: click

Two sessions:
  Session 1: T=0-2s (3 clicks)
  Session 2: T=32-33s (2 clicks)

Use case: User behavior analysis (session = user intent)
```

## Late Data: The Hard Problem

```
Perfect world: Events arrive in order
  Event 1: T=0s, arrives T=0s ✓
  Event 2: T=1s, arrives T=1s ✓
  Event 3: T=2s, arrives T=2s ✓

Real world: Network delays
  Event 1: T=0s, arrives T=0s ✓
  Event 2: T=1s, arrives T=5s ← 4 seconds late!
  Event 3: T=2s, arrives T=2s ✓

Problem:
  Window closed at T=10s (had events 1, 3 only)
  Event 2 arrives at T=5s (after window closed)
  Where does it go?
  
  Option A: Drop it (data loss)
  Option B: Update window (retract old result, emit new result)
```

## Handling Late Data

### Allowed Lateness

```
Window size: 10s
Allowed lateness: 30s

Window T=0-10s:
  Close officially at T=10s (emit result)
  But accept events until T=40s (10s + 30s lateness)
  Event at T=5s arriving at T=35s? Still counted (within 40s)
  Event at T=5s arriving at T=50s? Dropped (beyond 40s)

Trade-off:
  Higher lateness = slower final result, more accurate
  Lower lateness = faster result, might miss events
```

### Retraction-Based Updates

```
Window T=0-10s emits:
  @T=10s: user1=5, user2=3, user3=2

Late event arrives at T=15s (user1 click at T=8s):
  Retract old result: -(user1=5)
  New result: +(user1=6)

Consumers see:
  @T=10s: Update (user1=5, user2=3, user3=2)
  @T=15s: Retraction (user1=5), Correction (user1=6)

Challenge: Downstream system must handle retractions
```

## Interview Pattern: Windowing Strategy

```
Q: "Real-time ML feature: count user clicks per minute.
   How do you handle late data?"

Weak answer:
  "Drop late data"
  (❌ Loses training data)

Strong answer:
  "Depends on use case:
  
  1. For feature importance (training):
     - Accuracy matters more than latency
     - Use 5-minute allowed lateness
     - Late clicks still affect training
     - Cost: 5min delay before final result
  
  2. For real-time metrics (dashboards):
     - Timeliness matters more than accuracy
     - Use 30-second allowed lateness
     - Quick feedback, accept 0.1% data loss
  
  3. For this case (ML features):
     - Allowed lateness: 5 minutes
     - Emit preliminary result at T=60s
     - Accept corrections until T=300s
     - Final result: after 5 minutes
  
  4. Implementation:
     Window: 60 second tumbling
     Lateness: 300 seconds
     
     Result flow:
       @T=60s: emit (preliminary)
       @T=90s: retraction + correction (late click at T=50s)
       @T=120s: retraction + correction (late click at T=70s)
       @T=360s: close window (no more corrections accepted)
  
  5. Monitoring:
     - Track % of clicks arriving late
     - Alert if > 5% (network issue?)
     - Track correction rate (how many updates per window?)
  
  6. Trade-off:
     - 5 min lateness means 5 min delay in training
     - Worth it for 99.9% completeness
     - If lateness < 1%, could reduce to 2 min"

Why this signals good judgment:
  - You understood accuracy vs latency tradeoff
  - You had concrete allowed lateness value
  - You thought about retractions (downstream handles it)
  - You'd monitor the actual lateness distribution
```

## What This Signals

- You've built real-time systems with windowing
- You understand late data isn't theoretical (happens in production)
- You can balance accuracy vs latency
- You know exactly-once is hard with retractions
