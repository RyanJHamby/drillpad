# Write-Ahead Logging & MVCC: Consistency Without Blocking

## Overview

ACID databases use two key mechanisms to achieve correctness without sacrificing concurrency:

1. **Write-Ahead Logging (WAL):** Durability guarantee (the D in ACID)
2. **Multi-Version Concurrency Control (MVCC):** Isolation without locks (the I in ACID)

This lesson covers:
- Why WAL is mandatory (crash recovery)
- How WAL avoids data corruption
- MVCC version snapshots and read consistency
- Garbage collection of old versions
- Real costs in PostgreSQL and MySQL

---

## The Problem: Durability Without WAL

Imagine a database crash during a write:

```
Scenario: Transfer $100 from account A to account B

Step 1: Read balance A (current: $1000)
Step 2: Calculate new balance A ($900)
Step 3: Update A in memory (buffer cache)
Step 4: Read balance B (current: $500)
Step 5: Calculate new balance B ($600)
Step 6: Update B in memory (buffer cache)

CRASH HERE (before flush to disk)

Restart:
  A on disk: $1000 (buffer cache lost)
  B on disk: $500 (buffer cache lost)
  Money lost! ($100 disappeared)

OR worse:
  A on disk: $900 (somehow persisted)
  B on disk: $500 (didn't persist)
  Money created! (duplicate $100)
```

**Solution: Write-Ahead Logging (WAL)**

Before updating the actual data file, write to a log file:

```
Step 1-2: Read balances, calculate
Step 3: WRITE LOG: "Transfer A→B, $100"
  (commit log entry to disk, 4KB write = ~1ms)
Step 4: Update A in memory
Step 5: Update B in memory
Step 6: Flush data to disk (maybe async, happens later)

CRASH HERE

Restart:
  Check WAL (uncommitted entries = roll back, committed entries = replay)
  If log says "Transfer A→B $100 COMMITTED": re-apply to data files
  Restart is safe, no data loss
```

---

## Write-Ahead Logging: How It Works

**Protocol (standard for all ACID databases):**

```
Transaction T1:
  BEGIN
  INSERT user_id=100, name="Alice"
  
  WAL entry: [LSN=1001, txn_id=T1, op=INSERT, table=users, values=(100, "Alice")]
  
  Flush WAL to disk (durable)
  
  COMMIT
  
  Update data page in buffer cache
  (data page flush to disk happens asynchronously, minutes later)

Transaction T2:
  BEGIN
  UPDATE users SET name="Bob" WHERE user_id=100
  
  (T2 sees "Alice" in buffer cache, waiting for async flush)
  
  WAL entry: [LSN=1002, txn_id=T2, op=UPDATE, table=users, old="Alice", new="Bob"]
  
  Flush WAL to disk
  
  COMMIT
```

**Cost of WAL:**

```
Each COMMIT requires:
  1. Serialize transaction changes
  2. Write WAL entry to log (sequential write to disk)
  3. fsync() = forced flush to disk (expensive)
  
Typical fsync cost: 1-10ms per COMMIT
  At 1000 COMMITS/sec = 1000 × 10ms = 10,000ms overhead (bottleneck)

Optimization: Group commit
  Batch 100 COMMITs into 1 fsync
  1 fsync = ~1ms
  100 COMMITs amortized: 1ms / 100 = 0.01ms per COMMIT
```

**WAL in PostgreSQL:**

```
WAL file: pg_wal/000000010000000000000001
  - 16MB file (default)
  - Contains sequential LSNs (Log Sequence Numbers)
  
After COMMIT:
  1. Write WAL record (~200 bytes)
  2. fsync(wal_fd) to disk
  3. Return success to client
  
Async:
  - Background writer flushes dirty pages to data files
  - Recovery process replays WAL on startup
```

---

## Multi-Version Concurrency Control (MVCC)

**Problem: Isolation without blocking**

```
Transaction A: SELECT * FROM users
Transaction B: DELETE FROM users WHERE id=100

Old approach (pessimistic locking):
  A acquires READ lock on table
  B wants WRITE lock, waits for A (blocked)
  A finishes, releases lock
  B acquires lock, deletes
  
Problem: B is blocked during A's long query (30 seconds)
Performance: Low, lots of blocking
```

**MVCC solution: Keep multiple versions**

