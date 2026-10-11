# Paxos & Multi-Paxos: Consensus for Replicated State Machines

## Why Paxos Matters

You have N servers. They must agree on a value (or a sequence of values).

**The Hard Part:** Servers can crash, network can partition, messages can be delayed or lost.

Paxos is the algorithm that solves this. It's used in:
- Google Chubby (lock service backing BigTable)
- Apache Zookeeper (distributed coordination)
- Amazon DynamoDB (metadata consensus)
- etcd (Kubernetes cluster state)

Most distributed systems that claim "strong consistency" use Paxos or Raft (a simpler variant).

## The Paxos Problem

Given:
- N servers (some may crash)
- Each server can propose a value
- Network can partition or delay messages

Find: An algorithm where:
1. A single value is chosen (safety: no two different values chosen)
2. If a value is chosen, processes eventually learn it (liveness)
3. Works even if F servers crash (as long as F < N/2)

## Paxos Roles & Phases

Three roles: **Proposer, Acceptor, Learner**

```
Proposer:         Acceptor:         Learner:
(wants to vote)   (holds ballots)   (learns consensus)
   |                   |                 |
   +---Propose(v)------>|                |
   |                   |--Ack----------->|
   |<---Promise(v)-----|                |
   |                                    |
```

### Phase 1: Prepare (Proposer gets permission)

Proposer sends: `Prepare(proposal_id)`

Acceptor response:
- If this is the highest proposal_id I've seen, promise not to accept lower proposal_ids
- Return the highest value I've already accepted (if any)

```
Proposer p1:
  "Can I propose? Here's my ballot number: 5"

Acceptor A1:
  "OK, I promise not to accept ballots < 5.
   The last value I accepted was: value=100 (from ballot 3)"

Proposer p1:
  "Good! I learned that someone already got 100 in.
   I should propose 100 to be safe."
```

### Phase 2: Accept (Proposer asks for votes)

Proposer sends: `Accept(proposal_id, value)`

Acceptor response:
- If this proposal_id >= my promised ballot, accept it
- Broadcast to all learners

```
Proposer p1:
  "Accept: proposal_id=5, value=100"

Acceptor A1, A2, A3:
  "Accepted!"

Learner:
  "3 acceptors agreed on 100. Quorum reached. Consensus!"
```

## Quorum: The Key Insight

With N acceptors, you need **majority (N/2 + 1)** to agree.

Why? Because any two majorities overlap.

```
With 5 acceptors (need 3):
Majority 1: {A1, A2, A3}
Majority 2: {A3, A4, A5}

Overlap: A3 (always exists)
So if Majority 1 committed value V,
Majority 2 will learn V from A3
```

**Safety guarantee:** At most one value can be chosen.

## Multi-Paxos: Consensus on Sequences

Basic Paxos agrees on ONE value. But replicated state machines need a SEQUENCE of values.

Option 1: Run Paxos N times (one per value)
- ❌ Too slow: each value takes 2 rounds

Option 2: Multi-Paxos (smart leader)
```
Round 1:
  Propose value V1
  Quorum accepts
  Learners see V1

Round 2:
  Propose value V2
  Quorum accepts
  Learners see V2
```

With a **stable leader**, Phase 1 (prepare) happens once. Phase 2 repeats.

```
Leader p1:
  "Can I be leader? Ballot 10"

Acceptors:
  "Yes, ballot 10 is highest"

Leader p1:
  "Accept slot=1, value=V1"   (Phase 2 only)
  "Accept slot=2, value=V2"   (Phase 2 only)
  "Accept slot=3, value=V3"   (Phase 2 only)
  ...
```

**Speed improvement:** From 2 RTT per value to 1 RTT per value (after initial prepare).

## Failure Recovery: What if Leader Dies?

New proposer starts:
1. Sends `Prepare(ballot=11)` (higher than 10)
2. Acceptors respond with last accepted values (V1, V2, V3, ...)
3. New leader knows the sequence history
4. Continues from slot=4

