# 2PC & Sagas: Coordinating Multi-Service Transactions

## The Problem: Order Processing Across Services

You're building an e-commerce system:

```
Client request: "Buy 1x Widget for $99"

This requires:
  1. Debit customer account (-$99)
  2. Decrement inventory (-1)
  3. Create order record
  4. Send email confirmation

Services involved:
  - Payment Service (holds customer balance)
  - Inventory Service (tracks stock)
  - Order Service (persists order)
  - Notification Service (sends email)
```

**The core problem:** What happens if step 2 fails?

```
Timeline:
  T1: Debit account (-$99) ✓ SUCCESS
  T2: Decrement inventory (-1) ✗ FAILS (out of stock)
  T3: ???
  
  Now: Customer's money is gone, but no order was placed.
  This is a consistency violation (customer lost $99).
```

This is why we need **distributed transactions**.

---

## First Principles: What is a Distributed Transaction?

A distributed transaction **spans multiple services/databases** and must maintain **ACID properties**:

```
ACID in distributed systems:

A - Atomicity: Either ALL steps succeed, or NONE do
    (no partial transactions)
    
C - Consistency: Data never enters an invalid state
    (if inventory is 0, you can't sell)
    
I - Isolation: Concurrent transactions don't interfere
    (customer A and B can't both buy the last item)
    
D - Durability: Once committed, data survives failures
    (if acknowledged, it stays committed even if DB crashes)
```

**Challenge:** ACID is easy on a single database (locks, transactions). Distributed ACID is hard (no global lock, networks fail, databases are independent).

---

## Solution 1: Two-Phase Commit (2PC)

**Two-Phase Commit** is a protocol to atomically commit across multiple databases.

### Phase 1: Prepare

Coordinator (Order Service) asks each participant "Can you commit?"

```
Coordinator             Service1            Service2            Service3
    |                     |                   |                   |
    +--Prepare----------->|                   |                   |
    |                 (lock rows,             |                   |
    |                  validate)              |                   |
    |                     +--Prepare--------->|                   |
    |                     |                   +--Prepare--------->|
    |                     |<--YES (locked)----|                   |
    |<--YES (locked)------|                   |                   |
    |                     |                   |<--YES (locked)----|
    |
    | (now all services have locked and validated)
```

Each service:
1. Acquires locks on affected rows
2. Validates the transaction (e.g., sufficient balance, stock available)
3. Returns "YES I can commit" (keeping locks held)

### Phase 2: Commit

Coordinator tells all participants "Go ahead, commit!"

```
    +--Commit---------->|
    |                   +--Commit------->|
    |                   |                +--Commit------->|
    |<--ACK-------------|                |                |
    |<--ACK-------------|                |                |
    |<--ACK-------------|                |                |
    |
    | (all have written changes to disk and released locks)
```

Each service:
1. Writes changes to persistent storage
2. Releases locks
3. Acknowledges "Committed"

---

## 2PC Timeline: Success Case

```
T0: Customer clicks "Buy"
T1: Coordinator asks Payment Service: "Can you debit $99?"
    → Service locks account row, checks balance >= $99
    → Returns "YES, locked"

T2: Coordinator asks Inventory Service: "Can you decrement stock?"
    → Service locks inventory row, checks stock > 0
    → Returns "YES, locked"

T3: Coordinator asks Order Service: "Can you create order?"
    → Service locks order table, validates input
    → Returns "YES, locked"

T4: All confirmed. Coordinator sends "COMMIT" to all.
    T4a: Payment Service: debit $99, release lock, reply "ACK"
    T4b: Inventory Service: decrement stock, release lock, reply "ACK"
    T4c: Order Service: create order, release lock, reply "ACK"

T5: Coordinator received all ACKs → transaction is durable.
    Customer sees "Order placed" ✓
```

---

## 2PC Failure: What Goes Wrong

### Scenario 1: Prepare Phase Fails

```
T0: Coordinator asks Payment Service: "Can you debit $99?"
    → Service responds "NO" (insufficient balance)

T1: Coordinator immediately sends "ROLLBACK" to all.
    T1a: Inventory Service rolls back (unlocks, discards prepared changes)
    T1b: Order Service rolls back
    
    Result: No state changed. Clean.
```

