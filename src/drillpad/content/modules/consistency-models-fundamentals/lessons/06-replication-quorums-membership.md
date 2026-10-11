# Replication Quorums & Membership: Dynamic Replication with Safety

## The Problem: Growing Your Cluster

You start with 3 servers (Paxos consensus on N=3, quorum=2).

Business grows. You need 5 servers (quorum=3).

But how do you add server #4 and #5 without breaking consensus?

```
Current state:
  [A, B, C] with quorum=2
  A is leader

What you can't do:
  "Add D and E now"
  → Quorum is now 3, but current leader A only has [A, B]
  → Can't reach quorum, system locks up

What you must do:
  1. Add D while keeping quorum=2 for [A, B, C, D]
  2. Then add E with quorum=3
```

## Quorum Intersection: The Core Invariant

The key insight: any two quorums must overlap.

If they don't, you can have a split brain:

```
Quorum 1: {A, B}        Quorum 2: {C, D}
No overlap!

Scenario:
  Network partition: {A, B} on one side, {C, D} on other

  Side 1: "We're quorum {A, B}, we commit value V1"
  Side 2: "We're quorum {C, D}, we commit value V2"

  After partition heals:
    Both groups think they're the source of truth
    V1 vs V2 conflict (safety violated!)
```

**Safe quorum:** Any two quorums must overlap.

With N servers, quorum size Q:
- Must have Q > N/2 (i.e., Q >= N/2 + 1)

```
N=5:
  Quorum size = 3
  
  Any two quorums of 3:
    {1, 2, 3} and {3, 4, 5} → overlap at 3 ✓
    {1, 2, 4} and {2, 3, 5} → overlap at 2 ✓
    Always overlap (pigeonhole principle)

N=5, bad quorum = 2:
  {1, 2} and {3, 4} → no overlap ✗ (unsafe)
```

## Changing Membership: The Reconfiguration Problem

You want to go from {A, B, C} to {A, B, C, D, E}.

**The Danger:** During the transition, both old and new quorums might be active.

Old membership: {A, B, C}, quorum = 2
New membership: {A, B, C, D, E}, quorum = 3

If a leader at old quorum commits with {A, B}, and a leader at new quorum commits with {D, E}, they don't overlap:

```
Old quorum {A, B} commits X
New quorum {D, E} commits Y
→ Split brain!
```

**Solution: Two-Phase Reconfiguration**

### Phase 1: Joint Consensus

Use a temporary membership that includes both old and new:

```
Old: {A, B, C}
Temp (Joint): {A, B, C, D, E}  ← includes all
New: {A, B, C, D, E}

Quorum rule during Joint: need quorum from BOTH old and new

  Old quorum = 2 (from {A, B, C})
  New quorum = 3 (from {A, B, C, D, E})
  
  Joint quorum = max(2, 3) = 3 from temp, but must overlap with both
  
  Safe quorum during Joint: need 2 from old AND 2 from new
  Example: {A, B, D} = includes {A, B} (quorum of old) + {A, B, D} (overlap with new)
```

During Joint consensus:
- At least one node from old must be in quorum
- At least one node from new must be in quorum
- Guarantees any future quorum will overlap

```
Timeline:
T1: Commit entry C1 with Joint membership {A, B, C, D, E}
    Quorum: {A, B, D} (has 2 from old {A, B, C}, 3 from new {A, B, C, D, E})
    Safe: any future quorum will overlap with C1

T2: Commit entry C2 with New membership {A, B, C, D, E}
    Quorum: {A, B, D, E} (has 4 from new)
    Safe: C1 and C2 are both visible to old and new
    
T3: Old membership {A, B, C} is officially dead
    Can ignore C without breaking safety
```

### Phase 2: New Membership

Once Joint is committed, switch to new membership.

```
Joint committed → all nodes know about both configs
Switch to new config

If leader crashes during Joint:
  New leader learns Joint config
  Knows it's in transition
  Must commit final New config before proceeding

Result: Old config is safely decommissioned
```

## Practical Implementation: Etcd (Kubernetes uses this)

Etcd uses a simplified version:

```
Current: {A, B, C}

Step 1: Add member D
  Membership = {A, B, C, D}
  Quorum goes from 2 to 3
  Wait for D to catch up

Step 2: Add member E
  Membership = {A, B, C, D, E}
  Quorum stays at 3
  Wait for E to catch up

Step 3: Add member F
  Membership = {A, B, C, D, E, F}
  Quorum goes to 4
  Wait for F to catch up
```

**Why safe:** Each step increases membership by 1. Quorum doesn't decrease (or increases safely).

