# ruff: noqa
import math
from collections import deque


class Autoscaler:
    def __init__(self, min_replicas, max_replicas, target_per_replica, down_window):
        if not (1 <= min_replicas <= max_replicas) or target_per_replica <= 0 or down_window < 0:
            raise ValueError("bad config")
        self.lo, self.hi = min_replicas, max_replicas
        self.target = target_per_replica
        self.window = down_window
        self.replicas = min_replicas
        self.dq = deque()            # (ts, desired) with strictly decreasing desired: monotonic max
        self.last_ts = None

    def observe(self, now, load):
        if load < 0 or (self.last_ts is not None and now < self.last_ts):
            raise ValueError("bad observation")
        self.last_ts = now
        desired = min(self.hi, max(self.lo, math.ceil(load / self.target)))
        while self.dq and self.dq[-1][1] <= desired:
            self.dq.pop()
        self.dq.append((now, desired))
        while len(self.dq) > 1 and self.dq[0][0] <= now - self.window:
            self.dq.popleft()
        if desired > self.replicas:
            self.replicas = desired
        else:
            stable = self.dq[0][1]
            if stable < self.replicas:
                self.replicas = stable
        return self.replicas
