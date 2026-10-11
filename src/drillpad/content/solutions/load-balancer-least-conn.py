# ruff: noqa
import heapq


class LoadBalancer:
    def __init__(self, backends, rng=None):
        self.names = list(backends)
        self.idx = {n: i for i, n in enumerate(self.names)}
        self.act = [0] * len(self.names)
        self.up = [True] * len(self.names)
        self.rng = rng
        self.heap = [(0, i) for i in range(len(self.names))]
        heapq.heapify(self.heap)

    def active(self, name):
        return self.act[self.idx[name]]

    def set_healthy(self, name, healthy):
        i = self.idx[name]
        was = self.up[i]
        self.up[i] = healthy
        if healthy and not was:
            heapq.heappush(self.heap, (self.act[i], i))

    def _healthy_idx(self):
        return [i for i in range(len(self.names)) if self.up[i]]

    def _take(self, i):
        self.act[i] += 1
        heapq.heappush(self.heap, (self.act[i], i))
        return self.names[i]

    def pick_least_conn(self):
        while self.heap:
            a, i = heapq.heappop(self.heap)
            if self.up[i] and self.act[i] == a:
                return self._take(i)
        raise RuntimeError("no healthy backend")

    def pick_p2c(self):
        healthy = self._healthy_idx()
        if not healthy:
            raise RuntimeError("no healthy backend")
        if len(healthy) == 1:
            return self._take(healthy[0])
        a, b = self.rng.sample(healthy, 2)
        return self._take(a if self.act[a] <= self.act[b] else b)

    def release(self, name):
        i = self.idx[name]
        if self.act[i] == 0:
            raise ValueError("no active connection")
        self.act[i] -= 1
        if self.up[i]:
            heapq.heappush(self.heap, (self.act[i], i))