```
Old leader:
  Ballot 10:
    slot=1: V1 (accepted)
    slot=2: V2 (accepted)
    slot=3: V3 (accepted)
    slot=4: V4 (in flight, never accepted)

New leader ballot 11:
  "What was accepted at ballot 10?"
  
Acceptors reply:
  "V1, V2, V3 were accepted. Slot 4 has no value."
  
New leader:
  "OK, I'll continue from slot 4."
```

**Safety guarantee:** The new leader won't overwrite V1, V2, V3. It will re-propose them if needed.

## The Diagrams

### Single-Value Paxos Timeline

```
Proposer p1    Acceptor A1   Acceptor A2   Acceptor A3   Learner L
    |              |             |             |             |
    |--Prepare(5)-->|             |             |             |
    |              |             |             |             |
    |            (promise)        |             |             |
    |<-Promise(5,nil)             |             |             |
    |              |             |             |             |
    |          (repeats for A2, A3)             |             |
    |              |             |             |             |
    |--Accept(5,X)-->|             |             |             |
    |              |--Accept(5,X)->|             |             |
    |              |              |--Accept(5,X)->|           |
    |              |              |             |--Learn(X)-->|
    |              |              |             |             |
    |              |<---Accepted-----|             |             |
    |<---Accepted-------<---Accepted---<---Accepted-|
    |              |             |             |             |
    (Quorum reached, X chosen)    |             |             |
```

### Multi-Paxos Pipeline

```
Time: T0    T1    T2    T3    T4
      |     |     |     |     |
Slot 1:|--P1--|--A1--|
      |     |     |     |
Slot 2:|         |--P1--|--A2--|
      |         |     |     |
Slot 3:|             |--P1--|--A3--|
      |             |     |     |
      (Pipelined: 3 values in flight simultaneously)
```

## Interview Section

### Q1: Why does Paxos need a majority, not just any subset?

**Weak answer:** "Uh, safety reasons?"

**Strong answer:**
"If you have N=5 acceptors and require only 2 (not 3), then:
- Majority 1: {A1, A2}
- Majority 2: {A3, A4}
- No overlap!

If Majority 1 accepts value X and Majority 2 accepts value Y,
two different values are chosen. Violates safety.

Majority ensures overlap: if A is N/2+1, and we have two sets of size N/2+1,
they must overlap by pigeonhole principle.

With N=5: need 3. Any two sets of 3 must share at least 1."

### Q2: A proposer sends Prepare(ballot=10). Two acceptors respond with (ballot=10, value=V1). One acceptor doesn't respond (crashed). Do we proceed?

**Weak answer:** "We need all acceptors."

**Strong answer:**
"No, we need a majority. With 5 acceptors and 2 responses:
- We have 2/5 acceptors, not majority (3/5)
- Wait for more responses or declare the proposer failed

The timeout depends on the system:
- [VERIFY] Chubby uses ~30 second Paxos round
- [VERIFY] Raft implementations use 150-300ms

If only 1 acceptor ever responds, we're stuck (network partition)."

### Q3: What if two proposers send conflicting Accept requests?

```
Proposer p1: "Accept(ballot=10, slot=1, value=A)"
Proposer p2: "Accept(ballot=11, slot=1, value=B)"
```

**Weak answer:** "First one wins?"

**Strong answer:**
"Phase 1 prevents this. Before accepting, proposers must do Prepare:

p1: Prepare(10) → acceptors promise not to accept < 10
p2: Prepare(11) → acceptors promise not to accept < 11

If p1's Prepare(10) reached quorum first:
  Acceptors now promise not to accept < 10
  When p2 sends Accept(11, B):
    Acceptors accept it (11 > 10)
    But acceptors will reply with the last accepted value
    When p2 does Prepare(12), it learns about value A and will use it

If network delays p2's Prepare(11):
  p1's Accept(10, A) succeeds first
  Later p2's Prepare(11) arrives
  Acceptors return 'A' as last accepted
  p2 re-proposes A, not B

Result: One value is chosen (safety preserved)."

### Q4: Describe Multi-Paxos latency with a stable leader.

**Weak answer:** "It's fast because you don't repeat Prepare."

**Strong answer:**
"Latency for each slot:
- Single-Paxos: 2 RTT (Prepare + Accept)
- Multi-Paxos with stable leader: 1 RTT

