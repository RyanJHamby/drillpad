# I/O Models & Page Cache: epoll, io_uring, fsync Costs, Zero-Copy

## Overview

High-performance systems live or die by I/O efficiency. This lesson covers:

1. **Blocking vs non-blocking I/O** (select, poll, epoll)
2. **io_uring** (Linux modern async I/O)
3. **Page cache behavior** and when it helps/hurts
4. **fsync cost** and durability trade-offs
5. **Zero-copy patterns** (mmap, sendfile, splice)
6. **DMA (Direct Memory Access)** and why it matters

---

## The Problem: Blocking I/O Doesn't Scale

**Naive blocking I/O:**

```
Web server handling 10,000 connections

Thread per connection:
  Thread A: socket.read()  → blocks on network I/O (wait ~100ms for data)
  Thread B: socket.read()  → blocks on network I/O
  ...
  Thread 10000: socket.read() → blocks

Total: 10,000 threads × ~1-8MB stack memory = 80GB memory (!!)
Cost: 10,000 context switches/second = chaos

Real system: kernel can't handle 10K threads + 10K context switches/sec
Performance: terrible (GC pressure, cache thrashing, overhead)
```

**Solution: Non-blocking I/O + event multiplexing**

```
Single thread, 10,000 connections

Loop:
  events = epoll_wait(fd_set, timeout=10ms)  → Returns ready fds
  for each fd in events:
    if readable:
      data = socket.read(fd, non_blocking)
      process(data)
    if writable:
      socket.write(fd, data, non_blocking)

Cost: 1 thread, 1 memory block, no context switching
Performance: high throughput
```

---

## epoll: The Standard Event Multiplexer

**How epoll works:**

```
epoll_create()  → Create event queue (kernel data structure)
epoll_ctl(ADD, fd, events=EPOLLIN | EPOLLOUT)  → Register fd for events
epoll_wait()    → Block until events ready

Example:
  int ep = epoll_create();
  
  for (int i = 0; i < 10000; i++) {
    int fd = accept();  // New connection
    epoll_ctl(ep, EPOLL_CTL_ADD, fd, EPOLLIN);  // Monitor for reads
  }
  
  while (true) {
    struct epoll_event events[1024];
    int n = epoll_wait(ep, events, 1024, 10);  // Wait up to 10ms
    
    for (int i = 0; i < n; i++) {
      if (events[i].events & EPOLLIN) {
        handle_read(events[i].data.fd);
      }
    }
  }
```

**epoll scalability:**

```
epoll_wait cost:
  - O(n) event delivery (only return ready fds, not all fds)
  - No context switch (still in same thread)
  - Typical: <1ms for 10K connections with 100 ready
  
vs select():
  - O(n) scan of all fds (even idle ones)
  - Returns all fds, must scan for readiness
  - Typical: 10ms+ for 10K connections
  
epoll advantage: only O(k) where k = ready connections
```

**Real impact: Nginx** (web server using epoll)

```
Single process (or one per CPU core) using epoll
Handles 10,000+ concurrent connections efficiently
Memory: ~1-2MB per connection (vs 8MB per thread)
Context switches: minimal (1 per core)
```

---

## io_uring: Modern Async I/O

**epoll limitation: Request + wait cycle**

```
epoll_wait() returns "fd is readable"
Then you call read():
  read(fd) → another syscall
  
Total: 2 syscalls per I/O operation
Cost: 2 × ~100ns = 200ns per syscall = significant at 1M ops/sec
```

**io_uring solution: Batch syscalls**

```
Submission Queue (SQ):
  App writes I/O requests (read, write, fsync, etc.)
  App calls io_uring_submit()  → 1 syscall, submits all pending requests
  
Completion Queue (CQ):
  Kernel writes completed I/O operations
  App polls CQ or waits (io_uring_wait_cqe)
  
Result: One syscall submits N requests, one syscall waits for N completions
  Old way: 2N syscalls
  io_uring: 2 syscalls (amortized)
```

**io_uring example:**

```cpp
struct io_uring ring;
io_uring_queue_init(32, &ring, 0);  // 32-entry queue

// Submit 100 reads
for (int i = 0; i < 100; i++) {
  struct io_uring_sqe *sqe = io_uring_get_sqe(&ring);
  io_uring_prep_read(sqe, fd, buf[i], 4096, offset[i]);
}

// One syscall submits all 100 reads
io_uring_submit(&ring);

// Poll completions (or wait)
struct io_uring_cqe *cqe;
io_uring_wait_cqe(&ring, &cqe);  // One syscall waits for first completion

// Completions arrive asynchronously, kernel notifies
while (io_uring_peek_cqe(&ring, &cqe) == 0) {
  process_result(cqe);
  io_uring_cqe_seen(&ring, cqe);
}
```

**io_uring performance (Linux 5.10+):**

