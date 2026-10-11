# Split Brain: Network Partitions and Recovery

## Overview

This lesson covers:
1. What happens when the network partitions (not just leader crashes)
2. Quorum read/write (when partitions persist)
3. Recovery strategies (leader demotion, fencing)
4. Real-world scenarios: ZooKeeper, etcd outages

---

## Network Partition Scenario

Imagine 5 servers. Network fails and splits them: [A, B] and [C, D, E].

```
         NETWORK PARTITION
              ↓
    [A ←→ B]        [C ←→ D ←→ E]
     side 1          side 2
    (minority)       (majority)

Time 0: Leader is A (current term=5)
        B is follower

Time 1: C, D, E timeout (can't reach A or B)
        E becomes candidate for term=6
        E gets votes from C, D, E
        E becomes NEW LEADER for term=6

Now: TWO LEADERS
  - A thinks it's still leader (term=5)
  - E thinks it's leader (term=6)

Problem: Client on [A, B] side writes to A
         Client on [C, D, E] side writes to E
         Both accept writes
         → SPLIT BRAIN (inconsistent state)
```

---

## Prevention: Quorum Writes

**Only a quorum can commit.**

```
5 servers: need 3 to commit

Side 1: [A, B] = 2 servers
  - A tries to replicate new write
  - Gets ACK from A (itself) and B
  - 2 < 3 (quorum)
  - CANNOT commit
  - Returns error to client: "not yet replicated"

Side 2: [C, D, E] = 3 servers
  - E replicates new write
  - Gets ACK from E (itself), C, D
  - 3 = 3 (quorum)
  - Can commit
  - Returns 200 OK to client
  
Result: Only side 2 can accept writes
        Side 1 blocks (high availability loss, but no split brain)
```

**This is the key insight:** Quorum prevents split-brain writes.

---

## Client Behavior During Partition

### Write Request

```
Client: SET x=100 (sent to A in [A, B] partition)

A receives, tries to replicate
  - Sends to B → ACK
  - Tries to send to C → TIMEOUT (network down)
  - Tries to send to D → TIMEOUT
  - Tries to send to E → TIMEOUT
  
A has 2 ACKs (A, B)
Quorum = 3
2 < 3 → CANNOT COMMIT

A holds request, keeps retrying until:
1. Network heals (C, D, E rejoin)
2. A steps down as leader
3. Timeout (client gives up)

A NEVER returns success to client
```

### Read Request

```
Client: GET x (sent to A)

Option 1: Stale read (from A's local copy)
  - Fast, but might be stale
  - Returns old value of x

Option 2: Quorum read (Raft ReadIndex)
  - A sends empty AppendEntries to all
  - Waits for majority ACK
  - If successful: can safely read local state
  - If fails: return error (not leader anymore)
```

---

## Partition Healing

```
Time 0-2: Partition active (A, B) vs (C, D, E)

Time 3: Network heals

[A, B] see heartbeats from E (term=6)
  E has higher term than A's term=5
  A steps down (no longer leader)
  B and A become followers of E

[A] has uncommitted entries (SET x=100 that never replicated)
  When A receives new term from E
  A's log is truncated
  Uncommitted entries are DISCARDED
  A adopts E's log

Result: All 5 servers converge on E's log
        SET x=100 is lost (never committed)
```

---

## Fencing: Preventing Old Leaders

Problem: Old leader (A) gets isolated, then network heals slowly. A still thinks it's leader.

```
Time 0-2: [A, B] isolated
          A keeps thinking it's leader (no heartbeats prove otherwise)

Time 3: Network partially heals
        C can reach A (but not B, D, E)
        A says "I'm the leader, write this value"
        C writes to A
        But C is already following E as leader
        → Confusion

Solution 1: Epoch/term tokens
  Each leader gets a unique token
  Old leader token is revoked when new leader elected
  Storage enforces: only accept writes from current token

Solution 2: Fencing (leases)
  Leader acquires lease: "I am leader for next 500ms"
  Lease expires, leader must renew
  If network fails, lease expires, leader can't write
  Prevents zombie leaders

Example: CockroachDB
  When new leader is elected, it invalidates old leader's token
  Old leader attempts to write → storage rejects (wrong token)
```

---

## Real Outage: etcd in Kubernetes

```
Scenario: 3-node etcd cluster, network partition
  [Master] gets isolated from [Worker1, Worker2]
  
Worker1 becomes new leader (quorum: 2/3)
New leader commits: "Pod X running on Worker2"

Master (old leader) gets stuck
  Tries to commit: "Pod X running on Worker1"
  Only itself agrees (1/3 < quorum)
  BLOCKS (doesn't return error immediately)

kubelet on Master: "Why can't I update Pod?"
  Timeout after 5 seconds
  Returns error to kube-apiserver

Result:
  - Cluster divided
  - Master can't update etcd
  - Kubernetes API on Master returns stale data
  - New leader (Worker1) is source of truth
  - Master eventually recognized as unhealthy
  - Pods on Master are evicted to Workers

Recovery:
  When partition heals
  Master sees Worker1/2 as leaders (higher term)
  Master becomes follower
  Master's uncommitted entries discarded
  All 3 converge
```

---

## Most Likely Interview Questions

**Q1: "Can Raft get split brain?"**

A: "No. Raft prevents split brain through quorum. In 5 nodes, you need 3 to commit. If partition is 3-2, only the 3 can form a quorum and elect a leader. The 2 side has no leader (candidates exist but can't reach majority). So max one leader exists at any time."

**Q2: "What happens to writes during partition?"**

A: "Writes to the majority partition succeed after replication to quorum. Writes to the minority partition block (leader can't get quorum ACKs) and timeout. No writes from minority are applied (safety). Trade-off: availability loss, but consistency preserved."

**Q3: "How do you recover after partition heals?"**

A: "Old leader (from minority) sees higher term from new leader (from majority), steps down, becomes follower. Minority's uncommitted entries are discarded. All servers converge on majority's log. Uncommitted entries are lost, but nothing was applied (safe)."

**Q4: "What if a leader gets isolated and thinks it's still leader?"**

A: "It can't make new writes (can't reach quorum for replication). Existing followers switch to the new leader when their election timeout fires (don't get heartbeats from old leader). Old leader is effectively powerless—it's a zombie leader that can't commit anything."

**Q5: "How would you handle this if you had only 3 nodes and one crashed?"**

A: "3 nodes, quorum = 2. If one crashes, you have 2 left (exactly quorum). New leader elected from 2 remaining. System still works. But if partition happens (1 node isolated, 2 together), the 2-node side is quorum, can elect leader. Good. If one more crashes, you have 1 node (not quorum), system blocks. This is why 5-node clusters are standard (can tolerate 2 failures)."

---

## Key Takeaways

1. **Quorum prevents split brain** (majority always has authority)
2. **Minority partition cannot commit** (blocks or times out)
3. **Majority partition continues** (new leader elected, writes succeed)
4. **Recovery discards minority's uncommitted entries** (safety first)
5. **Zombie leaders are powerless** (can't reach quorum)
6. **Token/fencing prevents old leader confusion** (explicit invalidation)

---

## Practice: Design a Scenario

**Scenario:** 7-node Raft cluster. Partition: [A, B] and [C, D, E, F, G]. Node H is on slow link (messages arrive with 5-second delay).

Questions:
1. Which partition can elect a leader? Why?
2. What happens to writes on each side?
3. When partition heals, what happens to A's uncommitted entries?
4. Why is H (slow link) a problem?
