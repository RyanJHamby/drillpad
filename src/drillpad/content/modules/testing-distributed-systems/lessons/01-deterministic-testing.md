# Deterministic Testing: Making Distributed Tests Repeatable

## Overview

Distributed systems are non-deterministic (timing varies, ordering is unpredictable). This lesson covers:
1. Why distributed tests fail randomly
2. Deterministic execution (control time and scheduling)
3. Jepsen-style testing (controlled chaos)
4. Real-world tools (TLA+, Loom, simulation)

---

## The Problem: Non-Determinism

```
Test: "2 servers replicate data consistently"

Run 1: PASS (fast network, good ordering)
Run 2: FAIL (slow network, race condition exposed)
Run 3: PASS (timing changed, race condition doesn't trigger)

Result: Flaky test. Hard to debug.
```

**Root cause:** Network latency, CPU scheduling, disk I/O all vary.

---

## Solution: Controlled Time

Use a simulated clock instead of wall-clock time:

```rust
// Normal: time advances unpredictably
let start = SystemTime::now();
network.send(msg);  // Takes 1-100ms (varies)

// Deterministic: manually control time
let time = SimulatedClock::new();
time.set_time(0);  // Start at time 0

network.send(msg);
// Completes at exactly the time we specify
time.advance_to(100);  // Advance to time 100ms
// Message delivery happens, clock is predictable
```

**Benefits:**
- Runs are reproducible (same input → same output)
- Tests run fast (no real network delays)
- Can test "impossible" scenarios (node down for 30 minutes)

---

## Example: Replication Test

```rust
#[test]
fn test_replication_with_partition() {
    let mut sim = Simulation::new();
    let [server_a, server_b] = sim.create_servers(2);
    
    // Time 0: Both servers online
    sim.time = 0;
    server_a.write("key=1");  // Replicates to B
    assert_eq!(server_b.read("key"), "1");
    
    // Time 100ms: Network partition (A ↔ B disconnected)
    sim.partition(server_a, server_b);
    sim.time = 100;
    
    // Time 200ms: A continues operating
    server_a.write("key=2");  // B doesn't see this
    assert_eq!(server_b.read("key"), "1");  // Stale
    
    // Time 500ms: Partition heals
    sim.heal_partition(server_a, server_b);
    sim.time = 500;
    
    // Time 600ms: Replication catches up
    sim.time = 600;
    assert_eq!(server_b.read("key"), "2");  // Eventually consistent
}
```

---

## Deterministic Scheduling

Even with controlled time, thread scheduling matters:

```
Thread A: Read x
Thread B: Write x = 2
Thread A: Check x

Which runs first? Non-deterministic.

Solution: Manual thread ordering

sim.thread_order = [A, B, A];  // Explicit order
// Now test is reproducible
```

---

## Chaos Engineering with Determinism

Jepsen framework injects failures deterministically:

```rust
#[test]
fn test_byzantine_failure() {
    let mut sim = Simulation::new();
    let [a, b, c] = sim.create_servers(3);
    
    // Normal operation
    sim.time = 0..100;  // Run for 100ms
    // All 3 servers operating normally
    
    // Inject failure: Server A crashes
    sim.crash(a);
    sim.time = 100..200;
    
    // B and C must operate (survive without A)
    b.write("key=99");
    assert_eq!(c.read("key"), "99");
    
    // Inject recovery: A comes back online
    sim.recover(a);
    sim.time = 200..300;
    
    // A catches up to B, C
    assert_eq!(a.read("key"), "99");
}
```

---

## Property-Based Testing

Instead of testing specific scenarios, test properties that should always hold:

```rust
#[property_test]
fn prop_eventual_consistency(writes: Vec<(String, String)>) {
    let mut sim = Simulation::new();
    let [primary, replica] = sim.create_servers(2);
    
    // Apply writes to primary
    for (key, value) in writes {
        primary.write(&key, &value);
    }
    
    // Advance time far enough for replication
    sim.time = 0..10000;  // 10 seconds
    
    // Property: Eventually, all replicas see all writes
    for (key, value) in writes {
        assert_eq!(replica.read(&key), value);
    }
}
```

The test harness tries many different write sequences automatically. If any fail, it reports the minimal failing case.

---

## Real Tools

**TLA+ (specification language):**
```
Spec models the system, tool explores ALL possible interleavings.
Finds bugs before code is written.
Overkill for simple systems, but catches subtle bugs.
```

**Loom (Rust testing):**
```rust
#[loom::test]
fn test_concurrent_counter() {
    loom::model(|| {
        let counter = Arc::new(AtomicUsize::new(0));
        
        let c1 = counter.clone();
        let t1 = thread::spawn(move || {
            c1.fetch_add(1, Ordering::Relaxed);
        });
        
        let c2 = counter.clone();
        let t2 = thread::spawn(move || {
            c2.fetch_add(1, Ordering::Relaxed);
        });
        
        t1.join().unwrap();
        t2.join().unwrap();
        
        // Loom tries all thread orderings, verifies final state
        assert_eq!(counter.load(Ordering::Relaxed), 2);
    });
}
```

Loom exhaustively explores all possible thread interleavings. Slow but thorough.

---

## Key Takeaways

1. **Distributed tests are flaky** (non-determinism)
2. **Controlled time** = reproducible tests
3. **Chaos testing** = inject failures systematically
4. **Property-based** = test invariants, not specific cases
5. **TLA+/Loom** = exhaustive exploration
6. **Simulation** = faster than real tests

---

## Q&A

**Q: Should I use TLA+ for my system?**

If critical and complex (consensus, replication), yes. Otherwise, deterministic testing is enough.

**Q: How long do simulated tests take?**

Fast. 10,000 simulated tests in seconds (vs hours of real network tests).

**Q: Can I test production issues deterministically?**

Yes. Replay the exact timing that caused the bug. Fix code, re-run to verify.
