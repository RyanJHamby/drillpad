# ruff: noqa
from bisect import bisect_left, bisect_right
class TimeMap:
    """Versioned values per key. Timestamps may arrive out of order; each version may carry a ttl."""
    def __init__(self):
        self.ts = {}    # key -> sorted timestamps
        self.vals = {}  # key -> values, parallel to ts
        self.exp = {}   # key -> expiry time (or None), parallel to ts

    def set(self, key, value, timestamp):
        self.set_with_ttl(key, value, timestamp, None)

    def set_with_ttl(self, key, value, timestamp, ttl=None):
        ts = self.ts.setdefault(key, [])
        vs = self.vals.setdefault(key, [])
        ex = self.exp.setdefault(key, [])
        deadline = None if ttl is None else timestamp + ttl
        i = bisect_left(ts, timestamp)
        if i < len(ts) and ts[i] == timestamp:
            vs[i], ex[i] = value, deadline  # same timestamp: the last write wins
        elif i == len(ts):  # in-order arrival: O(1) append
            ts.append(timestamp); vs.append(value); ex.append(deadline)
        else:  # out of order: O(n) insert here; a balanced tree makes it O(log n)
            ts.insert(i, timestamp); vs.insert(i, value); ex.insert(i, deadline)

    def get(self, key, timestamp):
        ts = self.ts.get(key)
        if not ts:
            return ""
        i = bisect_right(ts, timestamp)
        if not i:
            return ""
        deadline = self.exp[key][i - 1]
        if deadline is not None and timestamp >= deadline:
            return ""  # the governing version has expired; do not fall back to an older one
        return self.vals[key][i - 1]
