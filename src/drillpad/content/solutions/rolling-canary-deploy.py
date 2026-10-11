# ruff: noqa
import hashlib


class CanaryRollout:
    def __init__(self, stages, min_requests, tolerance):
        if not stages or any(not (0 < s <= 100) for s in stages) or any(b <= a for a, b in zip(stages, stages[1:])):
            raise ValueError("stages must be strictly increasing percentages in (0, 100]")
        if min_requests < 1 or tolerance < 0:
            raise ValueError("bad config")
        self.stages = list(stages)
        self.min_requests = min_requests
        self.tolerance = tolerance
        self.i = 0
        self._state = "running"

    def weight(self):
        return 0 if self._state == "rolled_back" else self.stages[self.i]

    def state(self):
        return self._state

    def report(self, canary_reqs, canary_errs, base_reqs, base_errs):
        if self._state != "running":
            raise RuntimeError("rollout is finished")
        if canary_reqs < 0 or base_reqs < 0 or canary_errs > canary_reqs or base_errs > base_reqs or min(canary_errs, base_errs) < 0:
            raise ValueError("bad counts")
        if canary_reqs < self.min_requests:
            return "hold"
        c = canary_errs / canary_reqs
        b = base_errs / base_reqs if base_reqs else 0.0
        if c > b + self.tolerance:
            self._state = "rolled_back"
            return "rollback"
        if self.i == len(self.stages) - 1:
            self._state = "complete"
            return "complete"
        self.i += 1
        return "promote"

    def route(self, key):
        bucket = int(hashlib.md5(key.encode()).hexdigest()[:8], 16) % 100
        return "canary" if bucket < self.weight() else "stable"
