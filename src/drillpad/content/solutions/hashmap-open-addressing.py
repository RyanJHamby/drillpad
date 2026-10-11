# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
_EMPTY, _TOMBSTONE = object(), object()   # sentinels distinct from any real key

class HashMapOpenAddressing:
    def __init__(self, capacity=8, load_factor=0.5):
        self._cap = capacity
        self._keys = [_EMPTY] * capacity
        self._vals = [None] * capacity
        self._size = 0          # live entries only
        self._used = 0          # live + tombstones, drives resize
        self._load_factor = load_factor

    def _probe(self, key):
        # linear probing; swap to (i*i + i)//2 step for quadratic
        idx = hash(key) % self._cap
        step = 1
        first_tombstone = None
        while self._keys[idx] is not _EMPTY:
            if self._keys[idx] == key:
                return idx, False           # found live slot
            if self._keys[idx] is _TOMBSTONE and first_tombstone is None:
                first_tombstone = idx
            idx = (idx + step) % self._cap
        return (first_tombstone if first_tombstone is not None else idx), True

    def put(self, key, val):
        if self._used / self._cap > self._load_factor:
            self._resize(self._cap * 2)
        idx, is_new = self._find_slot_for_put(key)
        if self._keys[idx] is _EMPTY:
            self._used += 1
        if is_new:
            self._size += 1
        self._keys[idx] = key
        self._vals[idx] = val

    def _find_slot_for_put(self, key):
        idx = hash(key) % self._cap
        step = 1
        first_tombstone = None
        while self._keys[idx] is not _EMPTY:
            if self._keys[idx] == key:
                return idx, False
            if self._keys[idx] is _TOMBSTONE and first_tombstone is None:
                first_tombstone = idx
            idx = (idx + step) % self._cap
        return (first_tombstone if first_tombstone is not None else idx), True

    def get(self, key):
        idx = hash(key) % self._cap
        step = 1
        while self._keys[idx] is not _EMPTY:
            if self._keys[idx] == key:
                return self._vals[idx]
            idx = (idx + step) % self._cap
        raise KeyError(key)

    def delete(self, key):
        idx = hash(key) % self._cap
        step = 1
        while self._keys[idx] is not _EMPTY:
            if self._keys[idx] == key:
                self._keys[idx] = _TOMBSTONE   # leave tombstone, don't clear to _EMPTY
                self._vals[idx] = None
                self._size -= 1
                return
            idx = (idx + step) % self._cap
        raise KeyError(key)

    def _resize(self, new_cap):
        old_keys, old_vals = self._keys, self._vals
        self._cap, self._keys, self._vals = new_cap, [_EMPTY] * new_cap, [None] * new_cap
        self._size = self._used = 0
        for k, v in zip(old_keys, old_vals):
            if k is not _EMPTY and k is not _TOMBSTONE:
                self.put(k, v)

    def __len__(self):
        return self._size