### Scenario 2: Commit Phase Fails (Network Partition)

```
T0: All services lock and return "YES"
T1: Coordinator sends "COMMIT" to Payment Service → ACK ✓
T2: Coordinator sends "COMMIT" to Inventory Service → TIMEOUT (network down)
T3: Network recovers 1 hour later.
    Inventory Service still holding lock on stock row.
    Question: Did the coordinator commit or not?
    
Problem: Inventory Service doesn't know.
    - If it committed: other requests can't access stock
    - If it didn't commit: we lost $99 from customer but no order
    
This is the "blocking" problem.
```

**Why is this bad?** 
- Locks held across long delays cause contention (low throughput)
- If coordinator crashes mid-commit, participant services hang indefinitely
- Network partitions make 2PC unreliable (FLP impossibility theorem bounds)

**2PC in practice:** Works in controlled environments (bank transfers within a company, private datacenters). Fails in distributed cloud systems (high latency, frequent failures).

---

## Solution 2: Saga Pattern

**Saga** is a different approach: Instead of locking, accept that transactions can fail and **plan for compensation** (rollback).

### Saga Orchestration (Synchronous)

Coordinator orchestrates the steps and calls services in sequence:

```
Coordinator
    |
    v
1. Call Payment Service: Debit $99
   → Success? Move to step 2
   → Failure? Go to rollback
    |
    v
2. Call Inventory Service: Decrement stock
   → Success? Move to step 3
   → Failure? Rollback step 1 (refund customer)
    |
    v
3. Call Order Service: Create order
   → Success? Move to step 4
   → Failure? Rollback steps 2 and 1
    |
    v
4. Call Notification Service: Send email
   → Success? Done
   → Failure? Rollback all (but order already created)
```

**Key idea:** Each step has a compensation action (inverse).

```
Step                           Compensation
────────────────────────────────────────────────
Debit customer $99             Credit customer $99
Decrement inventory by 1        Increment inventory by 1
Create order                   Delete order
Send email                     Send "order cancelled" email
```

---

## Saga vs 2PC Timeline

### Success Case (Both Are Identical)

```
2PC:
  Prepare 1, Prepare 2, Prepare 3 (lock all) → Commit all → Done

Saga:
  Execute 1 ✓, Execute 2 ✓, Execute 3 ✓ → Done
```

### Failure Case (Different Behavior)

```
2PC:
  Prepare 1 ✓, Prepare 2 ✗ → Rollback 1, Rollback 2 → Clean

Saga Orchestration:
  Execute 1 ✓, Execute 2 ✗ → Compensate 1 → Done
  (Step 1 was "committed" before we knew step 2 would fail)
```

**Key difference:** 2PC is atomic at the start. Saga is atomic at the end (via compensation).

---

## Saga Choreography (Asynchronous, Event-Driven)

Instead of a coordinator, services listen to events and trigger compensations.

```
1. Order Service publishes: "OrderCreated"
   
2. Payment Service hears it, debits account
   → On success: publishes "PaymentDebited"
   → On failure: publishes "PaymentFailed"

3. Inventory Service hears "PaymentDebited", decrements stock
   → On success: publishes "InventoryDecremented"
   → On failure: publishes "InventoryFailed"
   
   Then sends:
     "PaymentFailed" → Payment Service listens, refunds
     "InventoryFailed" → Inventory Service refunds, Order Service listens and cancels

4. Notification Service hears "OrderCreated", sends email
```

**Diagram:**
```
Order Service              Payment Service
    |                         |
    +--OrderCreated---------->|
    |                         | (debit)
    |<--PaymentDebited--------|
    |
Inventory Service            Order Service
    |                         |
    |<--PaymentDebited--------|
    | (decrement)             |
    |                         |
    +--InventoryDecremented-->|
    | (or InventoryFailed)    |
```

**Pros:** Services are decoupled, higher throughput, resilient to network delays.
**Cons:** Harder to debug, compensations are implicit, requires careful event ordering.

---

## When to Use Each

