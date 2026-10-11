# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class HashMapChaining:
    def __init__(self, capacity=8, load_factor=0.75):
        self._buckets = [[] for _ in range(capacity)]
        self._cap = capacity
        self._size = 0
        self._load_factor = load_factor

    def _hash(self, key):
        return hash(key) % self._cap   # Python's hash(); % gives bucket index

    def _resize(self):
        old_buckets = self._buckets
        self._cap *= 2
        self._buckets = [[] for _ in range(self._cap)]
        self._size = 0
        for bucket in old_buckets:          # rehash every entry
            for k, v in bucket:
                self.put(k, v)

    def put(self, key, val):
        idx = self._hash(key)
        bucket = self._buckets[idx]
        for i, (k, _) in enumerate(bucket):
            if k == key:                    # overwrite existing key
                bucket[i] = (key, val)
                return
        bucket.append((key, val))
        self._size += 1
        if self._size / self._cap > self._load_factor:
            self._resize()

    def get(self, key):
        idx = self._hash(key)
        for k, v in self._buckets[idx]:
            if k == key:
                return v
        raise KeyError(key)

    def delete(self, key):
        idx = self._hash(key)
        bucket = self._buckets[idx]
        for i, (k, _) in enumerate(bucket):
            if k == key:
                bucket.pop(i)
                self._size -= 1
                return
        raise KeyError(key)

    def __len__(self):
        return self._size
