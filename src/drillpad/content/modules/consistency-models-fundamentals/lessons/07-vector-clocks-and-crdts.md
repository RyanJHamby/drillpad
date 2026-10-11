# Vector Clocks & CRDTs: Causality Without Consensus

## The Problem: Distributed Causality

Logical clocks tell you: "Event A happened before Event B."

But with network delays and no central authority, how do you know?

```
User 1: sends message "hello"
User 2: sends message "reply"

Question: did User 1's message arrive before User 2 sent reply?

With local timestamps:
  User 1: T=10:00:00
  User 2: T=10:00:01
  Looks like yes, User 1 → User 2

But what if clocks are unsynchronized?
  User 1's clock is 5 minutes behind
  User 2's clock is 5 minutes ahead
  Order might be reversed (we can't trust wall-clock time)
```

**Vector clocks** solve this by tracking causality without synchronized clocks.

## Vector Clocks: How They Work

Each node maintains a counter per node.

```
Node A's clock: [A: 3, B: 2, C: 0]
              = "I've seen 3 of my own events, 2 from B, 0 from C"

Node B's clock: [A: 1, B: 5, C: 2]
              = "I've seen 1 from A, 5 of my own, 2 from C"
```

**Rule 1: On local event, increment your own counter**

```
Node A sends a message:
  Before: [A: 3, B: 2, C: 0]
  After:  [A: 4, B: 2, C: 0]  ← increment A's counter
```

**Rule 2: When sending a message, include your clock**

```
A sends to B: (message, clock=[A: 4, B: 2, C: 0])
```

