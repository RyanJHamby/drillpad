# Eventual Consistency: Variants, Guarantees, Pitfalls

## The Consistency Spectrum

**Strong Consistency (Slow, Reliable):**
Every read returns the latest write. Guaranteed.
Cost: Blocking on writes, coordination overhead.

**Eventual Consistency (Fast, Eventual):**
Reads might return stale data. Eventually all replicas agree.
Cost: Temporary inconsistency, complex client logic.

**Weak Consistency (Very Fast, Tricky):**
No guarantees. Data converges... maybe.
Cost: Applications must handle conflicts manually.

Eventual consistency is the middle ground: fast + eventual guarantee.

## How Eventual Consistency Works

```
Replica 1: balance = 100
Replica 2: balance = 100

User updates balance to 150 on Replica 1.

Time 0ms:   Replica 1: 150  |  Replica 2: 100 (stale)
Time 10ms:  Replica 1: 150  |  Replica 2: 150 (synced)
Time 20ms:  Replica 1: 150  |  Replica 2: 150 (consistent)
```

**Guarantee:** Given enough time (and no new writes), all replicas converge to the same value.

**No guarantee:** At any moment, replicas might disagree.

## Eventual Consistency Variants

### Variant 1: Causal Consistency

Maintains causality: if event A happens before event B, all replicas see A before B.

```
User writes message 1
User writes message 2

Thread 1 reads messages:
  [1] →   (sees message 1)
  [1, 2] → (sees both, in order)

NOT possible: [2] then [1] (causal order violated)
```

**Cost:** Slightly more overhead than eventual, but prevents causality violations.

### Variant 2: Read-Your-Write Consistency

After you write, your own reads will see the write.

```
User (at replica A) writes balance = 100
User (at replica A) reads → sees 100

Other users (at replica B) might see 99 (stale)
But the original user always sees their own write
```

**Cost:** Route user's reads to the replica that has their writes.

### Variant 3: Monotonic Reads

If you read version V, future reads are ≥ V (never go backward).

```
At time T1: User reads version 5
At time T2: User reads version 7 (or later, not 3)

NOT possible: read version 5, then read version 3 (time traveling)
```

**Cost:** Pin user to a primary replica (or track causality).

## Pitfall 1: Stale Read After Write

```cpp
// User writes:
db.set("balance", 150);

// User immediately reads:
int balance = db.get("balance");
// Might return 100 (stale) if read went to different replica
```

**Problem:** Write went to replica A, read went to replica B.

**Fix: Read-your-write consistency**
```cpp
db.set("balance", 150, node=A);
int balance = db.get("balance", node=A);  // Read from same node
```

## Pitfall 2: Conflicting Concurrent Writes

```
User 1 writes balance = 150 to Replica A
User 2 writes balance = 120 to Replica B

Time 10ms: Replica A: 150  |  Replica B: 120
Time 20ms: Replica A: ?    |  Replica B: ?  (conflict!)

What's the correct value? 150 or 120?
```

**Solution: Conflict Resolution**

**Option 1: Last-write-wins**
```
Timestamp User 1: T1=10ms, value=150
Timestamp User 2: T2=12ms, value=120

Replica A: sees T2 > T1, adopts 120
Replica B: sees T2 > T1, adopts 120
Final: 120
```
**Downside:** Silently loses one write (User 1 doesn't know their write lost)

**Option 2: Application-level resolution**
```
Replica A and B both keep: {T1=10ms: 150, T2=12ms: 120}
Application code decides: "use max(150, 120) = 150"
Or: "ask user which is correct"
```

**Option 3: Strong consistency for critical data**
```
Balance is money, can't be wrong. Use strong consistency (lock + write).
Likes count is not critical. Use eventual consistency.
```

## Pitfall 3: Durability Violation

```cpp
db.write("balance", 150);  // Write returns immediately
// Replica A has 150
// But not yet replicated to B or C

Server crashes before replication → 150 is lost
```

**Fix: Write quorum**
```cpp
// Wait for write to hit N out of M replicas before returning
db.write("balance", 150, quorum=2);  // Wait for 2/3 replicas
// Now 150 is durable (would need 2+ failures to lose it)
```

## Interview Pattern: Eventual Consistency Trade-offs

```
Q: "Your service has data in multiple regions.
   Writes to US, reads from both US and EU.
   EU reads might be 100ms behind. OK?"

Weak answer:
  "Yes, we'll just accept stale reads"
  (❌ Doesn't account for application impact)

Strong answer:
  "Depends on the data:
  
  1. Classify by impact of staleness:
     - User's own profile: STALE IS BAD (read-your-write)
     - Friend list: STALE IS OK (eventual is fine)
     - Leaderboard: STALE IS OK (people expect lag)
  
  2. For user's own profile (must see own writes):
     - Option A: Read-your-write: route to home region
       Cost: extra latency if away from home
     - Option B: Strong consistency: quorum write + read
       Cost: slower writes, more coordination
     - Option C: Embrace stale + show version: 
       Cost: UI complexity, but faster reads
  
  3. For friend list (eventual is OK):
     - Read from EU, might be 100ms stale
     - Eventually consistent
     - Cost: none
  
  4. For leaderboard (eventual is preferred):
     - Read from EU immediately
     - Stale is expected and acceptable
     - Cost: none
  
  5. Monitoring:
     - Track replica lag (EU replication latency)
     - Alert if lag > 1 second
     - If lag grows, investigate: network, database, load"

Why this signals good judgment:
  - You didn't blanket-apply eventual consistency
  - You classified data by criticality
  - You chose different strategies per data type
  - You understood the cost of each strategy
```

## When Eventual Consistency Is Right

| Use Case | Consistency | Why |
|---|---|---|
| **User's own data** | Read-your-write or strong | Writes shouldn't disappear |
| **Leaderboards** | Eventual | Lag is expected |
| **Analytics** | Eventual | Approximate is fine |
| **Money transfers** | Strong | Can't be wrong |
| **Social media feeds** | Eventual | Slightly stale is OK |

## What This Signals

- You understand the spectrum (eventual is not binary)
- You can classify data by criticality
- You know conflict resolution is hard (last-write-wins loses data)
- You think about durability + consistency together
