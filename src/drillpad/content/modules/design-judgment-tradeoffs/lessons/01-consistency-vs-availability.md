# Design Judgment: Consistency vs Availability (Firm-Specific)

## The CAP Theorem Decision Matrix

You cannot have all three: Consistency, Availability, Partition tolerance. **But the right choice depends on the firm.**

```
Domain (illustrative)  | Consistency Need | Availability Need | Decision
-----------------------|-----------------|-------------------|------------------
Trading systems        | HARD REQUIRE    | HIGH              | Consistency > Availability (CP)
AI inference platforms | MEDIUM          | HIGH              | Availability > Consistency (AP)
Cloud / payments       | MEDIUM-HIGH     | HARD REQUIRE      | Hybrid (can't sacrifice either)
```

## Trading Firms: Consistency > Availability

**Trading order book:**
```
User places limit order: "Buy 100 @ $50"
System must guarantee:
  - Exactly one order in the book (no dupes)
  - Order at correct price level
  - No skipped sequence numbers

If partition happens:
  - STOP accepting orders (fail-closed)
  - Wait for partition to heal
  - Resume once consistent

Why? Order loss = lost revenue. Downtime = downtime (hedge elsewhere).
Cost of inconsistency >> Cost of unavailability
```

**Interview signal:**
```
Q: "What if your order book replication lag to backup is 500ms and network partitions?"

Weak answer:
  "We serve from replica, eventually consistent"
  (❌ An interviewer will ask: what if two order books diverge?)

Strong answer:
  "We wait for ack from backup (CP design). If partition, we stop accepting 
   orders until partition heals. It's better to be down 10 seconds than 
   have one order duplicated."
  (✅ Shows you understand the cost model)
```

## AI Infrastructure: Availability > Consistency

**Anthropic inference system:**
```
User requests: "Generate response"
System requirement:
  - 99.99% uptime (customers expect instant API)
  - Response eventually correct (small inconsistency acceptable)
  - Can serve from stale replica

If partition happens:
  - SERVE from replica (might be stale KV-cache)
  - Accept slight accuracy loss (0.001% variance in tokens)
  - Reconcile later

Why? Downtime = angry customers. Slight staleness = imperceptible.
Cost of unavailability >> Cost of inconsistency
```

**Interview signal:**
```
Q: "Your inference cluster splits in half (network partition). What do you do?"

Weak answer:
  "We have consensus to detect partition, stop serving until healed"
  (❌ Anthropic wants uptime, you're offering downtime)

Strong answer:
  "We detect partition, serve from the larger half (or both if balanced).
   KV-cache might be 500ms stale. Users won't notice 0.001% accuracy change.
   We reconcile once partition heals."
  (✅ You prioritized their core metric: uptime)
```

## AWS/Fintech: Hybrid (Can't Sacrifice Either)

**Stripe payment system:**
```
User charges card: "Process $50"
System requirements:
  1. CONSISTENCY: No double-charge (exact once)
  2. AVAILABILITY: Handle 99.95% uptime (SLA)
  3. PARTITION TOLERANCE: Multi-region

Design:
  - Idempotency key (prevents double-charge via consistency)
  - Async processing (gives availability)
  - Fallback to stale state (partition tolerance)
```

**Decision tree:**
```
Partition happens:
  1. Primary region down?
     → Fail over to secondary (AP on data)
     → BUT idempotency key prevents double-charge (CP on semantics)
     
  2. Payment processor unreachable?
     → Queue the request (availability)
     → Retry with idempotency key (consistency on semantics)
     
Result: "Effectively CP for what matters (semantics), AP for availability"
```

## Decision Framework: How to Choose

**Ask yourself:**

1. **What's the unit of consistency?**
   - Trading: individual order (tiny scope → easier to enforce)
   - Payments: transaction (small scope → enforced via DB)
   - Notifications: message delivery (large scope → hard to enforce)

2. **What's the cost of inconsistency?**
   - Order book divergence: loss of real money → CONSISTENCY
   - Stale cache: 0.001% accuracy loss → AVAILABILITY
   - Duplicate payment: loss of real money → CONSISTENCY
   
