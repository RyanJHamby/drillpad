# Outbox Pattern & Why Dual-Write Fails: Guaranteeing Exactly-Once

## The Problem: Publishing Events Atomically

You're processing an order. You need to:
1. Update `orders` table: Set status to "confirmed"
2. Publish event: "OrderConfirmed" to message queue (so Inventory Service decrements stock)

```
Timeline:
  T1: Database write succeeds: orders.status = 'confirmed' ✓
  T2: Publish to message queue fails (network down) ✗
  
  Result:
    - Database thinks order is confirmed (customer sees it)
    - Message queue never got the event (Inventory Service never decrements stock)
    - Overselling: same item can be sold twice
    
This is a consistency violation.
```

**The core problem:** Two separate systems (database and message queue) must stay in sync. If one fails, the other is left in an inconsistent state.

---

## First Principles: Atomicity Across Systems

**Atomicity:** Either both succeed, or both fail. No partial states.

On a single database: Transactions guarantee this.
```sql
BEGIN TRANSACTION
  UPDATE orders SET status = 'confirmed' WHERE order_id = 123
  INSERT INTO events (type, data) VALUES ('OrderConfirmed', ...)
COMMIT
```

The database ensures both writes succeed or both rollback.

**But:** Message queues are separate systems. You can't atomically commit to both.

```
Database        Message Queue
  |                  |
  +--Write-------->  (network delay)
  |                  |
  +--Fail           Publish?
     (database       (message queue
      committed)     never got it)
```

**This is the "two-phase problem":** How do you atomically write to two independent systems?

---

## Solution 1: The Outbox Pattern (Transactional Outbox)

**Key idea:** Use the database as the source of truth for events. Write everything to the database in one transaction, then a separate process polls the outbox and publishes to the queue.

### Step 1: Write to Database + Outbox

```
BEGIN TRANSACTION
  UPDATE orders SET status = 'confirmed'
  INSERT INTO outbox (event_type, event_data, published=false)
         VALUES ('OrderConfirmed', {...}, false)
COMMIT
```

Both writes happen atomically within the same transaction. Either both succeed or both fail.

### Step 2: Poll and Publish

A background process (outbox-publisher) continuously polls the outbox:

```
while True:
  rows = SELECT * FROM outbox WHERE published = false LIMIT 100
  for row in rows:
    try:
      publish(row.event_type, row.event_data)
      UPDATE outbox SET published = true WHERE id = row.id
    except PublishError:
      # Retry next iteration
      log(error)
      continue
```

**Timeline:**
```
T1: Order Service writes to DB + outbox (atomic) ✓
T2: Outbox-publisher polls and sees unpublished events
T3: Outbox-publisher publishes to message queue ✓
T4: Outbox-publisher marks as published
T5: Inventory Service consumes event and decrements stock ✓
```

**What if publisher crashes at T3?**
```
T3: Publish starts, message reaches queue
T3b: Publisher crashes before marking published
T4: Publisher restarts, polls again, sees same event
T5: Publishes again (duplicate event)
T6: Inventory Service consumes duplicate, tries to decrement twice
```

**This is OK if downstream services are idempotent** (see idempotent consumers below).

---

## Why Dual-Write Fails

**Dual-write:** Write to database and message queue independently.

```
Backend Service:
  UPDATE orders SET status = 'confirmed'
  publish_to_queue('OrderConfirmed', ...)
```

**Failure scenarios:**

### Scenario 1: Database Succeeds, Queue Fails

```
T1: UPDATE orders ✓ (committed to disk)
T2: publish_to_queue() ✗ (network timeout)

Result:
  Database: order is confirmed
  Queue: no event published
  
Downstream view:
  Inventory Service never decrements stock
  → Overselling possible
```

### Scenario 2: Queue Succeeds, Database Fails

```
T1: publish_to_queue() ✓ (event in queue)
T2: UPDATE orders ✗ (disk write fails, rollback)

Result:
  Database: order is NOT confirmed (rolled back)
  Queue: event already published
  
Downstream view:
  Inventory Service decrements stock for an order that doesn't exist
  → Underselling (stock goes negative)
```

### Scenario 3: Both Succeed, But Consumer Crashes

```
T1: UPDATE orders ✓
T2: publish_to_queue() ✓
T3: Inventory Service consumes, crashes mid-decrement
T4: Message is NOT acknowledged (stays in queue)
T5: Inventory Service restarts
T6: Consumes same message again, decrements twice
```

