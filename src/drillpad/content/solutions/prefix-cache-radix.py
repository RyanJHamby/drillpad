# ruff: noqa
import heapq


class _Node:
    __slots__ = ("parent", "tok", "children", "last", "serial", "alive")

    def __init__(self, parent, tok, serial):
        self.parent, self.tok, self.children = parent, tok, {}
        self.last, self.serial, self.alive = 0, serial, True


class PrefixCache:
    def __init__(self, capacity):
        if capacity < 0:
            raise ValueError("capacity")
        self.capacity = capacity
        self.root = _Node(None, None, -1)
        self.n = 0
        self.serial = 0
        self.heap = []        # (last, serial, node) candidates, lazily validated

    def size(self):
        return self.n

    def _push_if_leaf(self, node):
        if node is not self.root and not node.children:
            heapq.heappush(self.heap, (node.last, node.serial, node))

    def insert(self, tokens, now):
        if self.capacity == 0:
            return 0
        node, new = self.root, 0
        for t in tokens:
            child = node.children.get(t)
            if child is None:
                child = _Node(node, t, self.serial)
                self.serial += 1
                node.children[t] = child
                self.n += 1
                new += 1
            child.last = now
            node = child
        self._push_if_leaf(node)
        self._evict()
        return new

    def match(self, tokens, now):
        node, length = self.root, 0
        for t in tokens:
            child = node.children.get(t)
            if child is None:
                break
            child.last = now
            node, length = child, length + 1
        if length:
            self._push_if_leaf(node)
        return length

    def _evict(self):
        while self.n > self.capacity:
            last, serial, node = heapq.heappop(self.heap)
            if not node.alive or node.children or node.last != last:
                continue
            del node.parent.children[node.tok]
            node.alive = False
            self.n -= 1
            self._push_if_leaf(node.parent)