**Rule 3: On receiving, update your clock to max of (yours, sender's), then increment own**

```
B receives from A with clock [A: 4, B: 2, C: 0]:
  B's clock before: [A: 1, B: 5, C: 2]
  
  Take element-wise max:
    A: max(1, 4) = 4
    B: max(5, 2) = 5
    C: max(2, 0) = 2
  Result: [A: 4, B: 5, C: 2]
  
  Increment own (B):
  Final: [A: 4, B: 6, C: 2]
```

## Causality Guarantees

Two events E1 and E2:
- If E1 happened before E2, then E1.clock < E2.clock (element-wise)
- If E1.clock and E2.clock are incomparable, then E1 and E2 are concurrent

```
Event E1: clock = [A: 2, B: 3, C: 1]
Event E2: clock = [A: 3, B: 2, C: 1]

Is E1 < E2?
  A: 2 < 3 ✓
  B: 3 < 2 ✗ (E2 is smaller here)
  C: 1 = 1 ✓

NO, they're not comparable. E1 and E2 are concurrent.
```

## Causal Order Delivery

Applications can use vector clocks to enforce "causal reads":

```
User 1 writes: "Hello" (VC=[1, 0])
User 1 reads: Sees "Hello"

User 2 reads: Should only see data with VC <= [1, 0]
             If received update with VC=[1, 1], must wait

Result: User 2 sees User 1's write before any later messages
```

## CRDTs: Conflict-free Replicated Data Types

CRDTs are data structures designed so replicas can diverge and then **merge safely**.

Unlike consensus (all nodes agree), CRDTs allow temporary disagreement that resolves via deterministic merge.

### Example 1: Add-Only Set (CRDT)

```
Replica A:
  Set = {apple, banana}
  VC_A = [2, 0]

Replica B:
  Set = {apple, cherry}
  VC_B = [0, 2]

They diverged. Who's right?

Merge rule: Union of sets
  Result = {apple, banana, cherry}

Both agree on merged state.
Both can continue with {apple, banana, cherry}

Why it works: Adding is idempotent (add twice = add once)
Can't conflict (set only grows)
```

### Example 2: LWW Register (Last-Write-Wins)

```
Replica A: register = 100 (timestamp T1=10:00:00)
Replica B: register = 200 (timestamp T2=10:00:05)

Merge rule: pick value with higher timestamp
  Result = 200 (T2 > T1)

Both converge to 200.

Downside: T1 is silently lost
(assumes clocks are close enough to be meaningful)
```

### Example 3: Counter CRDT

Traditional problem:
```
Replica A: count = 5 (I incremented 5 times)
Replica B: count = 3 (I incremented 3 times)

Non-CRDT merge: count = max(5, 3) = 5? or 8?
If you pick 5, you lose B's increments!
If you pick 8, you might double-count A's increments!
```

CRDT counter solution:
```
Replica A: {A: 5, B: 0} meaning "A incremented 5 times, B 0 times"
Replica B: {A: 0, B: 3} meaning "A 0 times, B 3 times"

Merge: {A: max(5, 0)=5, B: max(0, 3)=3}
       = {A: 5, B: 3}

Total = 5 + 3 = 8

Why it works: Each node increments its own counter
             Merge takes max per node
             Total is always sum of individual counters
             No double-counting, no lost increments
```

## Comparison: Vector Clocks vs CRDTs

| Property | Vector Clocks | CRDTs |
|----------|---------------|-------|
| **Purpose** | Track causality | Enable conflict-free merges |
| **Consensus needed?** | NO | NO |
| **Merge algorithm** | None (detect causality) | Yes (deterministic) |
| **Conflicts resolved** | Detected (not solved) | Automatically (per CRDT rules) |
| **Examples** | Causal ordering | Sets, counters, registers, maps |
| **Latency** | Zero (no coordination) | Zero (no coordination) |
| **Cost** | O(N) space per event (N nodes) | Depends on CRDT type |

## Diagrams

### Vector Clock Timeline

```
Timeline: Three nodes A, B, C communicating

A: [A:1, B:0, C:0]
   ↓ (local event)
A: [A:2, B:0, C:0]
   ↓ (send to B with VC)
   
B: [A:0, B:1, C:0]
   ← receives [A:2, B:0, C:0] from A
   max([0,1,0], [2,0,0]) = [2,1,0]
   ↓ (increment own)
B: [A:2, B:2, C:0]
   ↓ (send to C with VC)
   
C: [A:0, B:0, C:1]
   ← receives [A:2, B:2, C:0] from B
   max([0,0,1], [2,2,0]) = [2,2,1]
   ↓ (increment own)
C: [A:2, B:2, C:2]

Result: A → B → C causal chain is preserved in VC
```

### CRDT Merge Example (Add-Only Set)

```
Initial state:
  Replica A: {apple}
  Replica B: {apple}

T1: A adds banana
  A: {apple, banana}
  B: {apple}

T2: B adds cherry
  A: {apple, banana}
  B: {apple, cherry}

T3: Replicas sync (network)
  A sends its state to B
  B sends its state to A

Merge at A:
  Local: {apple, banana}
  Remote (from B): {apple, cherry}
  Merge rule (union): {apple, banana, cherry}

Merge at B:
  Local: {apple, cherry}
  Remote (from A): {apple, banana}
  Merge rule (union): {apple, banana, cherry}

Result:
  A: {apple, banana, cherry}
  B: {apple, banana, cherry}
  
Converged safely, no conflicts!
```

### Causal Consistency Violation Prevention

```
Scenario: Comment thread

User A posts: "Great talk!" (VC=[A:1])
User B reads comment
User B replies: "Yes, totally agree" (VC=[A:1, B:1])

Now replicate to User A:
  A's local VC=[A:1]
  Receives reply with VC=[A:1, B:1]
  
  A: replies to what? To original comment (VC=[A:1])
     VC of that comment: [A:1, B:0]
     
  Can show causality:
    Comment VC=[A:1, B:0] < Reply VC=[A:1, B:1]
    So Comment came before Reply ✓
    
Without VC, A couldn't tell:
  "Did B see my comment before replying?"
  Timestamps would be ambiguous if clocks drift
```

## Interview Section

### Q1: How do vector clocks handle concurrent events?

**Weak answer:** "They detect them."

**Strong answer:**
"Vector clocks detect causality: if E1 → E2 (causally), then VC(E1) < VC(E2).

Concurrent events have incomparable vector clocks:
  E1 VC = [2, 1, 0]
  E2 VC = [1, 2, 0]
  
  E1[A]=2 > E2[A]=1 (E1 is ahead at A)
  E1[B]=1 < E2[B]=2 (E1 is behind at B)
  
  Neither is strictly less than the other → Concurrent.

What can we do?
  Option 1: Accept both (no conflict expected, like sets)
  Option 2: Application chooses (merge conflict)
  Option 3: Use CRDT to auto-merge
  Option 4: Re-order using total clock (add timestamp for tie-breaking)

Pure vector clocks don't resolve conflicts, only detect causality."

### Q2: Why do CRDTs avoid consensus?

**Weak answer:** "Because they don't need to agree."

**Strong answer:**
"Consensus requires all nodes to decide on one value (cost: coordination).

CRDTs design the merge function so replicas can diverge and auto-merge:

Example: Counter CRDT
  A increments to 5, B increments to 3
  Merge: {A: 5, B: 3} → total = 8
  
  No coordination needed. Each node increments its own slot.
  Merge is deterministic (max per node, then sum).
  
Why it works:
  Operations commute (A's increment + B's increment = B's + A's)
  Merge is deterministic and idempotent
  Replicas converge to same value

Cost: not all data types are CRDTs
  Queues (order matters) → hard
  Stacks → hard
  Counters → easy
  Sets → easy
  Maps → medium (depends on merge strategy)

Consensus would be cheaper for non-commutative operations, but requires coordination."

### Q3: Can you use vector clocks to implement causal consistency?

**Weak answer:** "Yes, by tracking causality."

**Strong answer:**
"Vector clocks track causality, but you also need a delivery mechanism.

Implementation:
  1. Each write includes VC
  2. Each read includes VC of data user has seen
  3. On read, wait until replica has all writes causally before the read

Example:
  User writes to A: VC_write = [1, 0]
  User reads from B: B's VC = [0, 0] (B hasn't seen write yet)
  
  Read blocks until B's VC >= [1, 0]
  Then B replicates write from A
  B's VC becomes [1, 0]
  Read unblocks, sees the write

