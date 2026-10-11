# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import threading
import time


class TTLCache:
    def __init__(self, sweep_interval=1.0):
        self.data = {}       # key -> (val, expiry_ts)
        self.lock = threading.Lock()
        self.sweep_interval = sweep_interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sweep_loop, daemon=True)
        self._thread.start()

    def put(self, key, val, ttl_seconds):
        expiry = time.monotonic() + ttl_seconds  # monotonic clock avoids wall-clock skew/jumps
        with self.lock:
            self.data[key] = (val, expiry)

    def get(self, key):
        with self.lock:
            entry = self.data.get(key)
            if entry is None:
                return None
            val, expiry = entry
            if time.monotonic() >= expiry:
                del self.data[key]   # lazy expiry: catch it here even if sweeper hasn't yet
                return None
            return val

    def _sweep_loop(self):
        while not self._stop.wait(self.sweep_interval):
            now = time.monotonic()
            with self.lock:
                expired = [k for k, (_, exp) in self.data.items() if now >= exp]
                for k in expired:
                    del self.data[k]

    def stop(self):
        self._stop.set()
        self._thread.join()
