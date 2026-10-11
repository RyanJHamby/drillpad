# ruff: noqa
from collections import deque


class SnakeGame:
    D = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}

    def __init__(self, width, height, food):
        self.w, self.h = width, height
        self.food = [tuple(f) for f in food]
        self.fi = 0
        self.body = deque([(0, 0)])
        self.cells = {(0, 0)}
        self.score = 0
        self.over = False

    def move(self, direction):
        if self.over:
            return -1
        dr, dc = self.D[direction]
        r, c = self.body[0]
        nr, nc = r + dr, c + dc
        if not (0 <= nr < self.h and 0 <= nc < self.w):
            self.over = True
            return -1
        eating = self.fi < len(self.food) and self.food[self.fi] == (nr, nc)
        if not eating:
            tail = self.body.pop()          # vacate the tail first so it can be re-entered
            self.cells.discard(tail)
        if (nr, nc) in self.cells:
            self.over = True
            return -1
        self.body.appendleft((nr, nc))
        self.cells.add((nr, nc))
        if eating:
            self.fi += 1
            self.score += 1
        return self.score
