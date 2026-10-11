# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading


class SlowStore:
    def read(self, key): ...

class CacheAsideCache:
    def __init__(self, store: SlowStore):
        self.store = store
        self.data = {}
        self.lock = threading.Lock()
        self.inflight = {}  # key -> threading.Event, for stampede protection

    def get(self, key):
        with self.lock:
            if key in self.data:
                return self.data[key]
            event = self.inflight.get(key)
            if event is None:
                event = threading.Event()
                self.inflight[key] = event
                is_loader = True
            else:
                is_loader = False

        if not is_loader:
            event.wait()             # another thread is already loading this key
            return self.data.get(key)

        val = self.store.read(key)   # only one thread actually hits the slow store
        with self.lock:
            self.data[key] = val
            del self.inflight[key]
            event.set()
        return val

    def invalidate(self, key):
        with self.lock:
            self.data.pop(key, None)