```
1M random file reads:

Traditional read loop:
  for (i = 0; i < 1M; i++) {
    pread64(fd, buf, 4096, offset[i]);
  }
  Time: 2-3 seconds (syscall overhead dominates)

io_uring:
  for (i = 0; i < 1M; i++) {
    Submit read request to SQ
    if (SQ full) {
      io_uring_submit();
      io_uring_wait_cqe();
      process_completions();
    }
  }
  io_uring_submit();  // Final batch
  while (io_uring_cqe_ready()) {
    io_uring_wait_cqe();
    process_completions();
  }
  Time: 1-1.5 seconds (2-3x faster)
```

---

## Page Cache: The Memory-Disk Bridge

**Page cache:** OS buffers disk blocks in memory for speed

```
Read from file:

1st read:
  App: read(fd, buf, 4096)
  Kernel: Page fault (data not in cache)
  Kernel: DMA from disk to page cache (1-10ms)
  Kernel: Copy from page cache to app buffer (100ns)
  Total: 1-10ms

2nd read (same page):
  App: read(fd, buf, 4096)
  Kernel: Page cache hit (in memory)
  Kernel: Copy from page cache to app buffer (100ns)
  Total: 100ns (100x faster!)
```

**Page cache costs: Dirty pages and fsync**

```
Write to file:

1st write:
  App: write(fd, buf, 4096)
  Kernel: Copy to page cache (100ns)
  Kernel: Mark page dirty, don't sync yet
  Return immediately to app
  Total: 100ns (perceived as fast)

Later:
  pdflush (background writer):
    Dirty page → DMA to disk (1-10ms)
  
Real question: When is data actually on disk?
  write() doesn't guarantee durability
  fsync(fd) blocks until all dirty pages written to disk
  
fsync cost:
  Dirty pages = 4096 bytes each
  Disk bandwidth = 1GB/sec
  fsync(one page) = 1ms (includes disk seek time)
  fsync(100 pages) = 100ms
```

**Page cache behavior in practice:**

```
Sequential read (e.g., log file):
  Page 1: cache miss, DMA (1ms)
  Page 2: cache hit (100ns)
  Page 3: cache hit (100ns)
  ...
  Page N: cache hit (100ns)
  
  Result: First page slow, rest fast
  Amortized: (1ms + 999 × 100ns) / 1000 ≈ 0.2ms per page (great!)

Random read (scattered across disk):
  Page 1: cache miss, DMA (1ms)
  Page 50000: cache miss, DMA (1ms, different disk location)
  ...
  
  Each page = cache miss = 1ms
  If working set > memory size: constant misses
  Amortized: 1ms per page (slow)
  
Solution: Keep working set in cache (RAM > data size)
```

---

## fsync: The Performance Killer

**fsync forces data to disk (durability guarantee)**

```
Write without fsync:
  write(fd, data)  → Page cache (100ns)
  App continues
  
Perceived latency: 100ns
Actual data on disk: unknown (pdflush might write in 5 seconds)
Risk: Power loss = data gone

Write with fsync:
  write(fd, data)  → Page cache (100ns)
  fsync(fd)        → Wait for all dirty pages to disk
                     (blocking I/O, 1-100ms depending on how many pages)
  App continues
  
Actual latency: 100ns + fsync_time
Actual data on disk: guaranteed
Risk: None (durability guaranteed)
```

**fsync cost at scale:**

```
Database commit throughput:

No fsync (unsafe):
  1M commits/sec (just page cache)

With fsync (safe):
  fsync = 1-10ms per commit = 100-1000 commits/sec
  
  100-1000x slower! (major bottleneck for databases)
```

**Optimization: Group commit**

```
Request 1: write(txn_1_data) + fsync()  (blocks)
Request 2: write(txn_2_data) + fsync()  (waits for fsync from req 1)
Request 3: write(txn_3_data) + fsync()  (waits for fsync from req 1)

One fsync() flushes all 3 transactions
Cost: 1 × 10ms for 3 commits = 3.3ms per commit (vs 10ms each)

Real benefit:
  With 100 concurrent writes:
    fsync = 10ms
    100 commits × 10ms / 100 = 1ms per commit (10x improvement)
```

---

## Zero-Copy Patterns

**Normal copy (web server sending file):**

```
App: read(fd, buf, 4096)
  Kernel: DMA disk → page cache
  Kernel: Copy page cache → app buffer (4096 bytes, ~1µs)
  
App: send(socket, buf, 4096)
  Kernel: Copy app buffer → kernel socket buffer (4096 bytes, ~1µs)
  Kernel: DMA socket buffer → NIC (4096 bytes, ~10µs)
  
Total: 2 copies + 2 DMAs = overhead
```

**sendfile: Zero-copy**

```cpp
ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);

App: sendfile(socket_fd, file_fd, &offset, 4096)
  Kernel: DMA disk → page cache (if needed)
  Kernel: DMA page cache → NIC directly (no copy to app buffer)
  
Benefit: No copy to/from app space, just DMAs (4x faster)

Real impact:
  Normal: 4KB @ 1µs = 1µs latency
  sendfile: 4KB @ DMA speed only (~10µs, but kernel avoids context switch)
```

