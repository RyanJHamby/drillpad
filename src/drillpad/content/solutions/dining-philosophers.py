# ruff: noqa
import threading


class DiningTable:
    def __init__(self, n):
        self.n = n
        self.forks = [threading.Lock() for _ in range(n)]

    def dine(self, i, eat):
        if not 0 <= i < self.n:
            raise ValueError(i)
        order = sorted({i, (i + 1) % self.n})   # global lock order breaks the cycle; n == 1 has one fork
        acquired = []
        try:
            for f in order:
                self.forks[f].acquire()
                acquired.append(f)
            return eat()
        finally:
            for f in reversed(acquired):
                self.forks[f].release()
