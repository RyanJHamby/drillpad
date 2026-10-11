# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import queue
import threading


class ThreadPool:
    def __init__(self, num_workers):
        self._tasks = queue.Queue()   # thread-safe, blocking get()
        self._workers = []
        self._shutdown = False
        for _ in range(num_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)

    def submit(self, fn, *args, **kwargs):
        self._tasks.put((fn, args, kwargs))

    def _worker_loop(self):
        while True:
            item = self._tasks.get()   # blocks — no busy-wait
            if item is None:           # poison pill = shutdown signal
                self._tasks.task_done()
                break
            fn, args, kwargs = item
            try:
                fn(*args, **kwargs)
            except Exception:
                pass  # log in real code; never let a worker thread die silently
            finally:
                self._tasks.task_done()

    def shutdown(self, wait=True):
        self._tasks.join()             # drain queued work first
        for _ in self._workers:
            self._tasks.put(None)      # one poison pill per worker
        if wait:
            for t in self._workers:
                t.join()