Cost: reads may block [VERIFY] (~10-100ms per blocked read)

Alternative: Paxos or other consensus
  Pros: reads never block
  Cons: requires quorum coordination

Trade-off: latency (VC eventual) vs consistency (consensus strict)"

### Q4: What's the space overhead of vector clocks?

**Weak answer:** "O(N) where N is number of nodes."

**Strong answer:**
"Each event carries a vector of size N (one counter per node).

With 5 nodes:
  VC = [A:100, B:50, C:200, D:30, E:10]
  Space per event: 5 * 64 bits = 40 bytes
  
Per million events: 40 MB

For comparison:
  Single logical clock: 8 bytes per event
  Timestamp: 8 bytes (microsecond precision)
  
Vector clock is 5x more expensive than single clock.

Optimization: Interval Tree Clocks (ITC)
  [VERIFY] Uses dynamic trees instead of vectors
  [VERIFY] Space: O(log N) in practice
  
  Not commonly used (complexity not worth 5x savings)

Modern systems:
  Hybrid approach: vector clocks in metadata, not on every data item
  E.g., Dynamo uses version vectors (like VC) but only on object metadata, not events"

### Q5: Numeric Exercise: CRDT Counter Performance

You have 3 replicas. Each increments a counter 1000 times/sec locally.

Without CRDT (consensus required):
  Throughput per replica: ~100 ops/sec (limited by consensus latency)
  [VERIFY] Consensus latency: ~10ms
  Total across 3 replicas: 300 ops/sec

With CRDT counter:
  Throughput per replica: 1000 ops/sec (no coordination)
  Total across 3 replicas: 3000 ops/sec
  
  At merge (every 1 sec): 3 replicas exchange {A: 1000, B: 1000, C: 1000}
  
Performance gain: 10x (3000 vs 300 ops/sec)

Cost: merge latency (eventual consistency)
  [VERIFY] Replication delay: ~10-100ms
  Counter value is eventually correct within 100ms

Trade-off: 10x throughput for 100ms eventual consistency
  Good for distributed counters, bad for financial transactions"

## When to Use / When NOT

| Scenario | Vector Clocks? | CRDTs? |
|----------|---------------|--------|
| Detect causality | YES | Maybe |
| Enforce causal reads | YES + blocking | - |
| Conflict-free sets | - | YES |
| Conflict-free counters | - | YES |
| Conflict-free queues | NO | NO (hard) |
| Financial transactions | NO | NO (use consensus) |
| Real-time collaborative editing | Maybe | YES (better) |
| Eventually consistent chat | YES | YES (combined) |
| Replicated state machine | NO | NO (use Paxos/Raft) |

## Checklist: Vector Clocks Correctness

- [ ] On local event, does own counter increment?
- [ ] On message send, does VC get included?
- [ ] On receive, does VC get element-wise max then increment own?
- [ ] Can you compare two VCs to detect causality?
- [ ] Are concurrent events properly detected (incomparable)?
- [ ] Does causal ordering match user expectations?
- [ ] Is VC overhead acceptable (O(N) space)?

## Checklist: CRDT Correctness

- [ ] Is merge function deterministic?
- [ ] Is merge idempotent (merge(a,a) = a)?
- [ ] Does merge commute (merge(a,b) = merge(b,a))?
- [ ] Are replicas guaranteed to converge?
- [ ] Can operations be applied out of order?
- [ ] Are conflicts actually eliminated (not just detected)?

## Common Wrong Answers

1. "Vector clocks solve conflicts." → NO, they detect causality only.
2. "CRDTs are slower than consensus." → NO, zero coordination overhead.
3. "CRDTs work for any data type." → NO, limited to commutative operations.
4. "Vector clocks prevent split brain." → NO, they just track causality.
5. "Add vector clocks to consensus to make it stronger." → NO, unnecessary.
6. "Merge with max(VC1, VC2) always works." → NO, need CRDT-specific merge rules.
7. "Concurrent events must be resolved by user." → Maybe, depends on CRDT type.
