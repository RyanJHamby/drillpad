# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading
import time
from collections import deque


class LeakyBucketMeter:
    """Counter version: tracks current 'water level'. Overflow = reject.
    Output rate is capped at leak_rate regardless of burst size."""

    def __init__(self, capacity: float, leak_rate: float):
        self.capacity = capacity      # max backlog before rejecting
        self.leak_rate = leak_rate    # units drained per second
        self.level = 0.0
        self.last_check = time.monotonic()
        self.lock = threading.Lock()

    def allow(self, cost: float = 1.0) -> bool:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last_check
            self.level = max(0.0, self.level - elapsed * self.leak_rate)  # drain
            self.last_check = now
            if self.level + cost <= self.capacity:
                self.level += cost
                return True
            return False  # bucket overflowed -> reject, don't let it burst through


class LeakyBucketQueue:
    """Queue version: requests are held and released at a fixed rate,
    rather than accepted/rejected instantly. Used when you want to shape
    traffic to a downstream system instead of just gatekeeping it."""

    def __init__(self, capacity: int, leak_interval_sec: float):
        self.queue = deque(maxlen=capacity)
        self.leak_interval = leak_interval_sec
        self.lock = threading.Lock()

    def submit(self, request) -> bool:
        with self.lock:
            if len(self.queue) >= self.queue.maxlen:
                return False  # queue full -> reject
            self.queue.append(request)
            return True

    def leak(self):
        """Called on a fixed cadence (or by a consumer loop) to release
        exactly one request downstream at the constant leak rate."""
        with self.lock:
            return self.queue.popleft() if self.queue else None
