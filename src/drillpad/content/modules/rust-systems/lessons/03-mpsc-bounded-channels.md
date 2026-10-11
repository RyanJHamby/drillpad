# Multi-Producer Single-Consumer (MPSC) Bounded Channels

## Overview

MPSC channels are the backbone of concurrent Rust systems. This lesson covers:
1. Why bounded channels are critical for backpressure
2. Channel capacity tuning (how to pick the right size)
3. Deadlock prevention (receiver dropping vs sender stalling)
4. Real-world: batching, flow control, and graceful degradation

---

## Problem: Unbounded Queues Cause OOM

Scenario: You have 100 worker threads pushing work to a single consumer (event loop).

**Unbounded queue (WRONG):**
```rust
let (tx, rx) = mpsc::channel(); // No limit

for i in 0..1000000 {
    tx.send(Task { id: i }).unwrap(); // Queues forever
}
// Result: 1M tasks in memory, process OOM kills
```

**Bounded queue (CORRECT):**
```rust
let (tx, rx) = mpsc::channel(100); // Max 100 pending tasks

for i in 0..1000000 {
    match tx.send(Task { id: i }) {
        Ok(()) => { /* queued */ }
        Err(mpsc::error::TrySendError::Full(_)) => {
            // Queue is full. Options:
            // 1. Block and wait (backpressure)
            // 2. Drop task (shed load)
            // 3. Retry with exponential backoff
        }
    }
}
```

---

## Capacity Tuning

Your channel capacity should reflect:
- Producer throughput (tasks/sec)
- Consumer throughput (tasks/sec)
- Acceptable latency spikes

```
If producers push 100 tasks/sec and consumer processes 80 tasks/sec:
  Queue grows by 20 tasks/sec.
  Without bounded channel, OOM in ~13 hours (1M / 20 = 50k sec).
  
  With bounded channel (capacity=1000):
  Queue fills in 50 seconds, then backpressure kicks in.
  Producer blocks until consumer catches up.
  
  Trade-off: Consumer latency increased by ~10ms (time to drain queue).
```

**General formula:**
```
Capacity = (Peak producer throughput) × (Acceptable latency spike in seconds)

Example:
  Peak: 10k requests/sec
  Acceptable spike: 100ms
  Capacity = 10000 × 0.1 = 1000

This buys you 100ms to respond to a consumer slowdown before backpressure.
```

---

## Deadlock Prevention: Receiver Drop

```rust
// DEADLOCK RISK
fn broken_example() {
    let (tx, rx) = mpsc::channel::<Task>(100);
    
    // Spawn worker that sends
    std::thread::spawn(move || {
        for i in 0..1000 {
            tx.send(Task { id: i }).unwrap(); // Blocks if queue full
        }
    });
    
    // Main thread is busy doing something else
    // Worker blocks on send because queue is full
    // Main thread never reads from rx
    // DEADLOCK: Worker waiting for main thread, main thread not processing rx
}

// FIX: Ensure receiver is actively drained
fn working_example() {
    let (tx, rx) = mpsc::channel::<Task>(100);
    
    std::thread::spawn(move || {
        for i in 0..1000 {
            tx.send(Task { id: i }).unwrap();
        }
    });
    
    // Main thread actively reads
    while let Ok(task) = rx.recv() {
        process_task(task);
    }
}
```

---

## Real-World: Batching Pattern

Batching reduces context switches and improves throughput:

```rust
let (tx, rx) = mpsc::channel(1000);

// Producer: send in bursts
std::thread::spawn(move || {
    let mut batch = Vec::with_capacity(100);
    for item in items {
        batch.push(item);
        if batch.len() == 100 {
            tx.send(batch.clone()).ok(); // Send batch
            batch.clear();
        }
    }
});

// Consumer: process batches
while let Ok(batch) = rx.recv() {
    for item in batch {
        process(item); // Process 100 items before next channel read
    }
}
```

Benefits:
- Fewer channel lock acquisitions (1 per 100 items vs 1 per item)
- Better CPU cache locality (process items sequentially)
- Reduced context switches

---

## Q&A

**Q: Should I use `send()` or `try_send()`?**

Use `send()` if you want backpressure (block producer).
Use `try_send()` if you want to shed load (drop task).

```rust
// Backpressure: block until consumer catches up
tx.send(task).await?;

// Load shedding: drop task if queue full
if let Err(_) = tx.try_send(task) {
    metrics.increment("dropped_tasks");
}
```

**Q: How do I measure channel contention?**

Channel contention = time waiting on send/recv lock.

```rust
// Use a histogram to track send latency
let start = Instant::now();
tx.send(task)?;
histogram.record(start.elapsed());
```

If histogram shows bimodal distribution (fast sends + slow sends), you have contention.

**Q: What if receiver dies?**

```rust
match tx.send(task) {
    Ok(()) => { /* success */ }
    Err(mpsc::error::SendError(_)) => {
        // Receiver dropped. Don't retry.
        eprintln!("Consumer died, exiting producer");
        break;
    }
}
```

---

## Key Takeaways

1. **Always use bounded channels** in production (prevents OOM)
2. **Tune capacity to your workload** (peak throughput × acceptable latency)
3. **Ensure receiver is active** (deadlock = receiver not draining)
4. **Measure channel latency** (histogram, not just avg)
5. **Decide: backpressure or load shedding** (send vs try_send)
