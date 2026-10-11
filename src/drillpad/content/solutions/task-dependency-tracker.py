# ruff: noqa
import heapq
from collections import deque


class TaskTracker:
    def __init__(self):
        self.status = {}        # task -> "pending" | "done" | "failed" | "blocked"
        self.deps = {}          # task -> set of prerequisites
        self.rdeps = {}         # task -> set of dependents

    def add(self, task, deps=()):
        deps = list(deps)
        if task in self.status or any(d not in self.status for d in deps):
            raise ValueError("duplicate task or unknown dependency")
        self.status[task] = "pending"
        self.deps[task], self.rdeps[task] = set(deps), set()
        for d in deps:
            self.rdeps[d].add(task)
        if any(self.status[d] in ("failed", "blocked") for d in deps):
            self.status[task] = "blocked"

    def _reaches(self, start, target):
        stack, seen = [start], set()
        while stack:
            x = stack.pop()
            if x == target:
                return True
            if x not in seen:
                seen.add(x)
                stack.extend(self.deps[x])
        return False

    def add_dep(self, task, dep):
        if task not in self.status or dep not in self.status:
            raise ValueError("unknown task")
        if self.status[task] != "pending":
            raise ValueError("task is not pending")
        if self._reaches(dep, task):             # dep already (transitively) needs task, or dep == task
            raise ValueError("cycle")
        self.deps[task].add(dep)
        self.rdeps[dep].add(task)
        if self.status[dep] in ("failed", "blocked"):
            self._block_downstream(dep, include_self=False)
            self.status[task] = "blocked"

    def state(self, task):
        return self.status[task]

    def _is_ready(self, t):
        return self.status[t] == "pending" and all(self.status[d] == "done" for d in self.deps[t])

    def ready(self):
        return sorted(t for t in self.status if self._is_ready(t))

    def complete(self, task):
        if task not in self.status or not self._is_ready(task):
            raise ValueError("task is not ready")
        self.status[task] = "done"
        return sorted(r for r in self.rdeps[task] if self._is_ready(r))

    def _block_downstream(self, task, include_self):
        q = deque(self.rdeps[task])
        while q:
            r = q.popleft()
            if self.status[r] == "pending":
                self.status[r] = "blocked"
                q.extend(self.rdeps[r])

    def fail(self, task):
        if task not in self.status or self.status[task] not in ("pending",):
            raise ValueError("only a pending task can fail")
        self.status[task] = "failed"
        self._block_downstream(task, include_self=False)

    def order(self):
        indeg = {t: len(d) for t, d in self.deps.items()}
        heap = [t for t, k in indeg.items() if k == 0]
        heapq.heapify(heap)
        out = []
        while heap:
            t = heapq.heappop(heap)
            out.append(t)
            for r in self.rdeps[t]:
                indeg[r] -= 1
                if indeg[r] == 0:
                    heapq.heappush(heap, r)
        return out