```
Time 0: Version 1 of user_id=100, name="Alice"
        Create timestamp = 1
        Delete timestamp = ∞

Transaction A:
  BEGIN (snapshot timestamp = 5)
  SELECT * FROM users
  → See version 1 (create=1, delete=∞)

Transaction B:
  DELETE FROM users WHERE id=100
  Version 1 now has delete timestamp = 7
  Create new tombstone version 2 (create=7, delete=∞)

Time 10: Version 1 of user_id=100, name="Alice"
         Create timestamp = 1
         Delete timestamp = 7 (deleted by txn B)
        Version 2 tombstone (create=7, delete=∞)

Transaction A continues:
  SELECT * FROM users
  → Still see version 1 (because snapshot=5, delete timestamp=7 is in future)
  → Consistent view!

Transaction C (new transaction, snapshot timestamp = 9):
  SELECT * FROM users
  → Version 1 has delete=7 < snapshot=9 → not visible
  → Version 2 is tombstone → not visible
  → Empty result set (user deleted)
```

**Key insight: Each transaction gets a consistent snapshot**

```
Snapshot = (txn_id, txn_start_time)

Row visibility rule (for each row version):
  visible = (create_txn ≤ snapshot_txn) AND 
            (delete_txn > snapshot_txn OR delete_txn = ∞)
```

**Real example (PostgreSQL MVCC):**

```
Table: orders (order_id, customer_id, amount)

Time 0:
  Order 101: (cmin=NULL, cmax=∞)  → T1 creates
  Committed in T1

Time 1:
  T2 updates Amount 101: 100 → 200
  Order 101 old version: (cmin=NULL, cmax=T2)  → T2 deletes old
  Order 101 new version: (cmin=T2, cmax=∞)     → T2 creates new
  Committed in T2

Time 2:
  T3 (snapshot before T2) reads Order 101
  → Sees old version (cmax=T2, which is in future for T3)
  → Amount = 100

  T4 (snapshot after T2) reads Order 101
  → Sees new version (cmin=T2, visible for T4)
  → Amount = 200
  
No lock contention, reads don't block updates!
```

---

## Garbage Collection: The Cost of MVCC

**Problem: Old versions accumulate**

```
Transaction A: BEGIN (snapshot=0)
  long-running query, reads Version 1 of order_id=100

Meanwhile:
  T1 updates order_id=100 (amount: 100 → 110)
  T2 updates order_id=100 (amount: 110 → 120)
  T3 updates order_id=100 (amount: 120 → 130)
  ...
  T1000 updates order_id=100 (amount: 990 → 1000)

Now we have 1000 versions of order_id=100 on disk:
  - Version 1 (delete_txn=T1): still visible to Transaction A!
  - Version 2 (delete_txn=T2): not visible to A, but needed until A finishes
  - ...
  - Version 1000 (active)

If A runs for 1 hour:
  1000 versions = 1000 × 100 bytes = 100KB per row
  Table space grows 1000x until A finishes
  Disk space bloat
```

**Garbage collection rules:**

```
A version can be deleted from disk when:
  delete_txn < oldest_active_snapshot

Oldest active snapshot = minimum snapshot timestamp of all running transactions

Example:
  T5 (snapshot=5) still running
  T8 (snapshot=8) finished
  T10 (snapshot=10) finished
  
  Oldest active = 5
  
  Can delete versions with delete_txn <= 4
  Cannot delete versions with delete_txn >= 5 (T5 might need them)
```

**PostgreSQL VACUUM process:**

```
Background process that:
  1. Scans all tables
  2. Marks dead versions (delete_txn < oldest_snapshot)
  3. Reclaims space
  
Cost: Sequential scan of all pages + marks work = heavy I/O
  On large tables: VACUUM can take hours

During VACUUM:
  Some overhead to readers (but not blocking)
```

**Real impact: Long-running transactions are expensive**

```
System with 1M inserts/sec, 1GB/sec write bandwidth

Long-running read transaction (SELECT *, 1 minute):
  During 1 minute, system writes: 60 sec × 1GB/sec = 60GB of updates
  MVCC versions pile up: old versions can't be garbage collected
  Table bloat: 60GB of old versions accumulate on disk
  Disk space explosion + slower reads (more versions to skip)
  
Fix: Commit transactions quickly, or use READ-ONLY snapshot isolation
```

---

## MVCC with Transactions: Isolation Levels

**Read Committed (default, weak isolation):**

```
Transaction A:
  SELECT balance FROM accounts WHERE id=1  → $1000 (snapshot S1)
  (gap)
  SELECT balance FROM accounts WHERE id=1  → $900 (snapshot S2)
  
Between the two SELECTs, another transaction updated the account
Non-repeatable read!

MVCC: Each statement gets a new snapshot
```

