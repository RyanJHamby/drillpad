# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import math
import threading
import time


class SlidingWindowCounter:
    """Weighted hybrid: current fixed window count + a decayed
    contribution from the previous window, approximating a true
    sliding window without storing per-request timestamps."""

    def __init__(self, limit: int, window_sec: float):
        self.limit = limit
        self.window_sec = window_sec
        self.curr_window_start = self._window_start(time.monotonic())
        self.curr_count = 0
        self.prev_count = 0
        self.lock = threading.Lock()

    def _window_start(self, now: float) -> float:
        return math.floor(now / self.window_sec) * self.window_sec

    def allow(self) -> bool:
        with self.lock:
            now = time.monotonic()
            window_start = self._window_start(now)

            if window_start != self.curr_window_start:
                # rolled into a new fixed window (possibly skipping several
                # if traffic was idle) -> shift counts, zero out stale ones
                windows_elapsed = round((window_start - self.curr_window_start) / self.window_sec)
                self.prev_count = self.curr_count if windows_elapsed == 1 else 0
                self.curr_count = 0
                self.curr_window_start = window_start

            elapsed_in_curr = now - self.curr_window_start
            # weight = fraction of the previous window still "in view"
            overlap_weight = 1 - (elapsed_in_curr / self.window_sec)
            estimated = self.prev_count * overlap_weight + self.curr_count

            if estimated < self.limit:
                self.curr_count += 1
                return True
            return False