| Criterion | 2PC | Saga Orchestration | Saga Choreography |
|-----------|-----|-------------------|------------------|
| **Latency** | Low (synchronous) | Low (synchronous) | High (asynchronous) |
| **Consistency** | Strong ACID | Eventual (via compensation) | Eventual (via compensation) |
| **Coupling** | Tight (all lock together) | Moderate (coordinator knows all) | Loose (event-driven) |
| **Failure recovery** | Automatic rollback | Explicit compensation | Explicit compensation |
| **Implementation** | Complex protocol | Straightforward | Complex event handling |
| **When to use** | Private networks, <5 services | Public cloud, <10 services | Decoupled microservices, choreography desired |

---

## Failure Scenario: Saga Compensation Fails

```
Saga execution:
  Step 1: Debit account $99 ✓
  Step 2: Decrement stock ✗ FAILS
  
Compensate Step 1:
  Credit account $99 ✗ FAILS (Payment Service is down)
  
Now:
  - Account is debited (customer lost $99)
  - Stock was not decremented (it's correct)
  - Order was never created
  - Compensation failed (refund didn't go through)
  
Customer's view: "My $99 is gone, I have no order, and no one is helping me."
```

**How to handle this?**
1. **Idempotent compensations:** Make sure credit $99 is idempotent (if retried, same result)
2. **Dead-letter queue:** Log failed compensations, retry asynchronously
3. **Manual intervention:** Alert operations team to manually refund
4. **Timeout & retry:** Keep trying compensation until it succeeds

---

## Real Example: Payment Failure + Inventory Success

```
Inventory system had a bug: "Accept stock decrement, but sometimes don't persist"

Timeline:
  T1: Saga orchestrator calls Inventory: "Decrement by 1"
      → Inventory returns success
      → Saga thinks: "OK, stock is gone"
      
  T2: Saga calls Payment: "Debit $99"
      → Payment Service is down, returns failure
      
  T3: Saga compensates: "Increment inventory by 1"
      → Inventory increments (good)
      
  T4: Inventory bug manifests: It didn't actually decrement in T1
      → But it just incremented in T3
      → Net result: Stock is HIGHER than it should be
      
  T5: Customer orders same item 2 minutes later
      → System thinks there are 2 units
      → Sells both
      → Actual inventory was only 1
      
  Result: Oversold item (overbooking)
```

**Root cause:** Inventory's success response was a lie (it didn't persist the decrement).
**Solution:** Use exactly-once semantics (outbox pattern, see lesson 2).

---

## Story Card: Ride-Sharing Booking

```
System: Book a ride (charge card, allocate driver, create booking, notify)

Initial saga design:
  1. Charge card $25
  2. Find available driver
  3. Create booking record
  4. Send driver notification
  
Success: 4/4 steps pass → booking created

Failure scenario:
  1. Charge card $25 ✓
  2. Find driver: NO drivers available ✗
  
  Compensate step 1: Refund $25
  → But refund is slow (credit card takes 3–5 business days)
  → Customer sees refund after days
  → Bad experience
  
Better design:
  1. Find driver FIRST (no side effects, fast fail)
  2. If driver found: charge card
  3. Create booking
  4. Send notification
  
Now: If no driver available, fail before charging (better UX)
```

---

## Interview Pattern: Distributed Transaction Design

**Q: "Design a checkout system for an e-commerce platform. Customers buy items, you deduct inventory and charge their card. How do you ensure consistency?"**

Weak answer:
```
"Use transactions in the database."

Problem: You have multiple databases (payment DB, inventory DB).
A single database transaction won't span both.
```

Strong answer:
```
"I'd evaluate the latency and consistency requirements:

1. **If sub-100ms latency required + strong consistency:**
   Use 2PC (two-phase commit).
   - Coordinator locks all resources first
   - Validates all can proceed
   - Commits atomically or rolls back
   - Works if services are co-located or on fast network
   
   Tradeoff: Long lock times reduce throughput under contention.

2. **If 100ms–1s acceptable + eventual consistency OK:**
   Use Saga with orchestration.
   - Coordinator calls services sequentially
   - Each step can fail and be compensated
   - Allows services to be geographically distributed
   - Compensation is explicit (refund, decrement, etc.)
   
   Example flow:
     1. Debit card (charge customer)
     2. Decrement inventory
     3. Create order
     4. Send confirmation email
   
   If step 2 fails: Refund card immediately (step 1 compensation)
   
3. **If > 1s latency acceptable + high scale:**
   Use Saga with choreography (event-driven).
   - Order Service publishes 'OrderPlaced' event
   - Payment Service subscribes, debits card
   - On success, publishes 'PaymentConfirmed'
   - Inventory Service subscribes, decrements stock
   - Loose coupling, high throughput, harder to debug
   
4. **Prevent overselling:**
   - Inventory must return not just 'success', but idempotent responses
   - Include a transaction ID with each request
   - If retried, idempotent execution ensures no double-decrement

5. **Failure modes to handle:**
   - Compensation failures (refund fails): Use dead-letter queue, manual intervention
   - Duplicate requests: Use idempotency keys
   - Network partitions: Implement timeouts and retry logic
   - Service crashes mid-transaction: Persist state, resume on recovery
```

