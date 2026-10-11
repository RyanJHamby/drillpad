# ruff: noqa
import heapq
from collections import Counter

LEVELS = {"DEBUG", "INFO", "WARN", "ERROR"}


class LogAnalyzer:
    def __init__(self):
        self.records = []        # (ts, level, service, message) in arrival order
        self._malformed = 0

    @property
    def malformed(self):
        return self._malformed

    @property
    def total(self):
        return len(self.records)

    def ingest(self, line):
        parts = line.strip().split(" ", 3)
        if len(parts) < 4 or not parts[0].isdigit() or parts[1] not in LEVELS or not parts[2] or not parts[3].strip():
            self._malformed += 1
            return False
        self.records.append((int(parts[0]), parts[1], parts[2], parts[3]))
        return True

    def top_n(self, n, by="service", level=None, since=None):
        if by not in ("service", "message"):
            raise ValueError(by)
        if n <= 0:
            return []
        idx = 2 if by == "service" else 3
        counts = Counter(
            r[idx] for r in self.records
            if (level is None or r[1] == level) and (since is None or r[0] >= since)
        )
        return heapq.nsmallest(n, counts.items(), key=lambda kv: (-kv[1], kv[0]))
