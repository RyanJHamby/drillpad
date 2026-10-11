# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class HashSet:
    """Built directly on chaining buckets, storing bare keys (no value slot)."""

    def __init__(self, capacity=8, load_factor=0.75):
        self._buckets = [[] for _ in range(capacity)]
        self._cap = capacity
        self._size = 0
        self._load_factor = load_factor

    def _hash(self, key):
        return hash(key) % self._cap

    def _resize(self):
        old_buckets = self._buckets
        self._cap *= 2
        self._buckets = [[] for _ in range(self._cap)]
        self._size = 0
        for bucket in old_buckets:
            for k in bucket:
                self.add(k)

    def add(self, key):
        idx = self._hash(key)
        bucket = self._buckets[idx]
        if key in bucket:            # duplicate add is a no-op, like a real set
            return
        bucket.append(key)
        self._size += 1
        if self._size / self._cap > self._load_factor:
            self._resize()

    def contains(self, key):
        idx = self._hash(key)
        return key in self._buckets[idx]

    def remove(self, key):
        idx = self._hash(key)
        bucket = self._buckets[idx]
        if key not in bucket:
            raise KeyError(key)
        bucket.remove(key)
        self._size -= 1

    def __len__(self):
        return self._size

    def __contains__(self, key):
        return self.contains(key)
