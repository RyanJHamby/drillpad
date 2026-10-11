# ruff: noqa
import heapq


class _Node:
    __slots__ = ("children", "counts")

    def __init__(self):
        self.children = {}
        self.counts = {}   # sentence -> count for every sentence passing through this node


class AutocompleteSystem:
    def __init__(self, sentences, times):
        self.root = _Node()
        self.cur = self.root
        self.buf = []
        self.dead = False
        for s, t in zip(sentences, times):
            self._add(s, t)

    def _add(self, s, t):
        node = self.root
        for ch in s:
            node = node.children.setdefault(ch, _Node())
            node.counts[s] = node.counts.get(s, 0) + t

    def input(self, c):
        if c == "#":
            self._add("".join(self.buf), 1)
            self.buf = []
            self.cur = self.root
            self.dead = False
            return []
        self.buf.append(c)
        if self.dead or c not in self.cur.children:
            self.dead = True
            return []
        self.cur = self.cur.children[c]
        best = heapq.nsmallest(3, self.cur.counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return [s for s, _ in best]
