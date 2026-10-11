# Systems Design Framework: Requirements → Architecture → Bottleneck → Scale

## The Process (Used at Every Firm)

```
Interviewer: "Design a notification system."

You:
1. CLARIFY REQUIREMENTS (ask questions!)
   - Real-time? (milliseconds, seconds, hours?)
   - Scale? (1K users? 1M users? 1B users?)
   - Reliability? (99%, 99.9%, 99.99%?)
   - Cost constraints?
   - Mobile? Web? Both?

2. ESTIMATE SCALE
   - Users: 1M
   - Active daily: 10%
   - Messages/day: 100M
   - Throughput: 100M / 86400 = ~1200 msg/sec
   - Peak: 5000 msg/sec (assume 5x burst)
   - Storage: 100M messages * 1KB = 100GB/day

3. DESIGN ARCHITECTURE
   - Service layers: API → queue → notifier → push gateway
   - Data: message DB, user preferences, delivery receipts
   - Queue: FIFO + priority (urgent first)
   - Push gateways: Firebase (mobile), Websocket (web)

4. IDENTIFY BOTTLENECK
   - Write rate: 5000 msg/sec to queue (SQS can handle)
   - Push rate: 5000 notifications/sec to Firebase (bottleneck!)
   - Firebase rate: ~1000 notifications/sec per connection
   - Need: 5 parallel threads or batch delivery

5. SCALE & ITERATE
   - Add more push gateway threads
   - Implement batching (group 10 notifications, send once)
   - Add retry logic + dead letter queue
   - Implement delivery confirmation

6. HANDLE FAILURES
   - Gateway down → queue accumulates, retry later
   - Database down → still serve from cache
   - Thundering herd → rate limit + backoff
```

---

## Step 1: CLARIFY Requirements (The Most Important Step)

**Bad interview:** Just start designing without asking.

**Good interview:** Ask 5-10 clarifying questions.

```
Notification System — Key Questions:

Functional:
  1. What types of notifications? (push, email, SMS, in-app?)
  2. How real-time? (immediate, batch hourly, asynchronous?)
  3. User preferences? (opt-in/out, notification frequency?)
  4. Delivery guarantee? (at-least-once, exactly-once?)
  
Non-functional:
  5. Scale? (DAU: 1K, 1M, 1B?)
  6. Latency SLA? (P99 < 100ms, < 1s, < 5s?)
  7. Availability? (99%, 99.9%, 99.99%?)
  8. Cost sensitive? (expensive operations acceptable?)

Example answers that change design:
  "Real-time push (100ms SLA), exactly-once, 1M DAU"
    → Need distributed queue (Kafka), idempotency keys
  
  "Batch emails hourly, at-least-once, 1M DAU"
    → Simple: SQS + email service, no idempotency needed
```

---

## Step 2: ESTIMATE (Back of Envelope)

```
Order Book Matching — Estimation:

"Design an order matching engine for an exchange."

Questions:
  - Assets? (1000 stocks, 100?)
  - Orders/sec? (given: 1M orders/sec)
  - Users? (assume 10K traders)
  - Latency SLA? (sub-microsecond for trading)
  
Estimates:
  Throughput: 1M orders/sec
  
  Latency budget: 1 µs (1000 ns)
  ├─ Network: 100 ns (packet arrival)
  ├─ Validation: 100 ns
  ├─ Matching: 300 ns (tree lookup + iteration)
  ├─ Serialization: 100 ns
  └─ Network out: 100 ns
  
  Memory:
    Order book: 1000 stocks * 10K levels * 100 bytes = 1GB
    Pre-allocated pool: 1M orders * 200 bytes = 200MB
    
  Bandwidth:
    Inbound: 1M orders/sec * 100 bytes = 100MB/sec
    Outbound: 1M fills/sec * 50 bytes = 50MB/sec
    (10Gbps NIC can handle 1.25GB/sec, we're at 150MB/sec = ok)
```

---

## Step 3: ARCHITECTURE (Boxes and Arrows)

```
High-level flow:

Client (trader)
  ↓ (order)
API Gateway (load balance)
  ↓
Order Validator (format check)
  ↓
Order Book (SPSC queue → matcher)
  ↓ (fills)
Risk Checker
  ↓
Settlement Service
  ↓
Response back to client

Storage:
  - Order Book (in-memory, persistent log)
  - Matched trades (database, audit log)
  - User positions (cache + database)
```

---

## Step 4: IDENTIFY BOTTLENECK (Dive Deep)

```
For each component, ask: "Is this the bottleneck?"

Order validation:
  CPU: 1M orders/sec * 100 ns = 100 ms CPU time
  Can use 1 core, not bottleneck

Order matching:
  CPU: 1M orders/sec * 300 ns = 300 ms CPU time
  Can use 1 core, not bottleneck

Risk checking:
  Latency: 10 ms per check (remote call!)
  Throughput: 1M orders/sec, 10ms per check
  Can handle: 1 / 0.01 = 100 orders/sec
  BOTTLENECK! (need parallel risk checkers or cached decisions)

Settlement:
  Database write: 1M writes/sec
  Database throughput: ~100K writes/sec
  BOTTLENECK! (batch writes, use queue)

The bottleneck determines the design:
  Risk: need to parallelize or change architecture
  Settlement: need queue + batching
```

---

## Step 5: TRADEOFFS (Make Decisions)

