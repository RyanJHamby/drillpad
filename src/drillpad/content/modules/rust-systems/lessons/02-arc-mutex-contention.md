# Arc<Mutex<T>>: Contention Patterns, parking_lot vs std::sync

## Mutex Contention

```
Arc<Mutex<Data>> shared across threads
Thread 1 acquires lock, does work (1 μs)
Thread 2 waits for lock, spins (cost: 1 μs + context switch)
Thread 3 waits, spins
...
Thread 100 waits

Lock holder releases, one waiting thread wakes (OS picks which one, usually random)
Thundering herd: all waiting threads wake, only one acquires, others re-sleep
Overhead: O(N) context switches for N threads

Critical section > 100 μs: don't use Mutex, use RwLock or redesign
```

---

## parking_lot vs std::sync

std::sync::Mutex: fair scheduling, high overhead (~100 ns)
parking_lot::Mutex: unfair (gives to waker, not other waiters), low overhead (~50 ns)

For high contention: parking_lot wins (less overhead, starvation risk acceptable).

