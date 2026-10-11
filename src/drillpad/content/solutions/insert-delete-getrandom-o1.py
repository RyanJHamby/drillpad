# ruff: noqa
import random


class RandomizedSet:
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.items = []
        self.pos = {}

    def insert(self, val):
        if val in self.pos:
            return False
        self.pos[val] = len(self.items)
        self.items.append(val)
        return True

    def remove(self, val):
        i = self.pos.pop(val, None)
        if i is None:
            return False
        last = self.items.pop()
        if i < len(self.items):      # val was not the last element: move last into its slot
            self.items[i] = last
            self.pos[last] = i
        return True

    def get_random(self):
        if not self.items:
            raise IndexError("empty set")
        return self.items[self.rng.randrange(len(self.items))]

    def __len__(self):
        return len(self.items)
