# ruff: noqa
import threading
import time


class BrokenBarrierError(Exception):
    pass


class CyclicBarrier:
    def __init__(self, parties, action=None):
        if parties < 1:
            raise ValueError("parties must be >= 1")
        self.parties = parties
        self.action = action
        self._cond = threading.Condition(threading.Lock())
        self._count = 0
        self._generation = 0
        self._broken = False

    def _break(self):
        self._broken = True
        self._cond.notify_all()

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            if self._broken:
                raise BrokenBarrierError()
            gen = self._generation
            index = self.parties - 1 - self._count
            self._count += 1
            if self._count == self.parties:
                try:
                    if self.action:
                        self.action()
                except BaseException:
                    self._break()
                    raise
                self._count = 0
                self._generation += 1
                self._cond.notify_all()
                return index
            while gen == self._generation and not self._broken:
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._break()
                        raise BrokenBarrierError()
                    self._cond.wait(remaining)
            if gen == self._generation:      # woken by a break, not by a trip
                raise BrokenBarrierError()
            return index


class CountDownLatch:
    def __init__(self, count):
        if count < 0:
            raise ValueError("count must be >= 0")
        self._cond = threading.Condition(threading.Lock())
        self._count = count

    def count_down(self):
        with self._cond:
            if self._count > 0:
                self._count -= 1
                if self._count == 0:
                    self._cond.notify_all()

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while self._count > 0:
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
            return True

    def get_count(self):
        with self._cond:
            return self._count
