# ruff: noqa
from collections import deque


class CircuitBreaker:
    def __init__(self, window=10, failure_ratio=0.5, min_calls=5, cooldown=30.0, half_open_probes=2):
        if window < 1 or not (0 < failure_ratio <= 1) or min_calls < 1 or cooldown < 0 or half_open_probes < 1:
            raise ValueError("bad config")
        self.window, self.ratio, self.min_calls = window, failure_ratio, min_calls
        self.cooldown, self.probes = cooldown, half_open_probes
        self._state = "closed"
        self.results = deque()
        self.failures = 0
        self.opened_at = 0.0
        self.started = 0
        self.succeeded = 0

    def state(self, now):
        if self._state == "open" and now - self.opened_at >= self.cooldown:
            self._state = "half_open"
            self.started = 0
            self.succeeded = 0
        return self._state

    def allow(self, now):
        s = self.state(now)
        if s == "closed":
            return True
        if s == "open":
            return False
        if self.started < self.probes:
            self.started += 1
            return True
        return False

    def _open(self, now):
        self._state = "open"
        self.opened_at = now
        self.results.clear()
        self.failures = 0

    def record(self, success, now):
        s = self.state(now)
        if s == "open":
            return
        if s == "half_open":
            if not success:
                self._open(now)
            else:
                self.succeeded += 1
                if self.succeeded >= self.probes:
                    self._state = "closed"
                    self.results.clear()
                    self.failures = 0
            return
        self.results.append(success)
        if not success:
            self.failures += 1
        if len(self.results) > self.window:
            if not self.results.popleft():
                self.failures -= 1
        n = len(self.results)
        if n >= self.min_calls and self.failures / n >= self.ratio:
            self._open(now)


class HealthChecker:
    def __init__(self, backends, unhealthy_after=3, healthy_after=2):
        if unhealthy_after < 1 or healthy_after < 1:
            raise ValueError("thresholds")
        self.order = list(backends)
        self.ok = {b: True for b in self.order}
        self.streak = {b: 0 for b in self.order}
        self.un, self.hl = unhealthy_after, healthy_after

    def report(self, backend, ok):
        if backend not in self.ok:
            raise KeyError(backend)
        healthy = self.ok[backend]
        if ok == healthy:
            self.streak[backend] = 0
            return
        self.streak[backend] += 1
        if self.streak[backend] >= (self.hl if ok else self.un):
            self.ok[backend] = ok
            self.streak[backend] = 0

    def healthy(self):
        return [b for b in self.order if self.ok[b]]
