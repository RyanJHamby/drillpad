# Distributed Systems: Consensus Algorithms (Raft, Quorum Voting)

## Typical Contexts: payments, cloud platforms, and trading systems

**Problem:** You have 3 database replicas (A, B, C). Network partitions, and A can't reach B or C. What does A do?

- **Bad:** A thinks it's still the leader, accepts writes → divergence (split brain)
- **Better:** A waits to confirm with B and C → if partition heals, consistent
- **Best:** Use consensus algorithm (Raft) → automatic leader election, quorum voting

**Why hard:** Must tolerate network partitions while maintaining consistency.

---

## The Split Brain Problem

```
Normal state:
  Leader A, Replicas B, C
  Write: "balance = 100"
  A → B, C (sync)
  
Network partition:
  A ↔ [B, C]
  
Bad scenario (no consensus):
  A: "I'm still leader, accept new write: balance = 200"
  B+C: "A is dead, promote B to leader"
  B: "I'm leader, accept write: balance = 150"
  
  Now we have divergence:
  A says balance = 200
  B says balance = 150
  C says balance = 150
  
  Partition heals:
  A and B merge → CORRUPTION
```

---

## Quorum Voting (Simple Consensus)

```
Total replicas: 3 (A, B, C)
Quorum: majority = 2

Write "balance = 100":
  Leader A: ask B and C to write
  B: yes, wrote it
  C: yes, wrote it
  Leader: quorum achieved (A + 2) = 3 nodes, write is durable
  
Network partition (A isolated):
  A: try to write "balance = 200"
  B: no (A is unreachable)
  C: no (A is unreachable)
  A: quorum NOT achieved (only 1 out of 3), REJECT write
  
  B+C: elect new leader (quorum = 2)
  B elected, can still make decisions (has quorum)
  
Result: no corruption, writes possible only where quorum exists
```

---

## Raft Algorithm (Simplified)

```
States:
  - FOLLOWER (default, follow leader)
  - CANDIDATE (running for leader)
  - LEADER (elected, make decisions)

Heartbeat mechanism:
  Leader → Followers: "I'm alive, log entries are [1, 2, 3]"
  Followers: acknowledge
  
Timeout election:
  Follower: don't hear from leader for 150ms
  Follower → CANDIDATE
  CANDIDATE: "vote for me"
  If get majority votes → LEADER
  If see LEADER with higher term → FOLLOWER
  
Log replication:
  Leader: receive write, add to log as uncommitted
  Leader: send to followers
  Followers: acknowledge
  Leader: if quorum acknowledges, COMMIT (apply to state machine)
  Leader: tell followers "this entry is committed"
  Followers: apply to state machine
```

---

## Real Scenario: Database Replication

```
3-node cluster: A (leader), B (replica), C (replica)

Normal write:
  Client → A: "set key=X"
  A: add to log [term=1, index=5, entry="set key=X"]
  A → B: "replicate index 5"
  A → C: "replicate index 5"
  B: ack
  C: ack
  A: quorum = 3/3, commit
  A → B, C: "commit index 5"
  All: apply to state machine
  Client: "ok"

A fails (network partition):
  B, C: don't hear from A for 150ms
  B, C → CANDIDATES
  B: "vote for me"
  C: "vote for me"
  One wins (say B), becomes LEADER
  
A comes back online:
  A: "I'm the leader, have index 10"
  B: "No, I'm the leader (term=2, index=7)"
  A: "You have higher term, I'll follow you"
  A: rolls back uncommitted entries from index 8-10
  A: replicates from B to catch up
  
Result: no corruption, all nodes converge on same log
```

---

## Implementation: Python Raft Sketch