Again, requires idempotent consumers.

### Scenario 4: Network Partition

```
T1: Database write succeeds on primary
T2: Message queue published to one broker
T3: Network partition: primary and broker isolated

Question: Which side has authority?
  - If consumer reads from broker: event is real
  - If reading from primary: order is real
  - But they might be inconsistent
```

**Why dual-write is so dangerous:** You're relying on luck (both succeed), not protocol.

---

## Solution 2: Idempotent Consumers

If you can't guarantee at-most-once delivery, guarantee exactly-once **semantics** by making consumers idempotent.

**Idempotent:** Same input, same output. Safe to retry.

### Bad (Non-Idempotent)

```python
def consume_order_confirmed(event):
  # BAD: No guard against duplicates
  inventory = get_inventory(event.sku)
  set_inventory(inventory - event.quantity)  # Decrements every time!
```

If this runs twice:
```
T1: inventory = 100
T1b: Consume event: inventory = 100 - 1 = 99
T2: Consume duplicate: inventory = 99 - 1 = 98 ✗ WRONG (should be 99)
```

### Good (Idempotent)

```python
def consume_order_confirmed(event):
  # Check if already processed
  if event_id_exists(event.id):
    return  # Already processed, skip
  
  # Process
  inventory = get_inventory(event.sku)
  set_inventory(inventory - event.quantity)
  
  # Mark as processed (atomically)
  record_event_processed(event.id)
```

Now:
```
T1: inventory = 100
T1b: Consume event, mark processed: inventory = 99
T2: Consume duplicate:
     - Check: already_processed(event.id)? YES
     - Return early, no change
     → inventory = 99 ✓ CORRECT
```

### Storing Processed Events

Store processed event IDs in a table:

```sql
CREATE TABLE processed_events (
  event_id STRING PRIMARY KEY,
  processed_at TIMESTAMP
)
```

On receiving an event:
```sql
BEGIN TRANSACTION
  SELECT * FROM processed_events WHERE event_id = ?
  IF NOT FOUND:
    -- Process the event (update inventory, etc.)
    INSERT INTO processed_events (event_id, processed_at) VALUES (?, NOW())
  ELSE:
    -- Already processed, skip
COMMIT
```

---

## Exactly-Once Semantics with Outbox + Idempotent Consumers

Combining both patterns:

```
Producer Side:
  1. Write order + outbox entry atomically
  2. Outbox publisher polls and publishes (at-least-once delivery)

Consumer Side:
  3. Consumer checks: "Have I seen this event ID before?"
  4. If yes: Skip
  5. If no: Process and record event ID
```

**Result:** Exactly-once semantics at the application level.

```
Timeline:
  T1: Producer writes to outbox ✓
  T2: Publisher publishes (duplicate #1) ✓
  T3: Publisher publishes (duplicate #2) ✓ (due to retry)
  T4: Consumer receives duplicate #1, processes, records ID
  T5: Consumer receives duplicate #2, checks, sees ID recorded, skips
  
Net result: Order inventory decremented exactly once, despite duplicates.
```

---

## Event Sourcing: An Alternative

**Event sourcing:** Store events as the source of truth, not state snapshots.

Instead of:
```sql
orders table:
  order_id | status | amount | timestamp
  ────────────────────────────────────
  123      | confirmed | 99.99 | 2025-01-15
```

Store events:
```sql
events table:
  event_id | event_type          | order_id | data                | timestamp
  ────────────────────────────────────────────────────────────────
  1        | OrderCreated        | 123      | {amount: 99.99}    | 2025-01-15T10:00:00
  2        | OrderConfirmed      | 123      | {payment_id: 456}  | 2025-01-15T10:00:05
  3        | InventoryDecremented| 123      | {sku: ABC, qty: 1} | 2025-01-15T10:00:10
```

### Why Event Sourcing Solves This

```
On confirming order:
  INSERT INTO events (event_type, data) VALUES ('OrderConfirmed', ...)
  
This is a single write to a single table.
No dual-write, no race condition.

Derived data (current status):
  SELECT * FROM events WHERE order_id = 123
  Replay: OrderCreated → OrderConfirmed → InventoryDecremented
  → Compute current state: status = confirmed, inventory decremented
```

**Advantages:**
- Atomic, single write (no dual-write problem)
- Full audit trail (every change is recorded)
- Easy to replay and recompute state
- Naturally idempotent (same event, same result)

**Disadvantages:**
- More storage (all events kept)
- Queries are slower (must replay or compute snapshots)
- More complex (need event schema versioning)