[VERIFY] Etcd's reconfiguration guarantees:
- Leader sees quorum of new membership before proceeding
- All logs up to membership change are replicated

## Diagrams

### Quorum Intersection in N=5

```
Setup: N=5, quorum=3

          5
         / \
        /   \
       /     \
      4 ----- 1
       \     /
        \   /
         \ /
          3
          |
          2

Safe quorums (any 3 nodes):
  {1,2,3}, {1,2,4}, {1,2,5}
  {1,3,4}, {1,3,5}, {1,4,5}
  {2,3,4}, {2,3,5}, {2,4,5}
  {3,4,5}
  
Total: C(5,3) = 10 quorums

Any two overlap? 
  Example: {1,2,3} ∩ {3,4,5} = {3} ✓
  Example: {1,2,4} ∩ {2,3,5} = {2} ✓
  
Proof: Pigeonhole principle
  Two sets of 3 nodes from a universe of 5
  If disjoint, they'd cover 6 nodes (impossible, only 5 exist)
  Must overlap
```

### Two-Phase Membership Change

```
Timeline: Old → Joint → New

Old config:
  {A, B, C}
  quorum = 2

  A is leader, log = [entry1, entry2]
  Wants to add D, E

        Old State        Joint State        New State
       [A, B, C]       [A,B,C,D,E]       [A,B,C,D,E]
       quorum=2        quorum={2 from old} quorum=3
                       + {2 from new}

Commit entry:
  C_old:  {A,B,C} → {A,B,D} (has 2 from old)
  C_joint: {A,B,C,D,E} → {A,B,D,E} (has 2 from old, 3 from new)
  C_new:  {A,B,C,D,E} → {A,B,D,E} (quorum 3)

After C_joint:
  A: [entry1, entry2, C_joint]
  B: [entry1, entry2, C_joint]
  D: [entry1, entry2, C_joint]
  E: [entry1, entry2, C_joint]  (eventually)

Old nodes A, B know: membership is changing
New nodes D, E know: they're joining

After C_new:
  A, B, C: no longer vote (C never caught up during joint)
  D, E: now voting members
```

### Membership Change Failure Scenario

```
Leader A trying to add D, E:

T0: A commits C_joint to {A, B, D}
    A: [entry1, entry2, C_joint] ✓
    B: [entry1, entry2, C_joint] ✓
    D: [entry1, C_joint] ✓ (lagging)
    E: [] (never received C_joint)

T1: A tries to commit C_new to {A, B, C, D, E}
    A: [entry1, entry2, C_joint, C_new] ✓
    B: [entry1, entry2, C_joint, C_new] ✓
    D: [entry1, C_joint, C_new] ✓
    E: [C_new] ✓ (newly joined, no history)
    C: [entry1, entry2] ✗ (never saw joint)

T2: A crashes

T3: New leader (must be from {A, B, C, D, E}):
    If B or D elected:
      Can see C_joint (even if C never did)
      Knows membership is [A,B,C,D,E]
      Will replicate C_joint and C_new to all
    
    If C elected (shouldn't happen, lags):
      C is from old config only
      Will eventually learn it's been replaced

Result: Safe regardless of who crashes/when
```

## Interview Section

### Q1: Why can't you add a member by directly changing quorum from 2 to 3?

**Weak answer:** "It's complicated."

**Strong answer:**
"Suppose we go {A, B, C} (quorum 2) → {A, B, C, D} (quorum 3) instantly:

Race condition:
  Leader L1 (knows old config): proposes with {A, B}
    Thinks quorum = 2, gets {A, B} → committed!
  
  Leader L2 (knows new config): proposes with {C, D}
    Thinks quorum = 3, gets {C, D} → committed!

Results:
  L1 committed with {A, B}
  L2 committed with {C, D}
  No overlap → split brain

Solution: Joint consensus
  Both old and new membership are active
  Quorum must include nodes from both old and new
  This forces overlap, preventing split brain"

### Q2: During two-phase membership change, what happens if the leader crashes after committing joint config but before committing new config?

**Weak answer:** "The new config is lost."

**Strong answer:**
"After joint is committed to quorum:
  Example: {A, B, D} all have joint config

Leader A crashes.
New leader (must be from {A,B,C,D,E}):
  If B or D elected:
    They have [entry1, entry2, C_joint]
    They will re-replicate C_joint to C and E
    Then they can commit C_new with full quorum {A,B,C,D,E}

Result: Safe. Joint is durable once quorum has it.
  New config C_new will eventually be committed.

Why? Because joint membership guarantees:
  Any leader elected after joint is committed
  must have the joint config (by quorum intersection)
  and will continue the reconfiguration process."