```python
import time
import random
from enum import Enum

class NodeState(Enum):
    FOLLOWER = 1
    CANDIDATE = 2
    LEADER = 3

class RaftNode:
    def __init__(self, node_id, peers):
        self.node_id = node_id
        self.peers = peers  # list of other node IDs
        
        # Persistent state
        self.current_term = 0
        self.voted_for = None
        self.log = []  # list of {term, index, entry}
        
        # Volatile state
        self.state = NodeState.FOLLOWER
        self.commit_index = 0
        self.last_applied = 0
        
        # Leader state
        self.next_index = {}  # per follower
        self.match_index = {}  # per follower
        
        # Timing
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(1.5, 3.0)  # 1.5-3 seconds
    
    def tick(self):
        """Called regularly (e.g., every 100ms)."""
        now = time.time()
        
        if self.state == NodeState.LEADER:
            self._send_heartbeat()
        elif now - self.last_heartbeat > self.election_timeout:
            self._start_election()
    
    def _send_heartbeat(self):
        """Leader sends heartbeat to all followers."""
        self.last_heartbeat = time.time()
        for peer in self.peers:
            # Send log entries and current commit_index
            self._send_append_entries_rpc(peer)
    
    def _start_election(self):
        """Follower timeout, become candidate."""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = time.time()
        self.election_timeout = random.uniform(1.5, 3.0)
        
        votes = 1  # vote for self
        for peer in self.peers:
            if self._request_vote_rpc(peer, self.current_term):
                votes += 1
        
        if votes > len(self.peers) // 2:
            self._become_leader()
    
    def _become_leader(self):
        """Candidate wins election, become leader."""
        self.state = NodeState.LEADER
        for peer in self.peers:
            self.next_index[peer] = len(self.log)
            self.match_index[peer] = 0
        self._send_heartbeat()
    
    def apply_entry(self, entry):
        """Client request, append to log."""
        if self.state != NodeState.LEADER:
            return False  # not leader
        
        self.log.append({
            'term': self.current_term,
            'index': len(self.log),
            'entry': entry
        })
        
        # Replicate to followers asynchronously
        # (simplified; real Raft does RPC)
        return True
    
    def _request_vote_rpc(self, peer, term):
        """Ask peer for vote. Returns True if voted."""
        # In real code: network RPC
        # For demo: return random
        return random.random() > 0.3
    
    def _send_append_entries_rpc(self, peer):
        """Send log entries to follower."""
        # In real code: network RPC with log entries
        pass
```

---

## Paxos vs Raft

```
Paxos (older):
  ├─ Proven correct (difficult proof)
  ├─ Less intuitive
  └─ Used by Google Chubby, Apache Zookeeper
  
Raft (newer):
  ├─ Designed for understandability
  ├─ Similar fault tolerance
  └─ Used by etcd, Consul, CockroachDB
```

---

## Design Decisions

**Why quorum (majority) instead of unanimous?**
- Unanimous: all nodes must agree → can't tolerate any failure
- Quorum: majority agrees → can tolerate up to N/2 failures

**Why election timeout randomization?**
- Without: all followers timeout at same time → thundering herd
- With: stagger timeouts → one winner emerges

**Why log-based replication?**
- Log is immutable record of events
- Can replay log on new replicas
- Easy to debug divergences

**Why term numbers?**
- Prevent old leaders from causing trouble
- Followers reject stale leaders (low term)

---

## Q&A

**Recall 1:** You have 5 replicas (A, B, C, D, E). A is partitioned (can't reach others). Can A still be leader?

*Must-say:*
- Quorum = 3 (majority of 5)
- A has only itself = 1 vote
- A needs 3 votes to be leader
- A cannot achieve quorum alone
- A cannot be leader (rejects writes)

**Probe 1:** A is leader. Writes entry at index 10. Replicates to B and C. A then crashes. B elected new leader. What happens to entry 10?

*Expected:*
- If A received acks from B and C: entry 10 is committed, B has it, safe
- If A didn't ack: entry 10 is NOT committed, B rolls back, safe
- Either way: no data loss (consistency)

**Numeric 1:** Election timeout: 1.5-3 seconds. How long until candidate gives up and retries?

*Working:*
- Candidate starts election
- Waits for majority votes
- If no majority: timeout, new election
- Typical: waits ~150ms for votes, then timeout
- Then: new timeout 1.5-3s, retry

---

## Questions for the Interviewer

- Do you use Raft or Paxos? (or custom?)
- How do you handle network partitions? (automatic failover?)
- What's your quorum size? (3, 5, 7 replicas?)
- How long is election timeout? (tuned for latency?)
- Have you had split brain bugs? (how did you debug?)
- Do you run Raft on leader only, or all replicas? (complexity tradeoff)

