# Production Patterns: Thread Pools, Work Stealing, Backpressure

## Problem: Naive Threading

```cpp
// Naive approach: spawn a thread per task
for (Task t : tasks) {
    std::thread([t]() { process(t); }).detach();
}
```

**Problems:**
- Spawning threads is expensive (~1-10 microseconds per thread)
- No limit on thread count (1M tasks = 1M threads = system crash)
- Context switching overhead (100 threads = thrashing)
- Resource limits (file descriptors, memory, CPU cores)

**Result:** Slower than single-threaded for most workloads.

## Pattern 1: Thread Pool

Pre-create N threads, distribute work:

```cpp
class ThreadPool {
    int num_threads = 8;  // Fixed, based on CPU cores
    std::queue<Task> queue;
    std::vector<std::thread> workers;
    
public:
    ThreadPool(int n) : num_threads(n) {
        for (int i = 0; i < num_threads; i++) {
            workers.push_back(std::thread([this]() {
                while (true) {
                    Task t = queue.pop();  // Block if empty
                    if (t.is_shutdown) break;
                    process(t);
                }
            }));
        }
    }
    
    void submit(Task t) {
        queue.push(t);  // Enqueue, worker picks it up
    }
};

// Usage:
ThreadPool pool(8);  // 8 workers
for (Task t : tasks) {
    pool.submit(t);
}
```

**Benefits:**
- Fixed thread count (no unbounded growth)
- Threads reused (no spawn/destroy overhead)
- Easy to tune (set workers = CPU cores)

**Cost:** ~1% CPU per empty task check

## Pattern 2: Work Stealing (Reducing Latency)

Problem: Thread pool has 8 workers, but one worker gets slow tasks (takes 10x longer).

Result: 7 workers finish, 1 worker still busy (7 cores idle).

Solution: Work stealing queue (each worker has its own queue, steals from others' queues when idle):

```cpp
class WorkStealingPool {
    std::vector<std::deque<Task>> local_queues;  // One queue per worker
    
public:
    void worker_thread(int id) {
        while (true) {
            Task t;
            
            // First: check own queue
            if (!local_queues[id].empty()) {
                t = local_queues[id].front();
                local_queues[id].pop_front();
            } else {
                // Own queue empty: steal from another's queue
                for (int other = 0; other < num_workers; other++) {
                    if (!local_queues[other].empty()) {
                        t = local_queues[other].back();  // Steal from end
                        local_queues[other].pop_back();
                        break;
                    }
                }
            }
            
            if (!t) continue;  // No work available, spin or sleep
            process(t);
        }
    }
};
```

**Benefits:**
- Better utilization (idle workers steal work)
- Lower latency (less queueing)
- Scales to many workers

**Cost:** Slightly more complex, atomic operations on queues

## Pattern 3: Backpressure (Flow Control)

Problem: Tasks arrive faster than workers can process.

Result: Queue grows unbounded → memory exhausted → crash.

Solution: Limit queue depth, apply backpressure (reject/block new tasks):

```cpp
class ThreadPoolWithBackpressure {
    std::queue<Task> queue;
    const int MAX_QUEUE_SIZE = 10000;  // Limit
    std::mutex lock;
    
public:
    bool submit(Task t) {
        std::lock_guard<std::mutex> l(lock);
        
        if (queue.size() >= MAX_QUEUE_SIZE) {
            return false;  // Reject: apply backpressure
        }
        
        queue.push(t);
        return true;
    }
};

// Caller's responsibility:
while (!pool.submit(t)) {
    // Backpressure: pool is full
    // Either: wait, reduce input, or drop (depending on policy)
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
}
```

**Benefits:**
- Prevents unbounded memory growth
- Forces caller to handle overload
- Prevents cascading failures

**Cost:** Caller must handle rejection

## Real-World Pattern: Thread Pool + Backpressure + Work Stealing

```cpp
// Used in: Kafka, RocksDB, vLLM, etc.

ThreadPool pool(8);

for (Task t : incoming_tasks) {
    while (!pool.submit(t)) {
        // Backpressure: pool is full
        // Wait before retrying
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}
```

## Metrics: Knowing If You're Scaling Right

| Metric | Red Flag | Good |
|---|---|---|
| **Queue depth** | >MAX_QUEUE_SIZE | <20% of MAX |
| **Worker utilization** | <30% (wasted cores) | >80% |
| **Context switches** | >N * 1000/sec (per core) | <100/sec (per core) |
| **Tail latency (P99)** | >10x median | <2x median |
| **Rejected tasks** | >1% | 0% |

## Interview Pattern: Scaling Task Processing

```
Q: "You have a service that processes user requests.
   Currently single-threaded, 1000 requests/sec.
   You want to handle 10,000 requests/sec. How?"

Weak answer:
  "Create 10 threads"
  (❌ No backpressure, no load balance, no work stealing)

Strong answer:
  "Use a thread pool with work stealing + backpressure:
  
  1. Baseline:
     - Single thread: CPU-bound? I/O-bound?
     - If CPU-bound: can't exceed 1 core capacity
     - If I/O-bound: can add more threads
  
  2. Assume I/O-bound (typical for web requests):
     - Current: 1 thread, 1000 req/sec
     - Bottleneck: waiting for I/O (not CPU)
  
  3. Solution:
     - Thread pool size = min(num_cores, requests_in_flight)
     - Typical: 8-16 threads for 4-core machine
     - Why? More threads = better I/O overlap, but too many = context switching
  
  4. Implementation:
     ThreadPool pool(8);
     
     for (Request r : incoming) {
       if (!pool.submit(r)) {
         // Backpressure: queue is full (prevent memory explosion)
         wait_and_retry();
       }
     }
  
  5. Monitoring:
     - Track queue depth and latency
     - If P99 latency > 10x median: add threads or reject early
     - If P99 latency < 2x median: threads are well-balanced
  
  6. Expected throughput:
     - If requests are 100ms I/O:
       1 thread: 1000/sec (10 in-flight)
       8 threads: 8000/sec (80 in-flight)
       16 threads: 16000/sec (160 in-flight) → hitting 10K target
  
  7. If still not enough:
     - Horizontal scale: multiple machines
     - Load balance across machines"

Why this signals good judgment:
  - You measured the bottleneck (CPU vs I/O)
  - You sized threads correctly (not arbitrary)
  - You understood backpressure (prevents cascading failure)
  - You'd monitor latency percentiles (not just average)
```

## Common Production Issues

| Issue | Symptom | Fix |
|---|---|---|
| **Thread count too low** | Low CPU utilization, high latency | Increase threads |
| **Thread count too high** | Context switch overhead, thrashing | Decrease threads |
| **No backpressure** | Memory grows unbounded, crash | Add queue size limit |
| **Task starvation** | Some tasks never execute (low priority) | Priority queues, fair scheduling |
| **Lock contention** | Workers fight over queue lock | Lock-free queue or work stealing |

## What This Signals

- You've scaled systems from single-threaded to multi-threaded
- You understand the tradeoffs (threads, cores, I/O, context switching)
- You know backpressure prevents cascading failures
- You'd measure latency percentiles and queue depth (not just throughput)
