# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class Deque:
    def __init__(self, capacity=8):
        self._buf = [None] * capacity
        self._cap = capacity
        self._front = 0     # index of front element
        self._size = 0

    def _resize(self, new_cap):
        new_buf = [None] * new_cap
        for i in range(self._size):
            new_buf[i] = self._buf[(self._front + i) % self._cap]
        self._buf = new_buf
        self._cap = new_cap
        self._front = 0

    def push_back(self, val):
        if self._size == self._cap:
            self._resize(self._cap * 2)
        idx = (self._front + self._size) % self._cap
        self._buf[idx] = val
        self._size += 1

    def push_front(self, val):
        if self._size == self._cap:
            self._resize(self._cap * 2)
        self._front = (self._front - 1) % self._cap   # wrap backward
        self._buf[self._front] = val
        self._size += 1

    def pop_back(self):
        if self._size == 0:
            raise IndexError("pop from empty deque")
        idx = (self._front + self._size - 1) % self._cap
        val = self._buf[idx]
        self._buf[idx] = None
        self._size -= 1
        self._maybe_shrink()
        return val

    def pop_front(self):
        if self._size == 0:
            raise IndexError("pop from empty deque")
        val = self._buf[self._front]
        self._buf[self._front] = None
        self._front = (self._front + 1) % self._cap
        self._size -= 1
        self._maybe_shrink()
        return val

    def _maybe_shrink(self):
        if self._cap > 8 and self._size <= self._cap // 4:
            self._resize(self._cap // 2)

    def __len__(self):
        return self._size
