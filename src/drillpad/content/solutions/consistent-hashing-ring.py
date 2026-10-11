# ruff: noqa
import bisect
import hashlib


def _md5(s):
    return int.from_bytes(hashlib.md5(s.encode()).digest()[:8], "big")


class HashRing:
    def __init__(self, vnodes=100, hash_fn=None):
        self.vnodes = vnodes
        self.hash_fn = hash_fn or _md5
        self.points = []   # sorted list of ring positions
        self.owner = {}    # position -> node
        self.nodes = set()

    def add_node(self, node):
        if node in self.nodes:
            return
        self.nodes.add(node)
        for i in range(self.vnodes):
            h = self.hash_fn(f"{node}#{i}")
            if h in self.owner:   # collision: keep the existing owner
                continue
            bisect.insort(self.points, h)
            self.owner[h] = node

    def remove_node(self, node):
        if node not in self.nodes:
            return
        self.nodes.discard(node)
        dead = {h for h, n in self.owner.items() if n == node}
        self.points = [h for h in self.points if h not in dead]
        for h in dead:
            del self.owner[h]

    def get_node(self, key):
        if not self.points:
            return None
        i = bisect.bisect_left(self.points, self.hash_fn(key))
        return self.owner[self.points[i % len(self.points)]]

    def get_nodes(self, key, n):
        if not self.points:
            return []
        i = bisect.bisect_left(self.points, self.hash_fn(key))
        out = []
        for step in range(len(self.points)):
            node = self.owner[self.points[(i + step) % len(self.points)]]
            if node not in out:
                out.append(node)
                if len(out) == n:
                    break
        return out