```
For each bottleneck, consider tradeoffs:

Bottleneck: Risk checking (10ms latency, 100 orders/sec capacity)

Option A: Parallelize (10 threads)
  Capacity: 1000 orders/sec
  Tradeoff: more threads, more state, complexity
  
Option B: Cache risk decisions (30s TTL)
  Capacity: unlimited (cache serves)
  Tradeoff: stale risk (if position changes, cache outdated)
  Acceptable if: risk window is small (market moves < 30s)
  
Option C: Use ML model (pre-compute risk, 1ms latency)
  Capacity: 1M orders/sec
  Tradeoff: accuracy vs speed, requires ML pipeline
  
Option D: Synchronous risk check, accept P99 latency spike
  Capacity: 100 orders/sec
  Tradeoff: some orders slow, but correct
  
CHOOSE: Option B (cache risk, 30s TTL)
  Reason: trading window is fast, stale risk acceptable
  Implementation: Redis, invalidate on position change
```

---

## Step 6: FAILURE MODES (What breaks?)

```
Identify failures and mitigation:

Risk service down:
  Problem: can't check risk, orders backlog
  Mitigation: fallback to conservative defaults (allow 0 risk)
            or: skip risk check (accept risk)
  
Settlement DB down:
  Problem: can't write matched trades
  Mitigation: queue trades in memory, replay on recovery
            or: replay from event log
  
Order book crash:
  Problem: all orders in-memory, lost on crash
  Mitigation: persist to WAL (write-ahead log)
            or: replicate to standby
  
Network partition:
  Problem: risk check unreachable
  Mitigation: timeout (default behavior)
            or: assume risk passed (if acceptable)
  
Cascade failure:
  Problem: slow risk check → orders queue up → memory fills → crash
  Mitigation: circuit breaker (skip risk after N timeouts)
            or: backpressure (reject orders when queue full)
```

---

## Interview Conversation Example

```
Interviewer: "Design a notification system."

YOU: "Sure. Let me clarify requirements:
  - Types? Push, email, or both?
  - Real-time? Milliseconds or batch?
  - Scale? Daily active users?
  - Reliability? 99.9%?
  - User preferences?"

Interviewer: "Push notifications, real-time, 10M DAU, 99.9%, user can opt-in/out."

YOU: "Let me estimate:
  - 10M DAU * 2% active = 200K concurrent
  - Notification rate: assume 1 notification per user per day = 10M/day
  - Throughput: 10M / 86400 sec = ~115 notifications/sec
  - Peak (assume 5x): 575 notifications/sec
  
  High-level design:
  - API receives notification request
  - Enqueue to queue (SQS or Kafka)
  - Async worker pulls from queue
  - Check user preferences (cache)
  - Send via push gateway (Firebase)
  - Log delivery status
  
  Bottleneck: Push gateway throughput
  - Firebase: ~1000 notifications/sec per connection
  - Need: 1 push gateway thread can handle it
  
  Failure modes:
  - Gateway down: queue backs up, retry
  - User preference stale: use TTL cache
  - Thundering herd: rate limit + exponential backoff
  
  Scaling to 100M DAU:
  - Add more worker threads (15 → 150)
  - Partition queue by user ID (1 partition per 1M users)
  - Add caching layer for preferences
  - Monitor push gateway latency, alert if > 1s"

Interviewer: "What about delivery confirmation?"

YOU: "Good question. We need exactly-once semantics:
  - Idempotency key in request (user ID + timestamp)
  - Worker checks if notification already sent
  - Store sent notifications in cache (TTL 24h)
  - If duplicate: return cached status (don't resend)
  
  Tradeoff: requires tracking sent notifications (extra storage)
  But: prevents duplicate notifications (better UX)"

Interviewer: "What if the push gateway is slow?"

YOU: "That's the bottleneck. Options:
  A) Add more gateway connections (parallelize)
  B) Batch notifications (send 10 at once)
  C) Queue and drop non-essential (background) notifications
  
  I'd choose B + circuit breaker:
  - Batch if queue size > 1000
  - If gateway timeout > 1s, circuit open (drop non-essential)
  - Resume when gateway recovers
  
  This prioritizes urgent notifications, degrades gracefully."
```

---

## The Framework Checklist

```
When stuck, use this checklist:

□ Clarify requirements (ask 5+ questions)
□ Estimate scale (QPS, storage, bandwidth)
□ Draw high-level architecture (services, storage, queues)
□ Identify bottleneck (which component is slowest?)
□ Deep dive on bottleneck (why? how to fix?)
□ Consider tradeoffs (consistency vs latency? cost vs reliability?)
□ Design for failures (what breaks? how to mitigate?)
□ Plan scaling (2x, 10x, 100x load)
□ Discuss alternatives (what else could you do?)
□ Address interviewer concerns (follow their probes)
```

---

## Q&A

**Recall 1:** You design a system for 1M QPS. Interviewer asks "what if load doubles to 2M QPS?" What do you say?

*Must-say:*
- Identify new bottleneck at 2M QPS
- Is it CPU-bound? (add more cores/machines)
- Is it I/O-bound? (add cache, sharding)
- Is it network-bound? (add load balancer, edge servers)
- For each bottleneck, propose fix + tradeoff

**Probe 1:** "Your design queues messages in SQS. What if SQS is full?"

*Expected:*
- Circuit breaker: start rejecting messages (fast fail)
- Or: in-memory queue (risky, data loss on crash)
- Or: add more SQS shards (distribute load)
- Or: shed load (drop low-priority messages)

**Numeric 1:** System handles 1000 QPS. P99 latency is 100ms. Database takes 50ms. Where's the other 50ms?

*Working:*
- Database: 50ms
- Queueing delay: ? (other 50ms likely)
- Solution: add more database replicas (reduce queueing)
- Or: optimize query (make database faster)
- Or: cache (avoid database call)

---

## Questions for the Interviewer

- What's your process for system design? (like this?)
- When you hit a bottleneck, how do you debug? (measure? profile?)
- Have you made different tradeoff choices? (what changed your mind?)
- What's the most complex system you've designed? (what made it hard?)
- How do you communicate design decisions to the team?

