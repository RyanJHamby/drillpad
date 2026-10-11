# ruff: noqa
import heapq


class MetricsAggregator:
    def __init__(self, bucket_seconds, retention_buckets):
        if bucket_seconds <= 0 or retention_buckets < 1:
            raise ValueError("bad config")
        self.b = bucket_seconds
        self.keep = retention_buckets
        self.data = {}         # metric -> {bucket_start: [count, sum, min, max]}
        self.heaps = {}        # metric -> min-heap of bucket starts
        self.newest = {}       # metric -> newest bucket start seen

    def record(self, metric, ts, value):
        start = (ts // self.b) * self.b
        newest = self.newest.get(metric)
        if newest is not None and start <= newest - self.keep * self.b:
            return False                     # too old for the retention window
        buckets = self.data.setdefault(metric, {})
        heap = self.heaps.setdefault(metric, [])
        cell = buckets.get(start)
        if cell is None:
            buckets[start] = [1, value, value, value]
            heapq.heappush(heap, start)
        else:
            cell[0] += 1
            cell[1] += value
            cell[2] = min(cell[2], value)
            cell[3] = max(cell[3], value)
        if newest is None or start > newest:
            self.newest[metric] = start
            limit = start - self.keep * self.b
            while heap and heap[0] <= limit:
                del buckets[heapq.heappop(heap)]
        return True

    def series(self, metric, start, end):
        buckets = self.data.get(metric, {})
        if not buckets or end <= start:
            return []
        first = -((-start) // self.b) * self.b      # first bucket start >= start
        n = (end - first + self.b - 1) // self.b if end > first else 0
        if n <= 0:
            return []
        if n <= len(buckets):
            keys = [first + i * self.b for i in range(n) if first + i * self.b in buckets]
        else:
            keys = sorted(k for k in buckets if first <= k < end)
        return [(k, buckets[k][0], buckets[k][1]) for k in keys]

    def query(self, metric, start, end):
        buckets = self.data.get(metric, {})
        count, total, lo, hi = 0, 0, None, None
        for k, _, _ in self.series(metric, start, end):
            c, s, mn, mx = buckets[k]
            count += c
            total += s
            lo = mn if lo is None else min(lo, mn)
            hi = mx if hi is None else max(hi, mx)
        return {"count": count, "sum": total, "min": lo, "max": hi}