---

## Q&A: Drill the Concepts

**Recall 1:** What is atomicity in a distributed transaction?

*Expected:*
- Either all steps succeed, or none do
- No partial states (customer loses money but gets no order)
- 2PC achieves this via locking; Saga achieves via compensation

**Probe 1:** Why can't we just use one big database transaction across all services?

*Expected:*
- Each service owns its database (isolation principle)
- No single database transaction spans multiple systems
- Network is unreliable, so a distributed protocol is needed

**Probe 2:** In saga, if compensation fails, what happens?

*Expected:*
- Transaction is left in an inconsistent state
- Requires manual intervention or retry logic
- Dead-letter queue captures failed compensations
- Unlike 2PC, saga doesn't guarantee rollback

**Numeric 1:** You have 4 services in a saga. Prepare for one 2PC round-trip is 10 ms per service (prepare + commit). Each compensation is 5 ms. Success rate per service is 99%. What's the expected time for a successful transaction?

*Working:*
- Prepare: 4 services * 10 ms = 40 ms
- Commit: 4 services * 10 ms = 40 ms (overlapped, but synchronous = 40 ms)
- Total: 80 ms
- Success rate: 0.99^4 ≈ 96% (need to retry ~4% of the time)
- If retry takes 80 ms, expected latency = 80 + 0.04 * 80 = ~83 ms

**Numeric 2:** Saga orchestration: 5 services, each step takes 50 ms. One step fails 1% of the time. Compensation takes 100 ms. What's the throughput (requests/sec) if you have 1 worker?

*Working:*
- Success path: 5 * 50 ms = 250 ms
- Failure path (1%): 250 ms + compensation time
  - Compensation: depends on which step, but ~100 ms on average
  - Retry: 250 ms
  - Total on failure: 250 + 100 + 250 = 600 ms
- Expected time per request: 0.99 * 250 + 0.01 * 600 ≈ 252.5 ms
- Throughput: 1 / 0.2525 s ≈ 4 requests/sec

---

## Checklist: Did You Get It?

- [ ] You can explain atomicity in distributed systems (all or nothing)
- [ ] You understand 2PC: prepare phase (lock + validate), commit phase (persist + unlock)
- [ ] You know 2PC's blocking problem (locks held during network delays)
- [ ] You understand Saga: execute, then compensate on failure
- [ ] You know the difference between saga orchestration (coordinator) vs choreography (events)
- [ ] You can identify when to use 2PC vs saga vs choreography
- [ ] You understand compensation failures and how to handle them (dead-letter queue, retry)
- [ ] You can reason about latency, throughput, and consistency tradeoffs

## Common Wrong Answers

**Wrong:** "Use 2PC for all distributed transactions."
**Right:** 2PC is synchronous and locks resources. Use saga for high-scale systems.

**Wrong:** "Saga is eventual consistency, so data is inconsistent."
**Right:** Saga is eventually consistent in aggregate (via compensation), but each service's data is consistent. Customer either gets a refund or keeps the order, never a partial state.

**Wrong:** "Compensation always succeeds, like a database rollback."
**Right:** Compensation is a manual action (refund, decrement) that can fail. You need retry logic and manual intervention.

**Wrong:** "Saga orchestration and choreography are the same."
**Right:** Orchestration is synchronous with a coordinator. Choreography is asynchronous with event subscriptions (looser coupling).

**Wrong:** "If compensation fails, the transaction failed."
**Right:** Compensation failure is a separate incident. The original transaction may have succeeded; the compensation is what failed. Handle with dead-letter queues and alerts.
