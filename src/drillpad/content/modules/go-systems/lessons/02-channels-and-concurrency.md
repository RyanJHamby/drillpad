# Channels vs Mutexes: When to Use Each, Deadlocks, Blocking Semantics

## Channels: Synchronization by Communication

```go
// Channel: Safe communication between goroutines
ch := make(chan int, 0)  // Unbuffered

go func() {
    ch <- 42  // Send 42, blocks until receiver ready
}()

val := <-ch  // Receive, blocks until sender ready
```

**Semantics:**

```
Unbuffered channel (buffer=0):
  Sender blocks until receiver reads
  Receiver blocks until sender writes
  Synchronous exchange
  
Buffered channel (buffer=N):
  Sender blocks only if buffer full
  Receiver blocks only if buffer empty
  Asynchronous (up to N elements)
```

**When to use channels:**

```
Good:
  - Pipeline (multiple stages processing data)
  - Fan-out/fan-in (distribute work)
  - Signaling (goroutine coordination)

Bad:
  - Protecting shared state (use mutex instead)
  - Simple read/write to variable
```

---

## Mutexes: Protecting Shared State

```go
var m sync.Mutex
var counter int

func increment() {
    m.Lock()
    counter++
    m.Unlock()
}
```

**When to use mutexes:**

```
Good:
  - Shared map/slice
  - Atomic field updates
  - Brief critical sections

Bad:
  - Long-running operations (holding lock)
  - Nested locks (deadlock risk)
```

---

## Deadlock Scenarios

**Deadlock 1: Buffered channel, nobody receives**

```go
ch := make(chan int, 1)
ch <- 1  // OK (buffer has space)
ch <- 2  // DEADLOCK! (buffer full, no receiver)
```

**Deadlock 2: Circular wait**

```go
chA := make(chan int)
chB := make(chan int)

go func() {
    <-chA
    chB <- 1  // Waits for chA, never sends chB
}()

go func() {
    <-chB
    chA <- 1  // Waits for chB, never sends chA
}()
// DEADLOCK: Each waits for other
```

**Deadlock 3: Mutex circular dependency**

```go
var m1, m2 sync.Mutex

// Goroutine A
m1.Lock()
time.Sleep(1ms)
m2.Lock()  // Waits for B to release

// Goroutine B
m2.Lock()
time.Sleep(1ms)
m1.Lock()  // Waits for A to release
// DEADLOCK
```

---

## Blocking Semantics & Races

**Race condition example:**

```go
// WRONG: No synchronization
var x int

go func() { x = 1 }()
go func() { print(x) }()
// Race: One goroutine might read x before write

// RIGHT: Use channel
ch := make(chan int)

go func() { ch <- 1 }()  // Sender
x := <-ch               // Receiver (blocks until sender ready)
print(x)
// Synchronized: Receiver waits for sender
```

---

## Interview Pattern: Concurrent System Design

```
Q: "Design a request router that:
   - Receives requests on input channel
   - Distributes to N worker goroutines
   - Collects results
   - Enforces timeout"

Strong answer:
  "Fan-out/fan-in pattern with context:
  
  type Request struct { ... }
  type Response struct { ... }
  
  func Router(in <-chan Request, workers int, timeout time.Duration) {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    defer cancel()
    
    // Fan out: Distribute to workers
    reqs := make([]chan Request, workers)
    for i := range reqs {
      reqs[i] = make(chan Request)
      go worker(ctx, reqs[i])
    }
    
    // Load balance: Send to least-loaded worker
    for req := range in {
      select {
      case reqs[0] <- req:  // Send to worker 0
      case <-ctx.Done():    // Timeout
        log.Error('timeout')
        return
      }
    }
  }
  
  Benefits:
    - Channels for coordination
    - Context for cancellation
    - Select for non-blocking operations
  
  Issues:
    - Worker selection is naive (not load-balanced)
    - Better: Use random or round-robin selection"
```

---

## Checklist: Go Concurrency

- [ ] Goroutine leaks prevented (all exit eventually)
- [ ] Channels have defined ownership (one sender, multiple receivers)
- [ ] Deadlock potential analyzed (circular dependencies)
- [ ] Race conditions checked (go test -race)
- [ ] Context used for cancellation
- [ ] Mutex held briefly (avoid nested locks)
- [ ] Channel size appropriate (buffered vs unbuffered)

## Common Mistakes

1. **"Close channel from receiver side"**
   - Only sender should close
   - Receiver doesn't know if more data coming

2. **"Use only channels, avoid mutexes"**
   - Channels are for coordination
   - Mutexes are for protecting state
   - Use both

3. **"Goroutine cleanup unnecessary"**
   - Leaking goroutines = memory leak
   - Always ensure goroutines exit

4. **"Panic in goroutine is fine"**
   - Panic kills only that goroutine
   - Other goroutines continue
   - Use recover() if panicking is possible
