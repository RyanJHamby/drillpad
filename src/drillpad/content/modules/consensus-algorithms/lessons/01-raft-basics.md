# Raft Consensus: Leader Election and Log Replication

## Overview

Raft is a consensus algorithm that solves: "How do N servers agree on state even if some fail?" Used in etcd, Consul, CockroachDB, and many distributed systems.

This lesson covers:
1. Why consensus is hard (Byzantine generals problem)
2. Raft state machine (follower, candidate, leader)
3. Leader election (term-based voting)
4. Log replication (append-entries protocol)
5. Commit and apply (when is data durable?)

---

## The Problem: Byzantine Generals

Imagine 5 generals commanding armies. They must agree on "attack" or "retreat." But:
- Messages can be delayed or lost
- Some generals might be traitors (send conflicting messages)
- No centralized authority

**Raft assumes:** Failures are benign (crash, not Byzantine). Servers either work correctly or crash.

---

## Raft State Machine

Every server is in one of three states:

```
        ┌─────────────────────────────┐
        │  Follower (default)         │
        │  - Listens to leader        │
        │  - Votes in elections       │
        └─────────────────────────────┘
                    ↑         ↓
         no heartbeat   timeout
                        ↓
        ┌─────────────────────────────┐
        │  Candidate (election)       │
        │  - Requests votes           │
        │  - Increments term          │
        └─────────────────────────────┘
                    ↑         ↓
           votes lost   wins majority
                        ↓
        ┌─────────────────────────────┐
        │  Leader (1 per term)        │
        │  - Sends heartbeats         │
        │  - Replicates logs          │
        └─────────────────────────────┘
                    ↓
            loses network/quorum
                    ↓
                Follower
```

**Term:** Logical clock. Increments when election starts. Used to detect stale leaders.

---

## Leader Election

**Scenario:** 5 servers, leader dies.

```
Time 0: All followers, term=1
        Follower A ─ Follower B ─ Follower C ─ Follower D ─ Follower E

Time 1: A's election timeout fires
        Candidate A increments term → term=2, votes for self
        Candidate A broadcasts RequestVote(term=2)

Time 2: B, C, D, E receive RequestVote
        They check: "Is term 2 > my term 1?" Yes.
        They vote for A (grant vote if: term >= current term AND no vote yet this term)

Time 3: A gets votes from B, C, D (3/5 = quorum)
        A becomes leader, sends AppendEntries heartbeats

Time 4: E gets heartbeat from A (now leader)
        E updates term to 2, becomes follower
```

**Key insight:** Majority quorum prevents split brain. If 5 servers are partitioned 3-2, only the 3 can elect a leader (need 3/5).

---

## Log Replication

Leader replicates commands to followers:

```
Client: SET x=5

Leader:
  ┌──────────────────────────────┐
  │ term | index | command        │
  ├──────────────────────────────┤
  │  1   │  1    │ SET x=10       │ (committed)
  │  1   │  2    │ SET y=20       │ (committed)
  │  2   │  3    │ SET x=5        │ (uncommitted)
  └──────────────────────────────┘
         ↓ AppendEntries
  
Follower B:
  ┌──────────────────────────────┐
  │ term | index | command        │
  ├──────────────────────────────┤
  │  1   │  1    │ SET x=10       │ (committed)
  │  1   │  2    │ SET y=20       │ (committed)
  │  2   │  3    │ SET x=5        │ (not committed yet)
  └──────────────────────────────┘
         ↑ AppendEntries ACK
  
Leader receives ACK from B, C (majority)
  → Marks index=3 as "committed"
  → Applies to state machine: x=5
  → Future AppendEntries tell followers "up to index 3 is committed"
```

**Commit rule:** Entry is committed when it's been replicated to a quorum (majority).

---

## What Prevents Split Brain?

Scenario: Partition into [A] and [B, C, D, E].

```
A isolated, term=2
  Increments to term=3 (candidate)
  Broadcasts RequestVote
  Only gets votes from A (itself)
  Doesn't reach majority → stays candidate
  CANNOT become leader

B, C, D, E see heartbeat from old term=2
  Wait for timeout
  B becomes candidate, requests votes for term=4
  Gets votes from C, D, E (3/4 = majority)
  Becomes leader for term=4

Result: Only B can make decisions. A is stuck.
```

**When A reconnects:**
- A sees term=4 (higher than its term=3)
- A reverts to follower, drops any uncommitted entries
- A accepts B as leader (new term)

---

## Real Example: etcd (Kubernetes config store)

etcd uses Raft to replicate key-value stores across 3+ nodes.

```
kubectl set image deployment/app app=v2

┌─────────────────────────────────┐
│ API server (etcd leader)        │
│ - Receives: image=v2            │
│ - Writes to local log (term=5)  │
│ - Replicates to follower 1, 2   │
│ - Gets ACK from 1, 2            │
│ - Commits (safe now)            │
│ - Applies: update configmap     │
│ - Returns 200 OK to client      │
└─────────────────────────────────┘
```

If leader crashes mid-replication:
```
Leader died after replicating to follower 1, not yet follower 2

Follower 1: Has [image=v2] (uncommitted)
Follower 2: Doesn't have it

New leader elected (follower 2 or 3)
New leader's log is shorter
Old follower 1's uncommitted entry is discarded
Result: Consistent (no split-brain writes)
```

---

## Most Likely Interview Questions

**Q1: "How does Raft prevent split brain?"**

A: "Quorum-based voting. In 5 servers, you need 3 to elect a leader. If partitioned 3-2, only the 3 side can elect. The 2-side candidates get only their own vote, can't reach majority, stay as followers. So at most one leader per term."

**Q2: "What happens if the leader crashes?"**

A: "Followers have an election timeout (150-300ms). When it fires, a follower becomes candidate and requests votes. If it gets majority, it becomes leader and sends heartbeats. If two candidates split votes, both lose and retry with exponential backoff. Eventually, one candidate will get quorum."

**Q3: "Why do you need the 'term' concept?"**

A: "Term is a logical clock. It prevents a stale leader (disconnected, doesn't know it crashed) from accepting new entries. When a stale leader tries to replicate, followers see its term is lower and reject it. This guarantees only the current-term leader can commit entries."

**Q4: "What's the difference between 'replicated' and 'committed'?"**

A: "Replicated: entry is on the leader and some followers. Committed: entry is replicated to a quorum AND the leader knows it. Followers apply committed entries. This ensures durability: even if leader crashes, committed entries will exist on a majority."

**Q5: "How do you handle a slow follower?"**

A: "Leader tracks 'matchIndex' (how far each follower is replicated). If a follower is slow, leader sends AppendEntries regularly with all missing entries. Follower applies them in order. No special backoff—just retry until caught up. Once caught up, normal heartbeat (empty AppendEntries) keeps follower in sync."

---

## Key Takeaways

1. **Quorum prevents split brain** (majority always wins)
2. **Terms detect stale leaders** (higher term = newer)
3. **Commitment requires replication + leader knowledge** (durability)
4. **Followers apply committed entries** (state machines agree)
5. **Log is the source of truth** (not the leader's state)

---

## Real Systems Using Raft

- etcd (Kubernetes config)
- Consul (service mesh)
- CockroachDB (distributed SQL)
- TiDB (distributed MySQL-compatible DB)
- Vault (secret management)
