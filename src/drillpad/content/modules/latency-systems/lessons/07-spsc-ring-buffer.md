# SPSC Ring Buffer for Low-Latency Communication

## Single Producer, Single Consumer (SPSC)

```
Use case: one thread produces, one thread consumes
Example: network RX thread → app processing thread

Traditional queue (mutex-based):
  ├─ Lock overhead: 100-1000ns per operation
  ├─ Cache misses: lock contention
  └─ Latency: ~1-5 µs per enqueue/dequeue

Lock-free ring buffer:
  ├─ No locks (SPSC so no contention)
  ├─ Circular array: fixed memory allocation
  ├─ Atomic operations: minimal
  └─ Latency: ~100ns per operation
```

## Implementation

```cpp
template<typename T, size_t SIZE>
class SPSCRingBuffer {
    T buffer[SIZE];
    std::atomic<size_t> head {0};  // producer
    std::atomic<size_t> tail {0};  // consumer

    bool enqueue(const T& item) {
        size_t next_head = (head + 1) % SIZE;
        if (next_head == tail.load(std::memory_order_acquire)) {
            return false;  // full
        }
        buffer[head] = item;
        head.store(next_head, std::memory_order_release);
        return true;
    }

    bool dequeue(T& item) {
        if (tail == head.load(std::memory_order_acquire)) {
            return false;  // empty
        }
        item = buffer[tail];
        tail.store((tail + 1) % SIZE, std::memory_order_release);
        return true;
    }
};
```

## Memory Ordering

```
Producer:
  write(buffer[head])  ← must happen before
  release(head)        ← consumer sees new head

Consumer:
  acquire(tail)        ← syncs with producer's release
  read(buffer[...])    ← safe, producer's write visible
  
Guarantees:
  ├─ Write-write: producer's writes complete before update
  ├─ Write-read: producer's writes visible to consumer
  └─ Result: no data races
```

## Scale

```
Throughput:
  ├─ Capacity: SIZE elements
  ├─ Latency: 100ns per element
  ├─ Rate: 10M elements/sec (single threaded)

Memory:
  ├─ SIZE * sizeof(T)
  ├─ Example: 1M slots of 256 bytes = 256 MB
  └─ Cache-friendly: contiguous allocation

Bottleneck:
  ├─ Producer: CPU writing to buffer
  ├─ Consumer: CPU reading from buffer
  ├─ False sharing: if heads on same cache line
  ├─ Solution: pad to separate cache lines (64 bytes)
```

---

## Interview Checklist

- [ ] SPSC: no contention (single producer/consumer)
- [ ] Lock-free: atomic operations only
- [ ] Memory ordering: acquire/release semantics
- [ ] Cache line padding: avoid false sharing
- [ ] Latency: ~100ns per operation

## Common Wrong Answers

- ❌ "Use mutex queue" — 1000x slower
- ❌ "Ignore memory ordering" — data races
- ❌ "No padding for cache" — false sharing kills performance
