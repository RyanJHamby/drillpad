# ruff: noqa
from collections import deque


class MovingAverage:
    def __init__(self, size):
        if size < 1:
            raise ValueError("size must be >= 1")
        self.size = size
        self.window = deque()
        self.total = 0

    def next(self, val):
        self.window.append(val)
        self.total += val
        if len(self.window) > self.size:
            self.total -= self.window.popleft()
        return self.total / len(self.window)
