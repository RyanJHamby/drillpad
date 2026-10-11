# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading
import time
from collections import deque
from enum import IntEnum


class Priority(IntEnum):
    LOW = 0       # e.g., background jobs, analytics pings
    NORMAL = 1    # standard user requests
    HIGH = 2      # revenue-critical / SLA-bound requests

class AdmissionController:
    """Sheds load based on a saturation signal, protecting high-priority
    traffic by rejecting low-priority traffic first as the system nears
    capacity."""

    def __init__(self, max_in_flight: int, latency_window: int = 50):
        self.max_in_flight = max_in_flight
        self.in_flight = 0
        self.latencies = deque(maxlen=latency_window)  # rolling p99 estimate
        self.lock = threading.Lock()

        # thresholds are fractions of max_in_flight at which each priority
        # tier starts getting shed -- lower priority sheds earliest
        self.shed_thresholds = {
            Priority.LOW: 0.6,     # shed LOW once 60% saturated
            Priority.NORMAL: 0.85, # shed NORMAL once 85% saturated
            Priority.HIGH: 1.0,    # HIGH only shed at full saturation
        }

    def _saturation(self) -> float:
        # queue-depth-based signal; latency-percentile signal is an
        # alternative (see below) -- either works as the saturation proxy
        return self.in_flight / self.max_in_flight

    def _latency_p99(self) -> float:
        if not self.latencies:
            return 0.0
        ordered = sorted(self.latencies)
        idx = int(len(ordered) * 0.99)
        return ordered[min(idx, len(ordered) - 1)]

    def admit(self, priority: Priority) -> bool:
        with self.lock:
            saturation = self._saturation()
            if saturation >= self.shed_thresholds[priority]:
                return False  # shed: this tier's threshold has been crossed
            self.in_flight += 1
            return True

    def release(self, latency_sec: float):
        with self.lock:
            self.in_flight = max(0, self.in_flight - 1)
            self.latencies.append(latency_sec)

    def is_latency_saturated(self, latency_slo_sec: float) -> bool:
        # alternative/complementary signal: reject NEW low-priority work
        # if recent p99 latency already exceeds SLO, even if queue depth
        # looks fine -- catches saturation that queue depth alone misses
        # (e.g., downstream is slow but not yet backed up)
        return self._latency_p99() > latency_slo_sec


# usage sketch
controller = AdmissionController(max_in_flight=100)

def handle_request(priority: Priority, do_work):
    if not controller.admit(priority):
        raise Exception("503: shedding load, try again later")  # or degrade gracefully
    start = time.monotonic()
    try:
        return do_work()
    finally:
        controller.release(time.monotonic() - start)
