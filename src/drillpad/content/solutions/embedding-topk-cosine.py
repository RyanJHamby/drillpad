# ruff: noqa
import heapq
import math


class EmbeddingIndex:
    def __init__(self):
        self.items = {}        # id -> (order, unit vector)
        self.counter = 0
        self.dim = None

    def __len__(self):
        return len(self.items)

    @staticmethod
    def _unit(vec):
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0:
            return None
        return [x / norm for x in vec]

    def add(self, item_id, vec):
        if not vec:
            raise ValueError("empty vector")
        if self.dim is None or not self.items:
            self.dim = len(vec)
        elif len(vec) != self.dim:
            raise ValueError("dimension mismatch")
        unit = self._unit(vec)
        if item_id in self.items:
            self.items[item_id] = (self.items[item_id][0], unit)
        else:
            self.items[item_id] = (self.counter, unit)
            self.counter += 1

    def remove(self, item_id):
        del self.items[item_id]

    def search(self, query, k):
        if k <= 0 or not self.items:
            return []
        if len(query) != self.dim:
            raise ValueError("dimension mismatch")
        q = self._unit(query)
        scored = []
        for item_id, (order, unit) in self.items.items():
            if q is None or unit is None:
                s = 0.0
            else:
                s = sum(a * b for a, b in zip(q, unit))
            scored.append((-s, order, item_id))
        return [(i, -ns) for ns, _, i in heapq.nsmallest(k, scored)]
