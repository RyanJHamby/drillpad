# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class SlowStore:
    def write(self, key, val): ...  # e.g. network call, DB write
    def read(self, key): ...

# --- Write-through: write hits cache AND store synchronously, every time.
class WriteThroughCache:
    def __init__(self, store: SlowStore):
        self.store, self.data = store, {}
    def set(self, key, val):
        self.store.write(key, val)   # store first (or cache first — pick one, be consistent)
        self.data[key] = val
    def get(self, key):
        # FIXED vs source: source evaluated store.read(key) eagerly even on a cache hit
        if key in self.data:
            return self.data[key]
        return self.store.read(key)

# --- Write-back (write-behind): write hits cache only; store updated lazily/async.
class WriteBackCache:
    def __init__(self, store: SlowStore):
        self.store, self.data, self.dirty = store, {}, set()
    def set(self, key, val):
        self.data[key] = val
        self.dirty.add(key)          # marked for later flush
    def flush(self):
        for key in list(self.dirty):
            self.store.write(key, self.data[key])
            self.dirty.discard(key)
    def get(self, key):
        # FIXED vs source: source evaluated store.read(key) eagerly even on a cache hit
        if key in self.data:
            return self.data[key]
        return self.store.read(key)

# --- Write-around: write goes straight to store, bypassing cache entirely.
class WriteAroundCache:
    def __init__(self, store: SlowStore):
        self.store, self.data = store, {}
    def set(self, key, val):
        self.store.write(key, val)   # cache not touched — next read will be a miss
        self.data.pop(key, None)     # invalidate stale entry if present
    def get(self, key):
        if key not in self.data:
            self.data[key] = self.store.read(key)
        return self.data[key]