### Q3: Can you remove a member from the cluster?

**Weak answer:** "Just delete it from the config."

**Strong answer:**
"Removing is safer than adding. You go:
  {A, B, C, D, E} (quorum=3) → {A, B, C} (quorum=2)

Danger: if you drop D and E simultaneously:
  {A, B, C} and {D, E} have no overlap
  But the old quorum might be {D, E} (already committed)

Safe removal:
  1. Use joint consensus: commit {A, B, C, D, E} (temp)
  2. Commit new config: {A, B, C} (quorum=2)
  3. D and E stop accepting votes

Alternative (Raft): remove one at a time
  {A, B, C, D, E} → {A, B, C, D} (quorum still 3)
  {A, B, C, D} → {A, B, C} (quorum becomes 2)
  
Each step preserves quorum intersection."

### Q4: Describe the liveness guarantee of two-phase reconfiguration.

**Weak answer:** "It eventually finishes."

**Strong answer:**
"Liveness (progress) requires:
1. The leader proposing membership change is not partitioned
2. Quorum size of new membership is reachable

During joint consensus:
  Quorum = intersection of old and new
  Requires at least one node from {old} AND {new}
  
  If leader is from old membership:
    Need new members reachable
  If leader is from new membership:
    Need old members reachable
  If leader is in both:
    Needs less (e.g., {A, B} from {A, B, C, D, E})

Liveness failure: partition isolates all of old membership
  Then new membership {D, E} cannot reach old quorum requirement
  Reconfiguration stalls [VERIFY] (Etcd times out after ~5s)

Mitigation: overlap membership during transition
  Old: {A, B, C}
  New: {A, B, D, E}  ← include old leaders
  
  Leader A can reach quorum even if {C} partitions away"

### Q5: Numeric Exercise: Quorum Size Changes

Start: 3 nodes, quorum = 2
Add nodes: 3 → 5, new quorum = 3
Remove: 5 → 3, quorum = 2

Availability change:
- 3 nodes, quorum 2: tolerate 1 crash
  Availability: 3/3 = 100%, after crash = 2/3 = 66%
  
- 5 nodes, quorum 3: tolerate 2 crashes
  Availability: 5/5 = 100%, after crash = 4/5 = 80%
  
- Back to 3 nodes, quorum 2: tolerate 1 crash
  Availability: 3/3 = 100%, after crash = 2/3 = 66%

Throughput cost:
- Quorum 2: 2 RTTs for consensus (2 acceptors must respond)
- Quorum 3: 3 RTTs for consensus (3 acceptors must respond)

Latency (assuming 10ms per RTT):
- 2-node quorum: ~10ms (faster but riskier)
- 3-node quorum: ~10ms (same, just more nodes responding)

Bandwidth:
- Each added node increases replication traffic
- [VERIFY] Adding 2 nodes increases traffic 40% (5/3 = 1.67x)

Trade-off: reliability vs operational cost (more nodes = more network, disk)"

## When to Use / When NOT

| Scenario | Two-Phase Reconfig? |
|----------|-------------------|
| Growing cluster (3 → 5 nodes) | YES |
| Removing nodes from cluster | YES |
| Planned maintenance (decom one node) | YES |
| Emergency: partition detected | MAYBE (manual intervention) |
| Simple 3-node cluster | NO (too simple to change) |
| Immutable infrastructure (blue-green deploy) | NO (redeploy, don't reconfigure) |

## Checklist: Membership Change Correctness

- [ ] Joint consensus: Does quorum requirement include both old and new?
- [ ] Overlap guarantee: After joint, does any leader have both old and new config?
- [ ] Durability: Is joint config written to disk before proceeding to new?
- [ ] Liveness: Can the leader reach quorum during transition?
- [ ] Safety: Can old and new configs both commit without overlap violation?
- [ ] Crash recovery: After leader crash during transition, can new leader continue?
- [ ] Catchup: Do new members catch up logs before becoming voting members?
- [ ] Rollback: If reconfiguration fails, can you abort and retry?

## Common Wrong Answers

1. "Just add a node and update quorum size." → UNSAFE, split brain possible.
2. "Two-phase reconfiguration prevents all problems." → NO, still needs quorum for each phase.
3. "Any two configurations overlap automatically." → NO, must design carefully.
4. "Removing nodes is harder than adding." → Actually easier (less coordination).
5. "Membership change can happen in one atomic commit." → NO, needs joint consensus.
6. "Old members can vote after new config commits." → NO, must stop voting.
7. "Reconfiguration is instant." → NO, takes N RTTs (catching up logs, then commits).
