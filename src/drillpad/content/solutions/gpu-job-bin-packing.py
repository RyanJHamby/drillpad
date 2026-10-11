# ruff: noqa
import heapq


class GPUScheduler:
    def __init__(self, capacities):
        if any(c < 0 or c > 64 for c in capacities):
            raise ValueError("capacity must be in 0..64")
        self.cap = list(capacities)
        self.free_ = list(capacities)
        self.buckets = {}          # free count -> min-heap of node indices (lazy)
        for i, c in enumerate(capacities):
            self.buckets.setdefault(c, []).append(i)
        for h in self.buckets.values():
            heapq.heapify(h)
        self.jobs = {}             # job -> (node, gpus)

    def free(self, node):
        return self.free_[node]

    def _top(self, c):
        h = self.buckets.get(c)
        while h and self.free_[h[0]] != c:
            heapq.heappop(h)
        return h[0] if h else None

    def _set(self, node, new):
        self.free_[node] = new
        heapq.heappush(self.buckets.setdefault(new, []), node)

    def place(self, job_id, gpus, strategy="best_fit"):
        if job_id in self.jobs or gpus < 1 or strategy not in ("best_fit", "first_fit"):
            raise ValueError("bad request")
        cands = [(c, self._top(c)) for c in sorted(self.buckets) if c >= gpus]
        cands = [(c, n) for c, n in cands if n is not None]
        if not cands:
            return None
        if strategy == "best_fit":
            c, node = cands[0]
        else:
            c, node = min(cands, key=lambda cn: cn[1])
        self._set(node, c - gpus)
        self.jobs[job_id] = (node, gpus)
        return node

    def release(self, job_id):
        node, gpus = self.jobs.pop(job_id)
        self._set(node, self.free_[node] + gpus)

    def utilization(self):
        total = sum(self.cap)
        return 0.0 if total == 0 else (total - sum(self.free_)) / total


def pack_decreasing(capacities, jobs, strategy="best_fit"):
    s = GPUScheduler(capacities)
    placed, unplaced = {}, []
    for job_id, gpus in sorted(jobs, key=lambda j: -j[1]):
        node = s.place(job_id, gpus, strategy)
        if node is None:
            unplaced.append(job_id)
        else:
            placed[job_id] = node
    return placed, unplaced
