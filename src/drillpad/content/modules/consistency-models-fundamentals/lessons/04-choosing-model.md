# Choosing Your Model: Framework for Decision

## Decision Tree

```
Start: Do I need consistency?

1. Is this financial/money?
   YES → Strong Consistency (non-negotiable)
   NO → Continue

2. Is correct order critical?
   YES → Causal (order matters)
   NO → Continue

3. Can I tolerate 5-minute stale data?
   YES → Eventual Consistency (fastest)
   NO → Continue

4. Do users see their own writes?
   YES → Read-Your-Write (hybrid)
   NO → Eventual is fine
```

## Framework: Impact Assessment

Before choosing consistency, ask:

**1. What's the blast radius if consistency is violated?**

| Data Type | Impact of Stale | Impact of Lost Write | Best Choice |
|---|---|---|---|
| **Money transfer** | Catastrophic | Catastrophic | Strong |
| **User profile** | Bad (confuse user) | Bad (lose their data) | Strong |
| **Friend list** | Minor (friend added, not visible yet) | Bad (lose friendship) | Causal |
| **Like count** | None (approx is fine) | None (user can retry) | Eventual |
| **Leaderboard** | None (lag is expected) | None (position can change) | Eventual |
| **Analytics** | None (approx is fine) | None (can re-ingest) | Eventual |

**2. What's the latency budget?**

| Consistency | Latency | Tradeoff |
|---|---|---|
| **Strong** | 10-100ms | Coordination overhead |
| **Causal** | 5-50ms | Medium overhead |
| **Eventual** | <5ms | Temporal inconsistency |

**3. How often does this data change?**

- **Frequently changing** (likes, leaderboard): Eventual or causal
- **Rarely changing** (user profile): Strong is affordable
- **Medium** (friend list): Causal or quorum read-write

## Real-World Examples

### Example 1: Payment System

```
Data types:
  - Accounts (balance): Strong (money!)
  - Payment history: Strong (audit trail)
  - Failed payments (logs): Eventual (for debugging)

Architecture:
  - Balance: primary-backup, quorum read/write, replication lag < 100ms
  - History: same
  - Logs: eventual, okay to be 1 hour behind

Rationale:
  - If balance is stale, can double-charge
  - History needs to be exact (reconciliation)
  - Logs are non-critical (just for debugging)
```

### Example 2: Social Media Platform

```
Data types:
  - User profile: Causal (user's writes + metadata)
  - Friends list: Causal (causality: add friend → see in list)
  - Timeline/feed: Eventual (order doesn't matter much)
  - Likes: Eventual (count can be approximate)
  - Comments: Causal (threads need order)

Latency budget:
  - Profile page: <500ms (user can wait)
  - Like button: <100ms (interactive)
  - Timeline load: <1s (can be cached)

Architecture:
  - Profile/friends: causal, 50ms latency acceptable
  - Timeline: eventual, 5ms latency
  - Likes: eventual, 5ms latency
  - Comments: causal, 50ms latency
```

### Example 3: Collaborative Document

```
Data types:
  - Document content: Strong (must not lose edits)
  - Cursor positions: Eventual (lag is OK)
  - Comments: Causal (threads need order)

Rationale:
  - Content loss = data loss (unacceptable)
  - Cursor lag of 100ms is invisible to users
  - Comments are secondary, causal is good enough
```

## Implementation Checklist

### For Strong Consistency
- [ ] Use primary-backup or multi-paxos
- [ ] Quorum read/write (majority of replicas)
- [ ] All writes go through primary (no split-brain)
- [ ] Replication latency < 100ms (or accept slow commits)
- [ ] Monitor replica lag

### For Causal Consistency
- [ ] Version vectors or similar (track causality)
- [ ] Apply writes in causal order
- [ ] Handle causality correctly (explicit dependencies)
- [ ] Accept 5-50ms latency
- [ ] Compress version vectors to avoid bloat

### For Eventual Consistency
- [ ] Conflict resolution policy (last-write-wins, application logic)
- [ ] Accept stale reads (< 1 minute typical)
- [ ] Monitor replica lag
- [ ] Handle concurrent writes gracefully
- [ ] Plan for network partitions

## Interview Pattern: Consistency Decision

```
Q: "Design a real-time collaborative spreadsheet.
   Multiple users editing simultaneously.
   How do you ensure consistency?"

Weak answer:
  "Use strong consistency for everything"
  (❌ Slow, locks kill real-time experience)

Strong answer:
  "Different strategy per data:
  
  1. Critical: Cell data
     - Strong consistency (can't lose edits)
     - Implementation: OT (Operational Transformation) or CRDT
     - Cost: 50-200ms per edit
     - Worth it: losing a formula is catastrophic
  
  2. Medium: Cell selection, cursor positions
     - Eventual consistency (100ms lag is invisible)
     - Implementation: broadcast position updates
     - Cost: <10ms
     - Worth it: cursor lag doesn't break functionality
  
  3. Low: Comments on cells
     - Causal (thread order matters)
     - Implementation: causality tracking
     - Cost: 20-50ms
     - Worth it: comments are secondary, thread order is nice
  
  4. Real-time sync mechanism:
     - Incoming edits go through OT engine (resolves conflicts)
     - Position updates broadcast immediately (eventual)
     - Comments added with causal tracking
  
  5. User experience:
     - User types formula → immediately applies locally
     - Sent to server + other users
     - Server validates (OT) → broadcast result
     - Other users see edit within 100ms
     - Latency is hidden by local echo
  
  6. Handling conflict:
     - User A edits cell[0,0]
     - User B edits cell[0,0] concurrently
     - OT engine resolves: orders both edits deterministically
     - Both users see consistent result
  
  Alternative: CRDT (Conflict-free Replicated Data Type)
    - No central coordinator needed
    - Every replica computes same result from same edit history
    - Slightly slower (more overhead) but more resilient"

Why this signals good judgment:
  - You didn't apply one consistency model to everything
  - You understood OT/CRDT for real-time collab
  - You prioritized user experience (local echo hides latency)
  - You had a conflict resolution strategy
  - You knew the cost/benefit of each approach
```

## Quick Reference

**"I need..."**
- "...money to never be lost" → Strong
- "...threads to be ordered" → Causal
- "...fast reads" → Eventual
- "...users to see their own writes" → Read-Your-Write
- "...conflict-free writes" → CRDT or OT
- "...to scale to 100M users" → Eventual + caching

## What This Signals

- You understand the consistency spectrum (not binary)
- You classify data by criticality
- You know the cost of each model (latency, complexity)
- You can defend your choice (not arbitrary)
- You think about user experience (not just correctness)
