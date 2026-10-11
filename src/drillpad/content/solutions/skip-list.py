# ruff: noqa
import random


class _Node:
    __slots__ = ("key", "next")

    def __init__(self, key, level):
        self.key = key
        self.next = [None] * level


class SkipList:
    def __init__(self, p=0.5, max_level=16, rng=None):
        self.p = p
        self.max_level = max_level
        self.rng = rng or random.Random()
        self.head = _Node(None, max_level)
        self.level = 1
        self.size = 0

    def _random_level(self):
        lvl = 1
        while lvl < self.max_level and self.rng.random() < self.p:
            lvl += 1
        return lvl

    def _predecessors(self, key):
        update = [self.head] * self.max_level
        node = self.head
        for i in range(self.level - 1, -1, -1):
            while node.next[i] is not None and node.next[i].key < key:
                node = node.next[i]
            update[i] = node
        return update

    def add(self, key):
        update = self._predecessors(key)
        nxt = update[0].next[0]
        if nxt is not None and nxt.key == key:
            return False
        lvl = self._random_level()
        if lvl > self.level:
            self.level = lvl            # update[] already defaults to head above the old level
        node = _Node(key, lvl)
        for i in range(lvl):
            node.next[i] = update[i].next[i]
            update[i].next[i] = node
        self.size += 1
        return True

    def remove(self, key):
        update = self._predecessors(key)
        node = update[0].next[0]
        if node is None or node.key != key:
            return False
        for i in range(len(node.next)):
            if update[i].next[i] is node:
                update[i].next[i] = node.next[i]
        while self.level > 1 and self.head.next[self.level - 1] is None:
            self.level -= 1
        self.size -= 1
        return True

    def __contains__(self, key):
        node = self._predecessors(key)[0].next[0]
        return node is not None and node.key == key

    def __len__(self):
        return self.size

    def __iter__(self):
        node = self.head.next[0]
        while node is not None:
            yield node.key
            node = node.next[0]

    def ceiling(self, key):
        node = self._predecessors(key)[0].next[0]
        return None if node is None else node.key

    def range_query(self, lo, hi):
        out = []
        node = self._predecessors(lo)[0].next[0]
        while node is not None and node.key < hi:
            out.append(node.key)
            node = node.next[0]
        return out
