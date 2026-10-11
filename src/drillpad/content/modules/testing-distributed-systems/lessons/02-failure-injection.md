# Failure Injection: Testing What Breaks

## Overview

You can't test failure modes without injecting them. This lesson covers:
1. Network failures (delays, packet loss, reordering)
2. Byzantine failures (corrupt data, wrong answers)
3. Timing failures (timeouts, stalls)
4. Recovery testing

---

## Network Failures

**Latency:** Network is slow

```rust
let network = MockNetwork::new();
network.set_latency(Duration::from_secs(1));  // 1 second delay

server_a.send_to(server_b, msg);
// Message doesn't arrive for 1 second
```

**Packet Loss:** Network drops messages

```rust
network.set_packet_loss(0.1);  // Drop 10% of messages

server_a.send_to(server_b, msg);
// 10% chance message is lost (never arrives)
```

**Reordering:** Messages arrive out of order

```rust
network.set_reorder_probability(0.05);  // 5% out of order

server_a.send(msg1);
server_a.send(msg2);
// server_b might receive msg2, then msg1
```

**Partition:** Complete network split

```rust
network.partition(server_a, server_b);  // No communication between A ↔ B
server_a.send_to(server_b, msg);  // Message never arrives
network.heal();
```

---

## Byzantine Failures

**Corruption:** Data corruption during transmission

```rust
network.set_corruption_rate(0.01);  // 1% corruption

server_a.write("checksum=abc");
// 1% chance server_b reads "checksum=xyz" (bit flip)
```

**Wrong Answers:** Server returns incorrect data

```rust
server_a.set_byzantine(true);  // Server A now lies
result = server_a.read("key");
// Result might be wrong even if key exists
```

**Crash:** Server goes offline

```rust
server.crash();  // Server stops responding
server.send(msg);  // No response
// Server loses all in-memory state

server.recover();  // Server comes back online (with persistent data only)
```

---

## Timing Failures

**Timeout:** Operation takes too long

```rust
network.set_operation_timeout(Duration::from_millis(100));

server_a.send_to(server_b, msg);  // Might timeout
match response {
    Ok(data) => { /* got response */ }
    Err(TimeoutError) => { /* operation timed out */ }
}
```

**Clock Skew:** Servers have different times

```rust
server_a.clock.set_offset(Duration::from_secs(1));  // Server A is 1s fast
server_b.clock.set_offset(Duration::from_secs(-2));  // Server B is 2s slow

// A thinks it's 10:01, B thinks it's 9:58
// Consensus algorithms might break
```

**Slow Node:** One server is much slower

```rust
server_c.set_slowdown(10);  // Server C is 10x slower

// A and B respond in 1ms
// C responds in 10ms
// If system waits for all, tail latency is 10ms
```

---

## Cascading Failures

Test what happens when multiple things fail:

```rust
#[test]
fn test_cascading_failure() {
    let [a, b, c] = create_servers(3);
    
    // Primary fails
    a.crash();
    // System elects new primary (B)
    assert_eq!(b.is_primary(), true);
    
    // New primary fails
    b.crash();
    // System elects C as backup
    assert_eq!(c.is_primary(), true);
    
    // All failed, system should handle gracefully
    let result = a.read("key");
    assert!(result.is_err());  // Can't read from dead servers
}
```

---

## Recovery Testing

After failure, can the system recover?

```rust
#[test]
fn test_recovery() {
    let [a, b, c] = create_servers(3);
    
    // Normal operation
    a.write("key=1");
    
    // Crash 2/3 servers
    b.crash();
    c.crash();
    
    // System is down (only 1/3 servers alive, need quorum)
    assert!(a.read("key").is_err());
    
    // Recover servers
    b.recover();
    // Now 2/3 are alive (quorum), can read
    assert_eq!(a.read("key"), "1");
    
    c.recover();
    // All 3 alive again
    assert_eq!(a.read("key"), "1");
    assert_eq!(c.read("key"), "1");  // C caught up
}
```

---

## Test Scenarios

**Single Failure:**
```
Server A crashes → System must handle
```

**Multiple Simultaneous Failures:**
```
Servers A + B crash → Does quorum work?
```

**Transient Failure:**
```
Server A crashes for 5 seconds, then recovers → Can catch up?
```

**Cascading Failure:**
```
A crashes → B elected leader → B crashes → C elected
System remains operational through all transitions
```

**Arbitrary Failure:**
```
Random sequence of failures + recoveries
Property: System never loses committed data
```

---

## Implementation Example

```rust
#[test]
fn test_consensus_under_failure() {
    let mut sim = Simulation::new();
    let [a, b, c] = sim.create_servers(3);
    
    // Scenario 1: Single failure
    sim.crash(a);
    b.become_leader();
    assert!(b.is_leader());
    
    // Scenario 2: Recover + new failure
    sim.recover(a);
    sim.crash(b);  // Different server fails
    a.become_leader();  // A takes over
    assert!(a.is_leader());
    
    // Scenario 3: Cascading
    sim.crash(a);
    c.become_leader();
    assert_eq!(c.term(), 2);  // New term after leadership change
}
```

---

## Key Takeaways

1. **Inject failures systematically** (don't hope they're handled)
2. **Test each failure type** (latency, loss, corruption, crash)
3. **Test recovery** (can system come back after failure?)
4. **Test cascading** (what if multiple things fail?)
5. **Verify invariants** (data loss, split brain, etc.)

---

## Q&A

**Q: How many failure scenarios should I test?**

At minimum: single node crash, network partition, transient failures.
Ideally: combinatorial (all combinations of failures).

**Q: What if I can't inject all failures?**

Test the most likely (node crashes, network partitions).
Document what you didn't test.

**Q: How do I know my failure test is realistic?**

Compare to production incidents. Did your test find the same issues?
