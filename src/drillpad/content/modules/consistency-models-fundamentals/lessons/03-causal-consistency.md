# Causal Consistency: Between Strong & Eventual

## The Problem with Eventual Consistency

```
User A posts: "I'm hiring engineers"
User B replies: "I'm interested!"

Email to User A says: "User B replied to your post"

But when User A reads the feed, they see:
  [Reply from User B]
  [Original post from User A] ← Wrong order!

User A thinks: "Who is User B replying to?"
```

**Problem:** Eventual consistency allows out-of-order reads for causally related events.

**Solution:** Causal consistency (maintain causal order, but allow some staleness).

## Causal Consistency Definition

**If event A causally precedes event B, all viewers see A before B.**

Causality: A → B if:
1. Same user: User writes A, then reads and responds with B
2. Explicit dependency: B references A (message thread)
3. Read-from: User reads A, then writes B based on A's content

## How Causal Consistency Works

### Mechanism: Version Vectors

```
Replica 1 tracks: A wrote version (A=5, B=3, C=2)
This means: "I've seen 5 writes from A, 3 from B, 2 from C"

When new write arrives, it includes its version vector:
  Write: "C replies" with vector (A=5, B=3, C=3)

Replica 2 checks:
  Replica 2 has: (A=4, B=3, C=2)
  
  Does Replica 2 have all predecessors?
    A=5? No (only has 4) → Wait
    B=3? Yes
    C=3? No (only has 2) → Wait
  
  Once Replica 2 gets all preceding writes, it applies this write
```

**Result:** Writes are applied in causal order.

## Causal vs Eventual vs Strong

| Property | Eventual | Causal | Strong |
|---|---|---|---|
| **Latency** | Lowest | Medium | Highest |
| **Causal order guaranteed** | No | Yes | Yes |
| **Staleness possible** | Yes | Yes | No |
| **Conflict-free** | No | No | Yes |
| **Coordination cost** | Low | Medium | High |

## Pitfall 1: Version Vector Explosion

```
With N replicas, version vector has size N:
  (replica1, replica2, replica3, ..., replicaN)

If you have 1000 replicas:
  Version vector: 8KB per write (1000 * 8 bytes)
  10M writes: 80GB of metadata
```

**Fix:**
- Use interval tree (compress adjacent increments)
- Use hash of version vector (accept false positives)
- Limit replicas in the consistency group

## Pitfall 2: Causality Not What You Think

```
Thread 1 reads X
Thread 2 (unrelated) writes Y

Thread 1 is NOT causally dependent on Y (different threads)
But causal consistency might treat them as related (time-based)
```

**Fix:** Be explicit about dependencies.

## Interview Pattern: Choosing Consistency

```
Q: "Your system has user comments and likes.
   Comments are causally ordered (thread).
   Likes are independent.
   How do you handle consistency?"

Weak answer:
  "Use strong consistency for everything"
  (❌ Unnecessarily slow)

Strong answer:
  "Different strategy per data type:
  
  1. Comments (causally ordered):
     - Use causal consistency
     - Version vectors track comment thread
     - Comment replies always see parent
     - Cost: 10-50ms latency (worth it for correctness)
  
  2. Likes (independent):
     - Use eventual consistency
     - No causal dependency between likes
     - Cost: minimal latency
  
  3. Implementation:
     Comments:
       write_causal(thread_id, comment_id, content)
       read_ordered(thread_id) → returns comments in causal order
     
     Likes:
       write_eventual(post_id, user_id)
       read_eventual(post_id) → returns like count (might be slightly stale)
  
  4. Hybrid benefits:
     - Comments are 5% of data but critical
     - Likes are 95% of data but can be eventual
     - Overall: mostly fast (eventual), critical path is correct (causal)
  
  5. Monitoring:
     - Track comment read latency (should see causal order)
     - Track like staleness (acceptable lag)
     - If comment latency > 100ms, increase replicas"

Why this signals good judgment:
  - You didn't use one consistency model for everything
  - You understood causal order is important for threads
  - You let likes be eventual (not everything is critical)
  - You're pragmatic about latency vs correctness
```

## When Causal Consistency Is Right

| Use Case | Consistency | Why |
|---|---|---|
| **Message threads** | Causal | Replies must see parent |
| **Comments on posts** | Causal | Threads need order |
| **Collaborative editing** | Causal | Edits must see prior edits |
| **Social media timeline** | Eventual | Order matters less |
| **Analytics** | Eventual | Approximate is fine |

## Real-World Example: Cassandra + Quorum Reads

```
Cassandra uses quorum reads to approximate causal consistency:

Write: quorum=2 (write to 2/3 replicas before returning)
Read: quorum=2 (read from 2/3 replicas before returning)

Result: Very high probability that read includes the write
(unless the specific replicas diverged, which is rare)

Not true causal, but cheap approximation.
```

## What This Signals

- You understand causal order matters for some data
- You don't blanket-apply strong or eventual consistency
- You know version vectors (or equivalent tracking) enable causality
- You'd mix consistency models strategically per data type
