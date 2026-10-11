# ruff: noqa
import bisect
import hashlib


def _h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)


class HashRing:
    def __init__(self, vnodes=100):
        if vnodes < 1:
            raise ValueError("vnodes")
        self.vnodes = vnodes
        self.ring = []          # sorted (hash, node)
        self.nodes = set()

    def add_node(self, name):
        if name in self.nodes:
            return
        self.nodes.add(name)
        for i in range(self.vnodes):
            bisect.insort(self.ring, (_h(f"{name}#{i}"), name))

    def remove_node(self, name):
        if name not in self.nodes:
            raise KeyError(name)
        self.nodes.discard(name)
        self.ring = [e for e in self.ring if e[1] != name]

    def _start(self, key):
        i = bisect.bisect_left(self.ring, (_h(key), ""))
        return i % len(self.ring)

    def route(self, key):
        if not self.ring:
            raise LookupError("empty ring")
        return self.ring[self._start(key)][1]

    def route_n(self, key, n):
        if not self.ring:
            raise LookupError("empty ring")
        n = min(n, len(self.nodes))
        if n <= 0:
            return []
        out, seen = [], set()
        i = self._start(key)
        for k in range(len(self.ring)):
            node = self.ring[(i + k) % len(self.ring)][1]
            if node not in seen:
                seen.add(node)
                out.append(node)
                if len(out) == n:
                    break
        return out
