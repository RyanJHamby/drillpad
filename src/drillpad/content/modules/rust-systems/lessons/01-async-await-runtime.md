# Async/Await and Tokio: Spawning Tasks, Buffered Channels, Latency

## Tokio Runtime: M:N Threading

Tokio spawns N OS threads (usually = CPU cores), runs M tasks on them (M >> N).

```
OS thread pool: 8 threads (for 8-core CPU)
Task queue: 1000s of async tasks
Task scheduler: work-stealing, fair scheduling

Task spawning:
  tokio::spawn(async { ... })  // cost: ~1 μs, allocates task struct
  Task gets queued, executed by next free thread
  
Blocking task (mistake):
  tokio::spawn(std::thread::sleep(1000ms))  // BLOCKS entire OS thread
  Other 1000 tasks on that thread are starved for 1s
  
Fix: tokio::spawn(tokio::time::sleep(1000ms))  // async, yields thread
```

---

## Channel Buffering and Backpressure

```
Unbuffered channel: sender blocks until receiver is ready
  Throughput: latency-bound (each send waits for recv)
  
Buffered channel: sender writes to buffer, returns immediately
  mpsc::channel(100)  // 100-item buffer
  Throughput: throughput-bound until buffer fills
  
When buffer is full:
  sender.send() returns Err (channel full), sender must handle backpressure
  or use bounded_channel with .send().await (async wait for space)
```

---

## Latency in Tokio

```
Task 1 (light): does 1 μs of work
Task 2 (heavy): does 100 ms of work (CPU-bound)

If both spawned:
  Task 1 waits for Task 2 to yield
  Task 2 doesn't yield (CPU-bound, no .await)
  Task 1 sees 100 ms latency (unfair)
  
Fix: use blocking::spawn_blocking(task_2) to run on separate thread pool
```

