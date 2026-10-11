# Transactions & Isolation Levels

## Overview

Transactions provide ACID guarantees. This lesson covers:
1. What transactions do (atomicity, consistency, isolation)
2. Isolation levels (from weak to strong)
3. Real-world anomalies and how to prevent them
4. Performance trade-offs

---

## What is a Transaction?

A transaction is a group of operations that either all succeed or all fail.

```sql
BEGIN TRANSACTION;
  UPDATE accounts SET balance = balance - 100 WHERE id = 1;
  UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;  -- Both succeed or both fail
```

**Atomicity:** Either both updates happen or neither (never one without the other).
**Durability:** Once COMMIT succeeds, data is on disk (survives crashes).
**Consistency:** Account totals stay the same (no money created/destroyed).
**Isolation:** Concurrent transactions don't see each other's partial writes.

---

## Isolation Levels

Databases offer 4 isolation levels (weakest to strongest):

### 1. Read Uncommitted

```
Transaction A writes: salary = 50000
Transaction B reads: salary (sees 50000, even though A hasn't committed)
Transaction A rolls back: salary = 40000
Transaction B sees: 50000 (dirty read — read data that was rolled back)
```

**Problems:**
- Dirty reads (see uncommitted writes)
- Non-repeatable reads (same query returns different values)
- Phantom reads (rows appear/disappear)

**Use case:** Almost never. Too risky.

---

### 2. Read Committed

```
Transaction A writes: salary = 50000 (uncommitted)
Transaction B reads: salary = 40000 (old value, can't see uncommitted)
Transaction A commits: salary = 50000
Transaction B reads again: salary = 50000 (new value)
```

**Prevents:** Dirty reads

**Allows:**
- Non-repeatable reads (same query → different results if data changes between reads)
- Phantom reads (rows appear/disappear between reads)

**Use case:** Default in PostgreSQL, many DBs. Good for most workloads.

---

### 3. Repeatable Read

```
Transaction A reads user with id=1: age = 30
Transaction B updates user id=1: age = 31
Transaction A reads user id=1: age = 30 (still sees old value)
```

**Prevents:** Dirty reads + non-repeatable reads

**Allows:**
- Phantom reads (new rows inserted can appear)

**Example phantom:**
```
Transaction A: SELECT count(*) FROM users; → 1000
Transaction B: INSERT new user
Transaction A: SELECT count(*) FROM users; → 1001 (phantom)
```

**Use case:** Default in MySQL. Good for reading related data.

---

### 4. Serializable

```
Transaction A, B run concurrently as if they ran one after the other.

Order might be: A → B (or B → A)
Result: No anomalies at all
```

**Prevents:** All anomalies (dirty, non-repeatable, phantom)

**Cost:** Slowest. Each transaction might block others.

**Use case:** Critical transactions (financial, legal). Rarely used.

---

## Real-World Anomalies

### Non-Repeatable Read

```
User: Check bank balance twice in same session

Read 1: balance = $1000
(Friend transfers $100)
Read 2: balance = $900 (DIFFERENT!)

Fix: Repeatable Read isolation level
```

### Phantom Read

```
Report: Count all users created today

Read 1: SELECT count(*) → 100
(New user created)
Read 2: SELECT count(*) → 101 (row appeared!)

Fix: Serializable isolation level (but slow)
```

### Lost Update

```
Transaction A: Read count=5, update to 6
Transaction B: Read count=5, update to 6
Result: count=6 (lost B's update)

Fix: Use atomic operations or locks
```

---

## Choosing an Isolation Level

```
Financial transactions (payments, transfers)?
  → Serializable (correctness > speed)

Social media (likes, posts)?
  → Read Committed (fast, occasional stale reads OK)

Reports (analytics, historical data)?
  → Read Committed (old data is fine)

Multi-user editing (documents, code)?
  → Repeatable Read (see consistent snapshot)
```

---

## Locking vs MVCC

Two ways to implement isolation:

**Locking (traditional):**
```
Transaction A: Lock row 1
  Update row 1
  Release lock
Transaction B: Wait for lock on row 1
  Update row 1
  Release lock

Cost: Lock contention (B waits for A)
Benefit: Simple, strong isolation
```

**MVCC (Multi-Version Concurrency Control):**
```
Transaction A: Update row 1 → creates new version
  Row version 1 (old)
  Row version 2 (new, only visible to A)
Transaction B: Reads row 1
  Sees version 1 (old value)

Cost: Multiple versions in memory/storage
Benefit: No blocking (both read/write concurrently)
```

**Which is faster?**
- Read-heavy: MVCC wins (reads don't block writes)
- Write-heavy, low-contention: MVCC wins
- Write-heavy, high-contention: Locking might be simpler

---

## Real Example: Inventory Management

```
Product: "Widget", stock = 10

Scenario: 2 customers try to buy simultaneously

Without isolation:
  Customer A: Read stock=10, Decrement=9, Write
  Customer B: Read stock=10, Decrement=9, Write
  Result: stock=9 (sold 2, only 1 deducted, oversold)

With transaction (Repeatable Read):
  Customer A transaction:
    BEGIN
    Read stock=10 (locked)
    Decrement=9
    Write
    COMMIT
  Customer B transaction:
    BEGIN
    Read stock=9 (sees A's update)
    Decrement=8
    Write
    COMMIT
  Result: stock=8 (correct)
```

---

## Key Takeaways

1. **Read Committed** = default, good for most workloads
2. **Repeatable Read** = better for related reads
3. **Serializable** = best, but slow (avoid unless critical)
4. **Isolation costs performance** (choose what you need)
5. **MVCC** = modern approach (reads + writes concurrently)
6. **Test with your data** (contention patterns vary)

---

## Q&A

**Q: Should I use Serializable?**

Only if you have critical transactions. For 99% of apps, Repeatable Read is fine.

**Q: What's the performance cost of Serializable?**

10-100x slower than Read Committed (depends on contention). Profile first.

**Q: How do I detect isolation issues?**

- Non-repeatable read: Read same row twice, see different value
- Phantom: Run same SELECT twice, get different row count
- Lost update: Concurrent updates where one is overwritten

**Q: Can I use Read Committed for payments?**

Not safely. Payments need strong isolation (use Serializable or explicit locks).
