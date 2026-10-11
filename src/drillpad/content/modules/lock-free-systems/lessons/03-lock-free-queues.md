# Lock-Free Data Structures: Queues, Stacks, ABA Problem

## Lock-Free Queue (MPMC: Multi-Producer, Multi-Consumer)

```
Goal: push/pop without locks, multiple threads

Simple idea (FAILS):
  struct Queue {
    Node* head;
    Node* tail;
  }
  
  push(value):
    Node* new_node = new Node(value)
    CAS(tail, old_tail, new_node)  // append to tail
  
  pop():
    CAS(head, old_head, old_head->next)  // remove from head
  
Problem: What if head and tail race?
  Thread A: push, CAS(tail) succeeds
  Thread B: pop, CAS(head) succeeds
  Thread C: push, tail->next is stale
  CRASH!
```

---

## The ABA Problem

```
Classic bug in lock-free code:

Shared value: pointer to node (value = A)

Thread 1:
  1. Read pointer → A
  2. Check if still A
  3. Decide to update
  4. ... slow ...
  5. CAS(pointer, A, B)  → should succeed
  
Thread 2 (while Thread 1 is slow):
  1. CAS(pointer, A, C)  → success, pointer now C
  2. Do stuff
  3. Free node A
  4. allocate new node, reuse same memory address as old A
  5. CAS(pointer, C, A)  → success, pointer back to A (new node!)
  
Thread 1 (finally):
  1. CAS(pointer, A, B)  → succeeds!
     (doesn't know A is different node now)
  2. Reads A->next
     (but A is now different node, memory corrupted!)
  
The value "A" appeared twice, causing confusion → ABA problem
```

---

## Fixing ABA: Versioning

```
Instead of:
  CAS(pointer, A, B)
  
Use:
  CAS(versioned_pointer, (A, version=1), (B, version=2))
  
Versioned pointer = (pointer, version)
  - 64-bit: 48-bit pointer, 16-bit version
  - Each CAS increments version
  
Thread 2's reuse of node A:
  Old node A had version=1
  New node A (reused memory) has version=0
  When Thread 1 tries CAS with version=1, it fails!
  (pointer is now different object with version=0)
```

---

## Real Lock-Free Queue Implementation

```cpp
template<typename T>
class LockFreeQueue {
    struct Node {
        T value;
        std::atomic<Node*> next;
        Node(const T& v) : value(v), next(nullptr) {}
    };
    
    struct VersionedPtr {
        Node* ptr;
        uint64_t version;
    };
    
    std::atomic<VersionedPtr> head;
    std::atomic<VersionedPtr> tail;
    
public:
    void push(const T& value) {
        Node* new_node = new Node(value);
        while (true) {
            VersionedPtr old_tail = tail.load(std::memory_order_acquire);
            
            // Link new node to tail
            Node* next = old_tail.ptr->next.load();
            if (next == nullptr) {
                VersionedPtr new_next = {new_node, old_tail.version + 1};
                if (old_tail.ptr->next.compare_exchange_strong(
                    next, new_node, 
                    std::memory_order_release)) {
                    // Try to swing tail
                    VersionedPtr new_tail = {new_node, old_tail.version + 1};
                    tail.compare_exchange_strong(old_tail, new_tail, 
                        std::memory_order_release);
                    return;
                }
            }
        }
    }
    
    bool pop(T& result) {
        while (true) {
            VersionedPtr old_head = head.load(std::memory_order_acquire);
            VersionedPtr old_tail = tail.load(std::memory_order_acquire);
            Node* next = old_head.ptr->next.load();
            
            if (next == nullptr) {
                return false;  // queue empty
            }
            
            result = next->value;
            VersionedPtr new_head = {next, old_head.version + 1};
            
            if (head.compare_exchange_strong(old_head, new_head,
                std::memory_order_release)) {
                delete old_head.ptr;
                return true;
            }
        }
    }
};
```

---

## Complexity vs Simplicity

```
Mutex-protected queue:
  Code: 10 lines, easy to understand
  Correctness: obvious (mutex enforces serialization)
  Performance: slow under contention
  
Lock-free queue:
  Code: 50 lines, hard to understand
  Correctness: subtle (ABA, versioning, memory ordering)
  Performance: fast under contention
  
When to use lock-free?
  - Ultra-low latency required (trading, real-time)
  - High contention expected (many threads)
  - Correctness can be verified (tests, proof)
  
When NOT to use:
  - Simplicity matters (internal queues)
  - Moderate load (mutex is fine)
  - Team not trained in lock-free (bugs!)
```

---

## Testing Lock-Free Code

```
Problem: race conditions are rare, hard to reproduce

Solution 1: Stress test
  - Run with 100 threads
  - 1M operations each
  - Verify: no crashes, correct counts
  - Run for hours (expose race conditions)
  
Solution 2: ThreadSanitizer (TSAN)
  - Detects data races at runtime
  - Slower (10x), but finds bugs
  - Use in development, not production
  
Solution 3: Model checking
  - Formal verification of correctness
  - For critical code (trading, payment)
  
Example stress test:
  vector<thread> threads(100);
  for (int i = 0; i < 100; i++) {
    threads[i] = thread([&]() {
      for (int j = 0; j < 1000000; j++) {
        queue.push(j);
        int val;
        queue.pop(val);
      }
    });
  }
  for (auto& t : threads) t.join();
  assert(queue.empty());
```

---

## Q&A

**Recall 1:** What's the ABA problem?

*Must-say:*
- Thread reads pointer A
- Another thread deletes A, reuses memory
- New object is allocated at same memory (now "A" again)
- Original thread CAS succeeds but with wrong object

**Probe 1:** Why does versioning fix ABA?

*Expected:*
- Versioned pointer includes both pointer and version number
- When memory is reused, version is 0 (new allocation)
- CAS fails if version doesn't match (detects reuse)

**Numeric 1:** Versioned pointer: 48-bit address, 16-bit version. Max versions before overflow?

*Working:*
- 16-bit version = 65536 unique versions
- At 1M updates/sec: overflow in 65 seconds
- Need periodic cleanup or larger version field

---

## Questions for the Interviewer

- Have you used lock-free queues? (what was the tradeoff?)
- How do you debug lock-free data structure bugs?
- Have you encountered ABA problems? (how did you find it?)
- When do you prefer simplicity over performance?

