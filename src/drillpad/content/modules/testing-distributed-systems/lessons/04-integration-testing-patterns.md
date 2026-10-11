# Integration Testing Patterns: Real vs Simulated

## Overview

How do you decide between real and simulated tests? This lesson covers:
1. Unit tests (isolated, fast)
2. Integration tests (real network, slower)
3. End-to-end tests (full stack, slowest)
4. When to use each

---

## Test Pyramid

```
           [  E2E Tests ]
              (slow)
           [Integration Tests]
              (medium)
        [Unit Tests]
           (fast)

Rule of thumb:
- 70% unit tests (fast feedback)
- 20% integration (catch realistic issues)
- 10% E2E (catch user-facing bugs)
```

---

## Unit Tests: Isolated Components

```rust
#[test]
fn test_log_replication() {
    let mut log = ReplicaLog::new();
    
    log.append("entry1");
    assert_eq!(log.get(0), "entry1");
    
    log.append("entry2");
    assert_eq!(log.len(), 2);
}
```

**Advantages:**
- Fast (no network)
- Deterministic (no race conditions)
- Easy to debug

**Disadvantages:**
- Don't test real network behavior
- Don't catch integration bugs

---

## Integration Tests: With Real Network

```rust
#[test]
fn test_replication_with_real_network() {
    let server_a = Server::new("localhost:8001");
    let server_b = Server::new("localhost:8002");
    
    server_a.start();
    server_b.start();
    
    server_a.write("key=1");
    thread::sleep(Duration::from_millis(100));  // Wait for replication
    
    assert_eq!(server_b.read("key"), "1");
    
    server_a.stop();
    server_b.stop();
}
```

**Advantages:**
- Tests real network (delays, loss)
- Tests real OS thread scheduling
- More realistic

**Disadvantages:**
- Slow (network latency)
- Flaky (timing varies)
- Hard to debug (too many moving parts)

---

## E2E Tests: Full User Journey

```rust
#[test]
fn test_user_checkout() {
    let client = Client::new("http://localhost:8000");
    
    // Add item
    client.post("/cart/add", {"item": "widget"});
    assert_eq!(client.get("/cart").items.len(), 1);
    
    // Checkout
    client.post("/checkout", {"payment": "card"});
    
    // Verify order created
    let orders = client.get("/orders");
    assert_eq!(orders[0].status, "paid");
    
    // Verify inventory updated
    let inventory = client.get("/inventory/widget");
    assert!(inventory.quantity < original_quantity);
}
```

**Advantages:**
- Tests entire user flow
- Catches bugs that unit tests miss
- Most realistic

**Disadvantages:**
- Very slow (multiple services, network)
- Very flaky (external dependencies)
- Hard to debug (too many components)
- Environment setup is complex

---

## Hybrid Approach: Simulated Integration

Simulate network (deterministic) + real application logic:

```rust
#[test]
fn test_replication_hybrid() {
    let mut sim = Simulation::new();
    
    // Real application logic
    let server_a = RealServer::new(sim.network());
    let server_b = RealServer::new(sim.network());
    
    server_a.start();
    server_b.start();
    
    // Simulated network
    sim.network().set_latency(Duration::from_millis(10));
    
    server_a.write("key=1");
    
    // Advance simulated time
    sim.time = 0..100;  // Simulate 100ms
    
    // Real result
    assert_eq!(server_b.read("key"), "1");
}
```

**Advantages:**
- Fast (simulated network)
- Deterministic (controlled time)
- Tests real application logic
- No flakiness

**Disadvantages:**
- Requires simulation infrastructure
- Might miss OS-level bugs (thread scheduling, cache effects)

---

## Choosing a Test Type

```
Testing: Replication logic?
  → Unit test (logic only)
  
Testing: Replication + network delays?
  → Simulated integration (real app + fake network)
  
Testing: Replication + real network + multiple processes?
  → Integration test
  
Testing: Full user workflow?
  → E2E test
  
Testing: Performance under load?
  → Load test (separate from unit/integration/E2E)
```

---

## Real Example: Payment System

```
Unit test:
  Test: Transaction state machine (pending → charged → settled)
  Time: <1ms
  
Simulated integration test:
  Test: Payment server + Database + Notification service
  Simulate: Network delays, timeout recovery
  Time: <100ms per test
  
Integration test:
  Test: Payment server + Real database + Real notification service
  Test: What if database is slow?
  Time: 1-5 seconds
  
E2E test:
  Test: User adds item → Checkout → Payment processes → Email sent
  Test: Whole user journey
  Time: 10+ seconds
```

---

## When to Skip Tests

```
Don't write unit test for:
  - Trivial getters/setters
  - Auto-generated code (proto, ORM)
  - Vendored dependencies
  
Don't write integration test for:
  - Edge cases (test in unit test)
  - Error paths already tested in unit tests
  - Things that can't fail (like reading config)
  
Don't write E2E test for:
  - Single component behavior
  - Error handling (test in unit tests)
  - Network timeouts (test in integration)
```

---

## Flaky Test Strategies

If tests are flaky:

1. **Increase timeouts** (race condition)
2. **Add retries** (transient failures)
3. **Use deterministic testing** (simulated time)
4. **Reduce dependencies** (fewer things can fail)

Example:
```rust
#[test]
fn test_replication() {
    for attempt in 0..3 {  // Retry flaky test
        match run_test() {
            Ok(()) => return,
            Err(e) => eprintln!("Attempt {} failed: {}", attempt, e),
        }
    }
    panic!("Test failed after 3 attempts");
}
```

---

## Key Takeaways

1. **Unit tests** = fast, deterministic, test logic
2. **Integration tests** = slower, realistic, catch real bugs
3. **E2E tests** = slowest, user-focused, highest confidence
4. **Simulated integration** = best of both (fast + realistic)
5. **Test pyramid** = mostly units, some integration, few E2E

---

## Q&A

**Q: Should I write E2E tests?**

Yes, but sparingly. Focus on user journeys, not edge cases.

**Q: Why are integration tests flaky?**

Network timing varies. Use deterministic simulation or increase timeouts.

**Q: Can I skip integration tests and just do unit + E2E?**

Possible, but you'll miss bugs in the middle layer. Better to have some integration tests.
