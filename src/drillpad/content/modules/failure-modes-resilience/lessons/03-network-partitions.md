# Network Partitions: Split Brain, Stale Reads, Divergent Data

## First Principle: Two DCs, One Fails

**Network partition:** Network link goes down between two datacenters. Each DC can operate independently, but they can't communicate.

```
Normal state:
  DC1 (primary) ←→ DC2 (secondary)
  Both sync, consistent view

Network partition (link down):
  DC1 (primary)     DC2 (secondary)
      X----- -----X
  
  Can't reach each other.
  Both accept writes independently.
  Data diverges.
```

---

## The Split Brain Problem

```
DC1 thinks: "DC2 is down, I'm the authority"
  Accepts writes: payment_1, payment_2, payment_3
  Total: $300

DC2 thinks: "DC1 is down, I'm the authority"
  Accepts writes: payment_4, payment_5
  Total: $200

Network partition heals.
  DC1 has: payment_1, payment_2, payment_3 ($300)
  DC2 has: payment_4, payment_5 ($200)
  
  Conflict: Which is source of truth?
  Result: Either lose $200 or lose $300 (data divergence)
```

---

## Detection & Resolution

**Without detection:**
- Partition heals
- Data has diverged
- Nobody notices
- Later: customer sees charge removed, or duplicate charge

**With detection:**
- Monitor link health: ping every 5s, alert if fails
- When partition detected: mark secondary as "unhealthy"
- Primary-only writes: direct all traffic to DC1
- On heal: reconcile (audit log both DCs, replay missing writes)

```
Timeline:

T=0: Network partition detected (ping timeout)
  Alert: "DC2 unreachable"
  Action: DC1 = primary, DC2 = read-only (stop accepting writes at DC2)

T=1-60: Partition heals (link comes back)
  Detect: Ping succeeds, DC2 is reachable
  Action: Reconciliation
    - DC1 writes (payment_1, payment_2, payment_3): $300
    - DC2 writes (payment_4, payment_5): $200
    - Merge: all 5 payments (or resolve conflicts)
    - Total: $500 (correct)

T=60+: System consistent again
```

---

## Consensus: Quorum Voting

**Best practice:** Don't pick one DC as authority. Use **quorum voting**.

```
System needs 3 nodes to achieve consensus (simple majority):
  DC1, DC2, DC3

Partition: DC1 can't reach DC2 and DC3

  DC1 isolated: "I lost quorum, I'm not authority"
    Action: DC1 goes read-only (no writes)
    
  DC2 + DC3 partitioned (together): "We have 2 out of 3, quorum!"
    Action: DC2 and DC3 continue (accept writes)
    
When DC1 rejoins:
  DC1 sees "DC2 and DC3 have quorum data"
  DC1 syncs from them
  System consistent
```

**Guarantee:** Quorum ensures only ONE partition can have authority. The other partition (if smaller) goes read-only.

---

## Stale Reads During Partition

Even without writes, partition causes stale reads.

```
Normal:
  Client reads from DC2 (secondary)
  DC2 is synced with DC1 (primary): read is fresh

Partition:
  Client reads from DC2
  DC2 hasn't heard from DC1 in 30s
  Data in DC2 is now stale (DC1 has newer data but can't share)
  Client gets stale answer

Example:
  Bank account: balance = $1000
  DC1 updated to: balance = $500 (withdrawal)
  Client reads from DC2: balance = $1000 (stale!)
  Client thinks they have $1000, but really have $500
  Later: reconciliation reveals over-withdrawal
```

---

## Prevention: Read-After-Write Consistency

```cpp
class PaymentSystem {
  // After writing to primary, read from primary
  
  void deposit(string account, int amount) {
    primary_db.write(account, amount);  // Write to primary
    
    // Now read from primary (not secondary)
    // Ensures you see your own write
    balance = primary_db.read(account);
    
    return balance;
  }
};
```

**Cost:** All reads go to primary (bottleneck), but consistency is guaranteed.

**Alternative:** Read from secondary, but add timestamp

```cpp
void deposit(string account, int amount) {
  write_timestamp = primary_db.write(account, amount);
  
  // Read from secondary, but only if it's synced past write_timestamp
  balance = secondary_db.read_if_synced_past(account, write_timestamp);
  
  if (balance == null) {
    // Secondary too stale, read from primary instead
    balance = primary_db.read(account);
  }
  
  return balance;
}
```

---

## Story Card: Payment System in Two DCs

**Setup:** AWS Marketplace Payment system across two DCs (primary DC and failover DC).

**Incident:** Network link between DCs goes down.

```
Timeline:

T=0: Link down, undetected (monitoring had 60s heartbeat)
  Payments come in, both DCs accept them
  Divergence grows

T=60: Monitoring alerts: "DC2 unreachable"
  But already 60 seconds of divergent writes
  
T=60-300: Operators try to fix
  Which DC has the "real" payments?
  Which is source of truth?
  
T=300: Link restored
  Divergence detected: DC1 has $5M, DC2 has $4.8M in payments
  Which payments are legitimate?
  
T=600: Manual reconciliation
  Audit log shows:
    DC1: payment_A, payment_B, payment_C (user X)
    DC2: payment_D, payment_E (user Y)
  Both are valid (different users)
  Merge both
  Total: $9.8M
  
  But: DC1 had payment_B twice (write-write conflict)
  Result: $200 unaccounted (manual investigation)
```

**Prevention (your fix):**
1. **Faster detection:** 5s heartbeat (vs 60s) — catch partition sooner
2. **Read-only on partition:** DC2 stops accepting writes when DC1 unreachable — prevents divergence
3. **Quorum-based:** Use 3 DCs (or 2 + witness) — ensure only one has authority
4. **Timestamp validation:** Reconciliation validates timestamps — identify conflicts
5. **Idempotency:** Every payment has idempotency key — can replay safely

**Result:** Partition recovery time: 5 minutes (automated reconciliation) vs 5 hours (manual).

---

## Q&A

**Recall 1:** What is split brain? Why is it bad?

*Must-say:*
- Split brain: two partitions each think they're authority
- Both accept writes → data diverges
- On heal: can't merge without losing some writes
- Solution: quorum voting (only one partition can have majority)

**Probe 1:** You have 2 DCs. Network partition occurs. How do you prevent divergent writes?

*Expected:*
- 2 DCs can't use quorum (no majority possible)
- Solution: Mark DC2 as "non-authoritative" during partition
- DC2 goes read-only
- On heal: DC2 syncs from DC1

**Numeric 1:** Partition lasts 5 minutes. During partition, DC1 gets 50 writes/sec, DC2 gets 10 writes/sec. How many conflicting writes on heal?

*Working:*
- DC1: 50 writes/sec * 300s = 15K writes
- DC2: 10 writes/sec * 300s = 3K writes
- Total writes: 18K
- No conflicts if you use idempotency keys + quorum (only DC1's writes are valid)
- If both are valid: 18K total writes (all must be reconciled)

---

## Questions for the Interviewer

- How many DCs does your system span? (2, 3, multi-region?)
- How do you handle network partitions? (quorum? primary/secondary?)
- What's your heartbeat interval? (5s, 60s?)
- Have you had a split-brain incident? (how long did it take to recover?)
