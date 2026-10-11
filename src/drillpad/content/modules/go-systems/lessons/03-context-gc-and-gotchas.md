# Context Cancellation, GC Tuning, Allocation, and Go Gotchas

## Context Cancellation

```go
ctx, cancel := context.WithCancel(context.Background())

go func() {
    select {
    case <-ctx.Done():
        log.Println("Cancelled")
        return
    case <-time.After(10 * time.Second):
        log.Println("Timeout")
    }
}()

// Cancel from parent
cancel()
```

**Use context for:**

```
- Timeouts: WithTimeout(ctx, 5*time.Second)
- Deadlines: WithDeadline(ctx, time.Now().Add(1min))
- Cancellation: WithCancel(ctx) → cancel()
- Request-scoped values: WithValue(ctx, key, value)
```

---

## GC Tuning

**Go GC default:**

```
Trigger: When heap doubles
Cost: ~25% CPU for GC pauses

Example:
  Heap: 100MB
  GC triggers at: 200MB
  Pause time: ~50-200ms (depends on heap size)
```

**Tuning GOGC:**

```bash
GOGC=50    # Trigger at 150% of previous heap (smaller pauses, more frequent)
GOGC=200   # Trigger at 300% of previous heap (fewer GC, longer pauses)
GOGC=off   # Never collect (only for debugging)
```

**Reducing allocations:**

```go
// BAD: Allocates per iteration
func process() {
    for i := 0; i < 1M; i++ {
        buf := make([]byte, 1024)  // Allocates 1M times
        use(buf)
    }
}

// GOOD: Reuse buffer
func process() {
    buf := make([]byte, 1024)
    for i := 0; i < 1M; i++ {
        use(buf)  // Allocate once
    }
}

// BETTER: Use sync.Pool
var pool = sync.Pool{
    New: func() interface{} {
        return make([]byte, 1024)
    },
}

func process() {
    for i := 0; i < 1M; i++ {
        buf := pool.Get().([]byte)
        use(buf)
        pool.Put(buf)
    }
}
```

---

## Common Go Gotchas

**Gotcha 1: Loop Variable Capture**

```go
// WRONG
for i := 0; i < 3; i++ {
    go func() {
        fmt.Println(i)  // All print 3 (i modified by loop)
    }()
}

// RIGHT
for i := 0; i < 3; i++ {
    i := i  // Shadow outer i
    go func() {
        fmt.Println(i)  // Prints 0, 1, 2
    }()
}

// OR
for i := 0; i < 3; i++ {
    go func(j int) {
        fmt.Println(j)  // Parameter captures value
    }(i)
}
```

**Gotcha 2: Nil Interface Check**

```go
var err error = nil

// WRONG
if err != nil {  // True! (interface is not nil, but value is)
    ...
}

// Why?
var err error = (*CustomError)(nil)  // Nil pointer, non-nil interface
if err != nil {  // True!
    ...
}

// RIGHT
if err != nil {  // Check before type assertion
    ...
}
```

**Gotcha 3: Goroutine Leak**

```go
// LEAKS: Goroutine waits forever
go func() {
    <-make(chan struct{})  // Never closed, blocks forever
}()

// FIX: Use context
go func(ctx context.Context) {
    select {
    case <-ctx.Done():
        return
    case <-ch:
        ...
    }
}(ctx)
```

**Gotcha 4: Mutex Unlock Panic**

```go
// WRONG
m.Lock()
panic("error")
m.Unlock()  // Never executes!

// RIGHT
m.Lock()
defer m.Unlock()
panic("error")  // m unlocks anyway
```

---

## Memory Profiling

```bash
# Profile heap allocation
go test -memprofile=mem.prof

# Analyze
go tool pprof mem.prof

# See top allocators
(pprof) top -cum
```

---

## Interview Pattern: GC Impact

```
Q: "Your service's p99 latency doubled.
   Profiling shows: GC pauses went from 10ms to 100ms.
   Why? How to fix?"

Strong answer:
  "GC pause increased 10x → Heap grew 10x likely.
  
  Diagnosis:
    1. Check heap size: runtime.ReadMemStats()
    2. If heap >> expected: Memory leak
    3. If heap = expected: Increase GOGC (accept longer pauses)
  
  Solutions:
    a) Reduce allocations (reuse buffers, sync.Pool)
    b) Tune GOGC (trade pause length for frequency)
    c) Upgrade to newer Go version (better GC)
    d) Dedicated GC thread (Go 1.19+ likely to improve)
  
  Measurement:
    - Before: GOGC=100, p99=10ms
    - After: GOGC=200, p99=30ms, GC freq halved
    - Trade-off: 3x longer pause, but less frequent"
```

---

## Checklist: Go Production Code

- [ ] Context used for cancellation/timeouts
- [ ] Goroutine leaks prevented
- [ ] Race conditions checked (go test -race)
- [ ] Allocations minimized (profile with pprof)
- [ ] GC tuned for latency requirements
- [ ] Mutex held briefly (no nested locks)
- [ ] Panic handled with recover() where needed
- [ ] defer used for cleanup

## Common Mistakes

1. **"Goroutines are free, spawn unlimited"**
   - Each goroutine ~2KB stack + scheduler overhead
   - 100K goroutines: 200MB + GC pressure

2. **"No need to tune GC"**
   - Default GOGC=100 might not suit your workload
   - Tuning can 2-5x latency improvement

3. **"Loop variables safe in goroutines"**
   - No, must capture by value or shadow

4. **"Just use channels for everything"**
   - Channels for coordination
   - Mutexes for state protection
   - Use appropriate tool