---

## When to Use Each Pattern

| Pattern | Outbox | Dual-Write | Event Sourcing |
|---------|--------|-----------|-----------------|
| **Atomicity** | Guaranteed | Not guaranteed | Guaranteed |
| **Delivery semantics** | At-least-once | Best-effort | Exactly-once (single write) |
| **Implementation** | Moderate (polling) | Simple | Complex (replay, snapshots) |
| **Storage overhead** | Low (one extra table) | None | High (all events) |
| **Complexity** | Medium | Low (tempting but wrong) | High |
| **When to use** | Most systems (correct + simple) | **Never** (unsafe) | Complex domains, audit-heavy |

---

## Story Card: Payment Processor Bug

```
System: Process payment, update order status, notify customer

Initial design: Dual-write
  UPDATE orders SET status = 'paid'
  publish('OrderPaid', {...})

Bug: Network flaky. Publish often times out after order is updated.

Failure cascade:
  T1: Payment processed on external processor ✓
  T2: UPDATE orders ✓
  T3: Publish to queue ✗ (timeout after 5 seconds)
  T4: Service retries publish
  T5: Publishes succeeds (duplicate)
  
T6: Inventory Service consumes event
  T6a: No idempotency guard
  T6b: Inventory decremented for duplicate
  T6c: Overselling

Fix #1: Add idempotency check (consumer-side)
  - Guard against duplicate event IDs
  - Safe to retry

Fix #2: Switch to outbox pattern (producer-side)
  - Single atomic write to database
  - Outbox publisher handles retries
  - Consumer should still be idempotent (defense in depth)

Result with both fixes:
  Duplicates can happen, but idempotency guards prevent inconsistency.
```

---

## Failure Scenario: Outbox Publisher Lag

```
Outbox is large: 1 million unpublished events
Publisher is slow: Publishes 100 events/sec
Lag: 1M / 100 = 10,000 seconds ≈ 3 hours

During lag:
  Customer places order (written to outbox immediately)
  Customer sees "Order confirmed" in the web UI
  But Inventory Service hasn't received event yet (3 hour delay)
  Same item can be sold to another customer
  Overselling

Solution:
  1. Increase publisher throughput (parallel publishers, batch writes)
  2. Partition outbox by service (OrderService outbox, PaymentService outbox, etc.)
  3. Monitor lag, alert if > threshold
  4. Cache recent order status in-memory for immediate read-after-write consistency
```

---

## Q&A: Drill the Concepts

**Recall 1:** In the outbox pattern, where does the event live first?

*Expected:*
- In the database outbox table, same transaction as the business write
- Not in the message queue yet
- Publisher polls the database and publishes to queue

**Probe 1:** Why is dual-write inherently unreliable?

*Expected:*
- No atomic transaction across database and message queue
- If database succeeds but queue fails: event lost
- If queue succeeds but database fails: event orphaned
- No ordering guarantee: queue may receive event before database commits

**Probe 2:** If the outbox publisher crashes after publishing but before marking the event as published, what happens?

*Expected:*
- On restart, publisher sees the same unpublished event
- Republishes it (duplicate)
- This is OK if consumer is idempotent
- Consumer checks event ID, skips if already seen

**Numeric 1:** Your outbox table has 500K unpublished events. Publisher polls every 1 second and publishes up to 1000 events per poll. How long to clear the backlog?

*Working:*
- Backlog: 500K events
- Rate: 1000 events/sec (polls every 1 sec, 1000 per poll)
- Time: 500K / 1000 = 500 seconds ≈ 8 minutes

**Numeric 2:** You have an event-sourcing system with 1 billion events. Average event size: 200 bytes. How much storage?

*Working:*
- 1B events * 200 bytes = 200 GB
- Add indexes: ~50 GB
- Total: ~250 GB
- Add replication (3x): 750 GB
- This is substantial; may need partitioning (by order_id, by date, etc.)

---

## Story Card: E-commerce Payment Reconciliation

