# Deadlock & Livelock: Detection & Prevention

## Deadlock: The Classic Problem

```cpp
// Account 1 and Account 2 (both exist)
Account account1(balance: 100);
Account account2(balance: 50);

// Thread 1: Transfer $10 from account1 to account2
void transfer_1to2() {
    account1.lock();           // Lock account 1
    sleep(100ms);              // Simulate work
    account2.lock();           // Try to lock account 2... WAIT
}

// Thread 2: Transfer $5 from account2 to account1
void transfer_2to1() {
    account2.lock();           // Lock account 2
    sleep(100ms);              // Simulate work
    account1.lock();           // Try to lock account 1... WAIT
}

// Timeline:
// T=0ms:   Thread 1 acquires lock on account1
// T=0ms:   Thread 2 acquires lock on account2
// T=100ms: Thread 1 waits for account2 (held by Thread 2)
// T=100ms: Thread 2 waits for account1 (held by Thread 1)
// T=∞:     Both threads wait forever
```

**Deadlock definition:** Two or more threads waiting for each other to release locks in a cycle.

## Conditions for Deadlock (All 4 must be true)

1. **Mutual exclusion:** Resources can't be shared (locks are exclusive)
2. **Hold and wait:** Thread holds one lock while waiting for another
3. **No preemption:** Can't force a thread to release its lock
4. **Circular wait:** A → B → A (lock dependency cycle)

To prevent deadlock, **break any one of these conditions**.

## Prevention Strategies

### Strategy 1: Lock Ordering (Most Practical)

**Lock locks in a consistent order (e.g., by ID):**

```cpp
void transfer(Account& from, Account& to, int amount) {
    // Always lock in order: smaller ID first
    Account& first = (from.id < to.id) ? from : to;
    Account& second = (from.id < to.id) ? to : from;
    
    first.lock();
    second.lock();
    
    // Transfer
    from.balance -= amount;
    to.balance += amount;
    
    second.unlock();
    first.unlock();
}

// Now both threads lock account1 first, then account2
// No cycle, no deadlock
```

**Why it works:** Eliminates circular wait (always lock 1 → 2, never 2 → 1)

**Cost:** Requires discipline (must always lock in same order)

### Strategy 2: Timeout-Based Release

```cpp
bool acquire_with_timeout(Mutex& lock1, Mutex& lock2, int timeout_ms) {
    if (!lock1.try_lock_for(timeout_ms)) {
        return false;
    }
    
    if (!lock2.try_lock_for(timeout_ms)) {
        lock1.unlock();  // Release lock1 if we can't get lock2
        return false;
    }
    
    return true;
}

// Usage:
while (!acquire_with_timeout(account1.lock(), account2.lock(), 100)) {
    // Deadlock detected, retry from scratch
}
```

**Why it works:** If thread waits too long, it releases both locks and retries

**Cost:** Extra retries, but avoids deadlock

### Strategy 3: Single Lock (Simplest)

```cpp
Mutex global_lock;  // One lock for all accounts

void transfer(Account& from, Account& to, int amount) {
    global_lock.lock();
    from.balance -= amount;
    to.balance += amount;
    global_lock.unlock();
}
```

**Why it works:** Only one lock, no cycles

**Cost:** Bottleneck (all threads wait for the same lock, throughput suffers)

## Livelock: Threads Busy But Stuck

```cpp
void transfer(Account& from, Account& to, int amount) {
    while (true) {
        if (from.try_lock()) {
            if (to.try_lock()) {
                from.balance -= amount;
                to.balance += amount;
                from.unlock();
                to.unlock();
                return;
            }
            from.unlock();
        }
        
        // Retry immediately (without backoff)
        // Both threads keep retrying, never progress
    }
}
```

**Livelock definition:** Threads keep running (not blocked on locks) but make no progress.

**Why it happens:** Both threads keep unlocking and retrying without backoff.

**Fix: Add randomized backoff**

```cpp
void transfer(Account& from, Account& to, int amount) {
    while (true) {
        if (from.try_lock()) {
            if (to.try_lock()) {
                from.balance -= amount;
                to.balance += amount;
                from.unlock();
                to.unlock();
                return;
            }
            from.unlock();
        }
        
        // Backoff: wait random time before retry
        std::this_thread::sleep_for(
            std::chrono::milliseconds(rand() % 100)
        );
    }
}
```

**Why it works:** Threads retry at different times, eventually one succeeds

## Deadlock Detection

For complex systems, deadlock detection is automated:

```
1. Build a lock dependency graph
2. Check for cycles
3. If cycle found, either:
   - Kill one thread (and retry)
   - Break the deadlock (force unlock)
   - Report error
```

Most databases do this automatically (PostgreSQL detects circular waits and kills one query).

## Interview Pattern: Preventing Deadlock

```
Q: "You're building a payment system. Transfers between accounts
   involve locking both accounts. How do you prevent deadlock?"

Weak answer:
  "Use a global lock"
  (❌ Correct but kills throughput)

Strong answer:
  "Lock ordering. Specifically:
  
  1. Assign each account a unique ID (or use memory address)
  2. Always lock the lower ID first:
  
     void transfer(Account& from, Account& to, int amount) {
       Account& first = (from.id < to.id) ? from : to;
       Account& second = (from.id < to.id) ? to : from;
       
       first.lock();
       second.lock();
       // Transfer
       second.unlock();
       first.unlock();
     }
  
  3. Why this works:
     - Circular wait is impossible (always lock 1 → 2)
     - Two threads transferring between same accounts always lock in same order
     - No cycle = no deadlock
  
  4. Cost:
     - Negligible: one comparison per transfer
     - Throughput: near-perfect (no lock contention beyond necessary)
  
  5. Alternative if you need to try-lock (non-blocking):
     Add timeout + retry:
     while (!try_lock_both_with_timeout(from, to, 100ms)) {
       // Retry from scratch
     }
     
     Jitter: random backoff prevents thundering herd"

Why this signals good judgment:
  - You knew lock ordering eliminates circular wait
  - You chose the efficient solution (not global lock)
  - You understood the cost/benefit tradeoff
  - You had a fallback strategy (timeout-based)
```

## Common Pitfalls

| Pitfall | Symptom | Fix |
|---|---|---|
| **Different lock orders in different functions** | Random deadlocks in production | Enforce lock ordering in code review |
| **Nested lock acquisition without consistent order** | Intermittent deadlocks | Use lock ordering or single lock |
| **Livelock with busy-wait (no backoff)** | CPU 100% but no progress | Add exponential backoff |
| **Timeout too short** | Retries constantly | Increase timeout, add jitter |

## What This Signals

- You understand the conditions for deadlock (not just "locks cause deadlock")
- You can prevent deadlock (lock ordering is the key)
- You know livelock is distinct from deadlock
- You've thought about practical solutions (not just theory)
