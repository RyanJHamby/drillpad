# ruff: noqa
import threading
import time


class Semaphore:
    def __init__(self, value=1):
        if value < 0:
            raise ValueError("value must be >= 0")
        self._cond = threading.Condition(threading.Lock())
        self._value = value

    def acquire(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cond:
            while self._value == 0:
                if deadline is None:
                    self._cond.wait()
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
            self._value -= 1
            return True

    def release(self):
        with self._cond:
            self._value += 1
            self._cond.notify()

    @property
    def available(self):
        with self._cond:
            return self._value