**Repeatable Read (stronger isolation):**

```
Transaction A:
  BEGIN (snapshot S)
  SELECT balance FROM accounts WHERE id=1  → $1000
  (gap)
  SELECT balance FROM accounts WHERE id=1  → $1000 (same snapshot S)
  
All statements see the same snapshot
Repeatable: no phantom reads within the transaction
```

**Serializable (strongest isolation):**

```
Transaction A and B run concurrently
MVCC + conflict detection:
  If A reads X and B writes X: conflict
  If A writes X and B reads X: conflict
  If A writes X and B writes X: conflict
  
On conflict: one transaction aborts and retries
Cost: expensive (extra bookkeeping)
```

---

## Q&A

**Q1: Why does WAL use fsync() which is so slow?**

A: "fsync() forces OS to physically write data to disk (durable). Without it, data sits in OS buffer cache, and a power loss loses uncommitted data. fsync is slow (~1-10ms), but necessary for ACID compliance. Solution: group commit (batch 100 fsync calls into 1)."

**Q2: Can MVCC cause read anomalies?**

A: "Yes, under READ-COMMITTED isolation. Each statement sees a new snapshot, so a transaction can see different values for the same row. Solution: use REPEATABLE-READ or SERIALIZABLE, but they're slower (more bookkeeping)."

**Q3: How do you handle a situation where versions accumulate faster than VACUUM can clean them?**

A: "1) Commit transactions faster (don't hold long-running reads). 2) Run VACUUM more frequently (increase autovacuum aggressiveness). 3) Shard data so VACUUM runs faster per partition. 4) Use connection pooling to reuse connections (fewer active snapshots)."

**Q4: Does MVCC use more disk space?**

A: "Yes, old versions stay on disk until garbage collected. In steady state with few updates, overhead is low. During heavy update workloads with long-running reads, space can bloat 10-100x. Trade-off: lock-free (MVCC) vs space-efficient (pessimistic locking)."

**Q5: How is MVCC different between PostgreSQL and MySQL?**

A: "PostgreSQL: MVCC via tuple versioning (cmin/cmax, xmin/xmax). Each row version stored separately. MySQL InnoDB: MVCC via undo logs (separate log of old versions, linked). Both achieve same isolation, slightly different performance trade-offs."

---

## Real Example: Order Processing Failure

```
Setup: Payment processing system, 10K payments/sec

Scenario:
  T1: INSERT payment (committed, WAL flushed)
  Database crashes (before data page flushed)
  Restart:
    Check WAL
    Find INSERT in WAL, not yet in data file
    Replay INSERT
    Consistency maintained ✓

Second scenario (MVCC):
  T1: INSERT payment, amount=$100
  T2: SELECT SUM(amount) FROM payments  (snapshot S2, sees T1)
  T3: UPDATE payment SET amount=$200 WHERE id=1
  T4: SELECT SUM(amount) FROM payments  (snapshot S4, sees T3's update)
  
  Both T2 and T4 see consistent snapshots
  No lock contention, high throughput
```

---

## Key Takeaways

1. **WAL is mandatory for durability** (crash recovery)
2. **fsync cost: 1-10ms per COMMIT**, critical bottleneck
3. **Group commit** amortizes fsync cost (100x speedup)
4. **MVCC enables lock-free reads** (readers don't block writers)
5. **Old versions accumulate** until garbage collected
6. **Long-running transactions = bloat** (versions can't be freed)
7. **Isolation levels trade consistency vs performance**

---

## Checklist

- [ ] Understand why WAL is needed (crash recovery)
- [ ] Can explain what happens during fsync() and why it's slow
- [ ] Understand MVCC snapshot = transaction gets consistent view
- [ ] Know row visibility rule (cmin/cmax or xmin/xmax)
- [ ] Understand garbage collection and old version cleanup
- [ ] Know the cost of long-running transactions (space bloat)
- [ ] Can compare READ-COMMITTED vs REPEATABLE-READ vs SERIALIZABLE

## Common Wrong Answers

- "WAL slows down every write" ← Partially true, but group commit reduces cost
- "MVCC has no overhead" ← Wrong, old versions consume disk space
- "Garbage collection is automatic and free" ← Wrong, VACUUM is expensive I/O
- "Long-running transactions don't hurt performance" ← Wrong, they block version cleanup
- "Isolation levels don't affect performance" ← Wrong, SERIALIZABLE has overhead