Timeline:
T0: Client sends value V1 to leader
T1: Leader sends Accept(ballot, slot=1, value=V1)
T1: Quorum responds with Accepted
T2: Client receives confirmation

After quorum confirms, learner knows value is chosen.
Total: 1 RTT (from leader send to quorum response).

With multiple clients pipelining:
T1: Accept(slot=1, V1), Accept(slot=2, V2), Accept(slot=3, V3)
T2: Three slots committed in parallel (throughput increases)

Why no Prepare each time?
  Acceptors promised 'ballot B' in the initial Prepare.
  As long as leader holds ballot B and doesn't restart,
  Accept(B, ...) immediately succeeds without re-promising."

### Q5: A proposer crashes after Prepare but before Accept. What happens?

**Weak answer:** "The value is never chosen."

**Strong answer:**
"The proposer sent Prepare(ballot=B) and got majority quorum promises.
But crashes before sending Accept(B, value).

Acceptors are waiting for Accept(B, ...) forever.
State: promised ballot B, no accepted value yet.

When the proposer comes back (or new proposer):
1. Sends Prepare(ballot=B+1)
2. Acceptors respond: 'We promised B, now promising B+1. Last accepted: none for B.'
3. New proposer can now propose any value

No safety violation: the old ballot B never completed,
so no value was chosen at B. The new ballot wins."

### Q6: Numeric Exercise: Multi-Paxos Throughput

You have 5 servers, quorum size = 3.
Network latency = 10ms (each direction).
Single-Paxos latency per value = 2 RTT = 40ms.

Multi-Paxos with stable leader:
- Prepare phase (once): 1 RTT = 10ms (amortized to 0 over N values)
- Accept phase: 1 RTT per value = 10ms

If you pipeline 10 values at once:
- Leader sends 10 Accept requests in parallel (same network packet)
- Quorum processes all 10 in parallel
- All 10 respond in ~10ms (network latency, not sequential)

**Throughput:**
- Sequential (each 10ms): 1 value per 10ms = 100 values/sec
- Pipelined (10 in parallel): 10 values per 10ms = 1000 values/sec

**Bottleneck:** Disk write latency [VERIFY] (~5-10ms on SSD, [VERIFY] ~1-5ms NVMe).

With disk sync required after Accept, throughput limited to ~100-200 values/sec per leader.

## When to Use / When NOT

| Scenario | Paxos? |
|----------|--------|
| Replicated state machine (strong consistency needed) | YES |
| Key-value store needing atomic consensus | YES |
| Distributed lock service (like Chubby) | YES |
| Fast local caches (eventual consistency OK) | NO |
| Eventually consistent data (DNS, CDN) | NO |
| Single-writer, many readers (use replication w/o consensus) | MAYBE |
| Leader-based system with failover | YES |
| Pure peer-to-peer (no central authority) | MAYBE (Raft simpler) |

## Checklist: Is Your Paxos Implementation Correct?

- [ ] Phase 1: Do proposers get majority of promises before proposing?
- [ ] Phase 2: Do acceptors reject Accept() with lower ballot?
- [ ] Quorum: Does the implementation check for N/2 + 1 responses, not all N?
- [ ] Crash recovery: If leader dies, can new leader learn old values from acceptors?
- [ ] Durability: Are promises and accepted values written to disk before responding?
- [ ] Liveness: Does the implementation have a timeout/backoff to avoid dueling proposers?
- [ ] Learners: Do learners wait for quorum (not just first response) before committing?
- [ ] Holes in log: If slot 5 is missing, do replicas wait or propose a no-op?

## Common Wrong Answers

1. "Paxos chooses a value on first response." → NO, needs majority.
2. "If 2/5 acceptors respond, we can proceed." → NO, need 3/5.
3. "Proposers can propose different values in Phase 2." → NO, Phase 1 dictates the value.
4. "Multi-Paxos avoids Prepare entirely." → NO, one Prepare per leader, then many Accepts.
5. "Paxos works with equal crash failures (F >= N/2)." → NO, need F < N/2 (strict majority).
6. "Learners don't need to wait for quorum." → WRONG, they do (or rely on persistence).
7. "A crashed proposer's ballot number is lost." → NO, acceptors remember promised ballots.