```
System: Order → Payment Service → Inventory Service

Design: Outbox pattern
  1. Create order, insert outbox event "OrderCreated"
  2. Publisher publishes to queue
  3. Payment Service consumes, charges card, publishes "PaymentSucceeded"
  4. Inventory Service consumes, decrements stock

Issue: Payment Service response is slow (credit card processor lags 30 seconds)

Timeline:
  T0: Customer clicks "Buy"
  T1: Order created, outbox event published ✓
  T2: Inventory Service consumes "OrderCreated", tentatively decrements stock
  T3: Payment Service processing payment (30 second lag)
  T4: Customer clicks "Buy" for same item (different user)
  T5: System says "Buy" is OK (inventory still shows 1 unit)
  T6: Sells second copy
  T7: (30 seconds later) First payment succeeds
  T8: (60 seconds later) Second payment succeeds
  T9: Both paid, both decremented, but only 1 unit available
  
Overselling again!

Root cause: We decremented inventory before confirming payment (optimistic).

Fix: Change order of events
  1. Create order (NOT decremented yet)
  2. Payment Service processes (slow)
  3. Payment Service publishes "PaymentSucceeded"
  4. Inventory Service consumes and decrements
  
Now:
  T2: Order created, no inventory change yet
  T4: Customer clicks "Buy" for same item
  T5: System reserves? (needs reservation mechanism)
     OR: asks inventory "Can I sell?" (synchronous check)
  
Lesson: Outbox pattern fixes atomicity, but ordering and consistency
        require careful event design and consumer logic.
```

---

## Interview Pattern: When to Use Outbox vs Event Sourcing

**Q: "How would you design a payment system where orders and payments must stay in sync?"**

Weak answer:
```
"Write to database and publish to Kafka. Use transactions."

Problem: Database and Kafka are two separate systems.
Atomicity isn't guaranteed across both.
```

Strong answer:
```
"I'd use the outbox pattern:

1. In the orders service, when creating an order:
   BEGIN TRANSACTION
     INSERT INTO orders (order_id, status, amount)
     INSERT INTO outbox (event_type, event_data, published=false)
   COMMIT
   
   Both writes are atomic in the database.

2. A background process polls the outbox:
   - Selects unpublished events
   - Publishes to Kafka (at-least-once)
   - Marks as published

3. Downstream services (Payment, Inventory) consume:
   - They check: 'Have I seen this event ID?'
   - If yes: skip (idempotent)
   - If no: process and store event ID

Result: Even if publisher retries and creates duplicates,
        downstream services are idempotent.

If the order is time-sensitive:
  - Cache order status in-memory for immediate reads
  - Outbox publisher updates it asynchronously
  - Customers see consistent writes with eventual consistency for events

Scaling considerations:
  - Partition outbox by service or order ID
  - Run multiple publisher instances (each gets different partition)
  - Monitor publisher lag (alert if > threshold)
  
If orders are complex (multi-step fulfillment):
  - Consider event sourcing instead
  - Store all events (OrderCreated, PaymentReceived, ShippingInitiated, etc.)
  - Replay events to derive current order state
  - Natural audit trail, easier to debug state machines
  - Tradeoff: More storage, slower queries (unless snapshots used)
```

---

## Checklist: Did You Get It?

- [ ] You understand why dual-write is unsafe (no atomicity)
- [ ] You know the outbox pattern: write to DB + outbox table atomically, then publisher polls
- [ ] You understand outbox publisher can create duplicates (and that's OK with idempotency)
- [ ] You can implement idempotent consumers (check event ID before processing)
- [ ] You know exactly-once semantics = at-least-once delivery + idempotent processing
- [ ] You understand event sourcing: store events, not snapshots
- [ ] You can decide when to use outbox vs event sourcing
- [ ] You can trace through failure scenarios (publisher crash, network partition, duplicate events)

## Common Wrong Answers

**Wrong:** "Dual-write is fine; we'll just be careful."
**Right:** Dual-write is inherently unsafe. Network failures are probabilistic; "being careful" doesn't help.

**Wrong:** "The outbox pattern guarantees exactly-once delivery."
**Right:** Outbox guarantees at-least-once. Exactly-once comes from idempotent consumers.

**Wrong:** "If the publisher crashes, we lose events."
**Right:** If publisher crashes after publishing but before marking published, we re-publish. Idempotent consumers handle duplicates.

**Wrong:** "Event sourcing is just storing events instead of state."
**Right:** Event sourcing is a fundamentally different architecture. Events are immutable, state is derived, replaying gives you audit trail and time travel.

**Wrong:** "Idempotency is just checking for duplicates."
**Right:** Idempotency is more: same input must produce same output, even if retried. Requires external state (like event ID table) to track what's been processed.

**Wrong:** "Event sourcing solves all consistency problems."
**Right:** Event sourcing guarantees atomic writes and audit trail, but doesn't magically solve ordering or causal consistency. Still need careful event design.
