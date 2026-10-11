# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class RingBuffer:
    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._data = [None] * capacity
        self._head = 0   # index of oldest element
        self._size = 0

    def __len__(self):
        return self._size

    def is_full(self):
        return self._size == self._capacity

    def enqueue(self, val):
        if self.is_full():
            raise OverflowError("buffer is full")
        tail = (self._head + self._size) % self._capacity
        self._data[tail] = val
        self._size += 1

    def dequeue(self):
        if self._size == 0:
            raise IndexError("dequeue from empty buffer")
        val = self._data[self._head]
        self._data[self._head] = None
        self._head = (self._head + 1) % self._capacity
        self._size -= 1
        return val

    def peek(self):
        if self._size == 0:
            raise IndexError("peek on empty buffer")
        return self._data[self._head]