**mmap: Memory-mapped I/O**

```cpp
char *p = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);

Accesses:
  p[0]         → page cache (or page fault → DMA if not cached)
  p[4096]      → next page
  ...
  
Benefit: Direct memory access, no read() calls needed
Cost: Page faults on uncached pages

Use case:
  Sequential reads (working set fits in cache)
  Binary search (random access with good locality)
  
Don't use:
  Working set >> memory (constant page faults)
```

**DMA: Direct Memory Access (why it matters)**

```
CPU-driven transfer:
  CPU reads from disk: 1000 cycles
  CPU writes to memory: 1000 cycles
  CPU does other work while waiting: stuck
  
DMA-driven transfer (disk ← → memory without CPU):
  Setup DMA controller: 100 cycles
  CPU: free to do other work
  DMA completes: interrupt (100 cycles to handle)
  
Benefit: CPU doesn't stall during disk I/O
Cost: DMA setup overhead (negligible for large transfers)
```

---

## Q&A

**Q1: Should we always use epoll or io_uring?**

A: "Depends on workload. epoll: simplest, scales to 10K+ connections. io_uring: lower latency if you're doing thousands of I/O operations per second. For web servers (mostly network I/O): epoll. For databases (file I/O): io_uring. For hybrid: benchmark both."

**Q2: Page cache hits are fast, but how do you guarantee working set stays in cache?**

A: "Options: (1) Keep data < RAM size. (2) Use POSIX_FADV_SEQUENTIAL or WILLNEED hints. (3) mmap (OS prefers cached mmap over eviction). (4) Monitor via /proc/meminfo and be conservative. (5) Use page cache pressure tools (cgroups memory limits)."

**Q3: Does fsync hurt write throughput?**

A: "Yes, severely. fsync = 1-100ms per call. For 1000 writes/sec, you can only afford 1 fsync per millisecond (group-commit N writes per fsync). Without fsync, writes are 100x faster but unsafe."

**Q4: Sendfile vs read()+send() — when do you use each?**

A: "sendfile for large static files (zero-copy). read()+send() for small data or when you need to process/transform in app space. Real benchmark: sendfile ~200MB/s, read+send ~100MB/s. But modern kernels have optimized both."

**Q5: What's the downside of mmap?**

A: "Page faults. Each uncached page = page fault = ~1ms. If working set > RAM, you get constant page faults = slow. Also: less control over I/O patterns (kernel decides when to fetch). Use only when working set fits in memory or access pattern is sequential."

---

## Real Example: Slow Database Sync

```
Setup: Database committing 100 inserts/sec with durability

Scenario 1 (No fsync optimization):
  Each COMMIT:
    write(txn_wal, 4KB)  → page cache (100ns)
    fsync()              → wait for disk (10ms)
  100 commits/sec × 10ms = 1 second of fsync overhead
  Result: Can't achieve 100 commits/sec if each blocks for 10ms

Scenario 2 (Group commit, 10 fsync/sec):
  Batch 10 commits:
    write(txn_1_wal)     → page cache
    write(txn_2_wal)     → page cache
    ...
    write(txn_10_wal)    → page cache
    fsync()              → wait for disk (10ms)
  100 commits/sec = 10 batches × 10ms = 100ms overhead
  Result: Can achieve 100 commits/sec with group commit!

Failure case:
  fsync hangs (disk stalled)
  All 10 commits blocked
  No progress until fsync completes
  Solution: Add timeout, fall back to non-durable mode (risky) or retry
```

---

## Key Takeaways

1. **epoll scales to 10K+ connections** (one thread, low memory)
2. **io_uring reduces syscall overhead** (batch I/O operations)
3. **Page cache is powerful** (100x speedup for cached reads)
4. **fsync is expensive** (1-100ms per call, major bottleneck)
5. **Group commit amortizes fsync** (10x improvement)
6. **Zero-copy (sendfile, mmap) reduces latency** (avoid app buffer copies)
7. **DMA removes CPU from I/O** (CPU free to do other work)

---

## Checklist

- [ ] Understand epoll event model vs blocking per-thread
- [ ] Know io_uring reduces syscalls (SQ + CQ)
- [ ] Understand page cache hit/miss cost difference (100ns vs 1ms)
- [ ] Know fsync cost and group-commit optimization
- [ ] Can reason about when mmap is appropriate
- [ ] Understand sendfile zero-copy benefit
- [ ] Know DMA removes CPU from blocking I/O

## Common Wrong Answers

- "Page cache is free" ← No, page faults and fsync are expensive
- "fsync is unavoidable" ← Wrong, use group commit or replication
- "io_uring always faster than epoll" ← Depends on workload (benchmark required)
- "mmap is always better than read()" ← No, mmap = page faults if working set > RAM
- "DMA is only for kernels to use" ← Kernels use it, app code doesn't control it
