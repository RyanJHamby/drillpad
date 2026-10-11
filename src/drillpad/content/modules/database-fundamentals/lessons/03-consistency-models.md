# Consistency Models: What "Correct" Means

## Overview

Databases offer different consistency guarantees. This lesson covers:
1. Strong consistency (ACID)
2. Eventual consistency (BASE)
3. CAP theorem (pick 2 of 3)
4. Real-world implications

---

## Strong Consistency (ACID)

ACID = Atomicity, Consistency, Isolation, Durability

```
Transaction:
  BEGIN
    Deduct $100 from Account A
    Add $100 to Account B
  COMMIT

Guarantee: Either both succeed or both fail. Never partial.
Cost: Locks, coordination between replicas (slower)
```

**Example: Payment transfer**

```
User: Transfer $100 from savings to checking

Without ACID:
  Deduct from savings ✓
  System crashes
  Add to checking ✗
  Result: Money lost

With ACID:
  Both deduct + add, or neither
  Result: Money conserved
```

---

## Eventual Consistency (BASE)

BASE = Basically Available, Soft state, Eventually consistent

```
Write to database A:
  "User profile: name=John"
  
Replicate to B, C, D... asynchronously

Result:
  Immediately after write: A has "John", B/C/D don't
  1 second later: All replicas have "John"
  
Guarantee: Eventually all replicas match (but not immediately)
Cost: Reads might see stale data
Benefit: Fast writes (no waiting for replication)
```

**Example: Social media like count**

```
User likes post. Cache says "5 likes" (stale).
Actual in DB: "8 likes".
User refreshes → sees "8 likes" (eventually caught up).
```

---

## CAP Theorem

Distributed systems can have 2 of 3:
- Consistency (all reads see same data)
- Availability (system always responds)
- Partition tolerance (survives network split)

```
Network splits into 2 groups: A and B can't communicate.

Option 1: Consistency (choose C)
  Reject writes in both groups (wait for network fix)
  Result: Available=No, Partition=Yes
  
Option 2: Availability (choose A)
  Both groups accept writes independently
  Result: When network heals, conflict (must merge)
  Example: Git merge conflict
  
Most real systems choose: A + P (availability + partition tolerance)
Trade-off: Sacrifice consistency (eventual consistency)
```

---

## Consistency Levels

From strongest to weakest:

```
1. Linearizable
   Every operation appears to happen instantly
   Example: Single-server database
   
2. Sequential Consistency
   Order preserved globally, but not instant
   Example: PostgreSQL with replication
   
3. Causal Consistency
   Related operations preserve order, unrelated can reorder
   Example: Facebook feed (your likes → friend sees, but 2 unrelated posts can reorder)
   
4. Eventual Consistency
   All replicas eventually match, no ordering guarantee
   Example: Cassandra, DynamoDB
```

---

## Real-World Example: E-Commerce

```
Scenario: Inventory management

Products: 100 units in stock

Customer 1: Buy 1 unit
Customer 2: Buy 1 unit

Strong consistency:
  DB lock: inventory
  Customer 1 buys: inventory = 99
  Customer 2 buys: inventory = 98
  Result: Correct inventory count
  Cost: Customers wait for lock

Eventual consistency:
  Customer 1: Inventory = 100, buys, local count = 99 (optimistic)
  Customer 2: Inventory = 100, buys, local count = 99 (optimistic)
  Later: Replicate → actual inventory = 98 (both succeeded)
  
  Problem: Oversold (sold 2 units, only 1 left)
  Solution: Reconciliation job finds and refunds 1 customer
```

---

## Choosing a Consistency Model

```
Strong consistency needed?
  Financial transactions → Yes (ACID)
  Payments → Yes (ACID)
  Order processing → Yes (ACID)
  
Eventual consistency OK?
  Social media likes → Yes
  User profile sync → Yes
  Analytics → Yes
  
Mixed?
  E-commerce: Strong for payments, eventual for inventory
  Banking: Strong for balances, eventual for history
```

---

## Implementation Trade-Offs

**Strong (PostgreSQL, MySQL with replication):**
```
Write: 
  Primary: update
  Wait for replica ACK
  Return to client
  Cost: ~50ms for cross-region replication
```

**Eventual (Cassandra, DynamoDB):**
```
Write:
  Write to local replica
  Return to client immediately
  Background: Async replicate to others
  Cost: ~1ms (non-blocking)
  
Read:
  Read from closest replica (might be stale)
  Option: Quorum read (wait for majority, more accurate)
```

---

## Key Takeaways

1. **Strong = slow but correct** (ACID, locks)
2. **Eventual = fast but potentially stale** (eventual consistency)
3. **CAP = pick 2 of 3** (most pick availability + partition)
4. **Choose by use case** (payments → strong, social → eventual)
5. **Hybrid = use both** (strong for critical, eventual for non-critical)

---

## Q&A

**Q: Is strong consistency always better?**

No. It's slower. Use only when correctness is critical.

**Q: How long is "eventual"?**

Typically 1-5 seconds in practice. Can be optimized but adds complexity.

**Q: Can I detect stale reads in eventual consistency?**

Yes, add version numbers/timestamps. Check if read is older than expected.
