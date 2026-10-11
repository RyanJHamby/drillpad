# ruff: noqa
import threading
import time


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold, recovery_timeout, success_threshold=1, clock=time.monotonic):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.clock = clock
        self._lock = threading.Lock()
        self._state = "closed"
        self._failures = 0
        self._successes = 0
        self._opened_at = 0.0
        self._probe_in_flight = False

    def _refresh(self):
        if self._state == "open" and self.clock() - self._opened_at >= self.recovery_timeout:
            self._state = "half_open"
            self._successes = 0
            self._probe_in_flight = False

    @property
    def state(self):
        with self._lock:
            self._refresh()
            return self._state

    def call(self, fn, *args, **kwargs):
        with self._lock:
            self._refresh()
            if self._state == "open":
                raise CircuitOpenError("circuit open")
            probe = self._state == "half_open"
            if probe:
                if self._probe_in_flight:
                    raise CircuitOpenError("probe in flight")
                self._probe_in_flight = True
        try:
            result = fn(*args, **kwargs)
        except BaseException:
            with self._lock:
                if probe:
                    self._probe_in_flight = False
                    self._state = "open"
                    self._opened_at = self.clock()
                else:
                    self._failures += 1
                    if self._failures >= self.failure_threshold and self._state == "closed":
                        self._state = "open"
                        self._opened_at = self.clock()
            raise
        with self._lock:
            if probe:
                self._probe_in_flight = False
                self._successes += 1
                if self._successes >= self.success_threshold:
                    self._state = "closed"
                    self._failures = 0
            else:
                self._failures = 0
        return result