3. **What's the cost of unavailability?**
   - Trading platform down: traders hedge elsewhere → MEDIUM PAIN
   - API down: customers lose revenue → HIGH PAIN
   - Notification down: users miss message (low cost) → AVAILABILITY

4. **Scope of consistency enforcement**
   - Single server? Easy (lock)
   - Single DC? Hard (replication)
   - Multi-region? Very hard (consensus)

## Domain-Specific Interview Answers

### Trading systems

**Q: "Design a matching engine for 1M orders/sec across 3 DCs. What happens if one DC is unreachable?"**

Strong answer:
```
"Consistency is the constraint. Matching must happen in one DC (CP).

Design:
  1. Primary DC processes all orders
  2. Backup DCs replicate (streaming log)
  3. Network partition? Stop accepting orders to primary
     (fail-closed, not fail-open)
  4. Traffic reroutes to backup after 5s timeout
  
  Cost: 5s downtime to guarantee no order duplication
  Benefit: Zero inconsistency risk"
```

Why this works:
- Shows you understand the **cost model** (consistency > uptime)
- Explains the **decision** (fail-closed, not fail-open)
- Names the **trade-off** explicitly (5s downtime)

### AI infrastructure

**Q: "Your inference cluster spans US and EU. Network partition. What do you do?"**

Strong answer:
```
"Availability is the constraint. Each region serves independently.

Design:
  1. Detect partition (heartbeat timeout)
  2. US serves US traffic, EU serves EU traffic
  3. KV-cache might be 5 minutes stale (acceptable)
  4. On heal: reconcile (EU catches up to US log, or vice versa)
  
  Cost: 0.1% accuracy loss (users won't notice)
  Benefit: 99.99% uptime (no geographic blackout)"
```

Why this works:
- Shows you understand the **user impact** (uptime >> accuracy)
- Explains the **recovery** (reconcile on heal)
- Names the **acceptable loss** (0.1% accuracy)

### AWS (Stripe, PayPal)

**Q: "Design a payment system for 1M transactions/day across 3 regions. Can you lose a region?"**

Strong answer:
```
"Hybrid approach: strong consistency on semantics, high availability on uptime.

Design:
  1. Idempotency key (database enforces: no duplicate charges)
  2. Primary region processes, async replicates to secondaries
  3. Region down? Fail over to secondary (might lose 5 min of replication)
  4. Idempotency key prevents double-charge on recover
  
  Cost: 5 min of lost in-flight (retried with same key)
  Benefit: No double-charge risk, high availability"
```

Why this works:
- Shows you understand **semantic consistency** vs **availability** are different
- Explains the **recovery mechanism** (idempotency)
- Names the **actual loss** (5 min data, not 5 min downtime)

## Interview Pattern Recognition

**🚩 Red flags that you're wrong about consistency/availability:**

1. "We'll use eventual consistency" (trading context) → Wrong domain, wrong cost model
2. "We need strong consistency everywhere" (AI-infra context) → Sacrifice uptime unnecessarily
3. "Idempotency key solves everything" (cloud-platform context) → Doesn't handle replication lag

**✅ Green flags you're thinking right:**

1. Named the firm's actual constraint (trading: single order correctness)
2. Explained why consistency > availability (cost of mistake)
3. Described the recovery mechanism (partition heal, fallback strategy)
4. Named the acceptable loss (5s downtime, 0.1% accuracy, 5 min replication)

## Quick Reference: When You're Stuck

```
In interview, asked to design X system, unsure about CAP:

1. Ask: "What's the cost of inconsistency?"
   - > cost of downtime? → Pick Consistency (CP)
   - < cost of downtime? → Pick Availability (AP)
   
2. Ask: "What's the scope of consistency?"
   - Single server → Lock (easy)
   - Single DC → Quorum (hard)
   - Multi-region → Consensus (very hard)
   
3. Ask: "Can we degrade gracefully?"
   - Yes (AP) → serve from stale replica
   - No (CP) → stop serving
```

