# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading
import time


class TokenBucket:
    """Lazy refill: no background thread. Refill amount computed
    on-demand from elapsed wall-clock time at each check."""

    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity          # max tokens (burst allowance)
        self.refill_rate = refill_rate    # tokens added per second
        self.tokens = capacity            # start full
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()      # single-process concurrency

    def allow(self, cost: float = 1.0) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            # lazy refill: top up based on time passed, capped at capacity
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


class TokenBucketBackgroundThread:
    """Alternative: a ticker thread adds tokens on a fixed cadence.
    Shown for contrast — generally worse: extra thread per bucket (or a
    global scheduler managing all buckets), ticks fire even when idle,
    and you still need a lock since the ticker and callers both mutate
    `tokens`."""

    def __init__(self, capacity: int, refill_rate: int):
        self.capacity = capacity
        self.tokens = capacity
        self.lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._tick, args=(refill_rate,), daemon=True)
        self._thread.start()

    def _tick(self, refill_rate):
        interval = 1.0 / refill_rate
        while not self._stop.is_set():
            time.sleep(interval)
            with self.lock:
                self.tokens = min(self.capacity, self.tokens + 1)

    def allow(self) -> bool:
        with self.lock:
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
