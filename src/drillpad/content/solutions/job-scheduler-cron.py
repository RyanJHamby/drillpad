# ruff: noqa
import heapq
import itertools


class Scheduler:
    def __init__(self, clock):
        self.clock = clock
        self.heap = []              # (run_at, seq, job_id)
        self.jobs = {}              # job_id -> [seq, fn, interval or None]
        self.seq = itertools.count()

    def _add(self, job_id, fn, run_at, interval):
        seq = next(self.seq)
        self.jobs[job_id] = [seq, fn, interval]    # replaces any old job (old heap rows go stale)
        heapq.heappush(self.heap, (run_at, seq, job_id))

    def schedule(self, job_id, fn, run_at):
        self._add(job_id, fn, run_at, None)

    def schedule_every(self, job_id, fn, interval, start=None):
        if interval <= 0:
            raise ValueError("interval must be positive")
        if start is None:
            start = self.clock() + interval
        self._add(job_id, fn, start, interval)

    def cancel(self, job_id):
        return self.jobs.pop(job_id, None) is not None

    def _live_top(self):
        while self.heap:
            run_at, seq, job_id = self.heap[0]
            job = self.jobs.get(job_id)
            if job is not None and job[0] == seq:
                return self.heap[0]
            heapq.heappop(self.heap)
        return None

    def run_pending(self):
        ran = []
        now = self.clock()
        while True:
            top = self._live_top()
            if top is None or top[0] > now:
                break
            run_at, seq, job_id = heapq.heappop(self.heap)
            _, fn, interval = self.jobs[job_id]
            if interval is None:
                del self.jobs[job_id]
            else:
                heapq.heappush(self.heap, (run_at + interval, seq, job_id))
            try:
                fn()
            except Exception:
                pass
            ran.append(job_id)
        return ran

    def next_run_time(self):
        top = self._live_top()
        return None if top is None else top[0]
