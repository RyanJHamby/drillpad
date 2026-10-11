# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class DynamicArray:
    def __init__(self):
        self._capacity = 1
        self._size = 0
        self._data = [None] * self._capacity

    def __len__(self):
        return self._size

    def get(self, i):
        if not 0 <= i < self._size:
            raise IndexError(i)
        return self._data[i]

    def set(self, i, val):
        if not 0 <= i < self._size:
            raise IndexError(i)
        self._data[i] = val

    def append(self, val):
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        self._data[self._size] = val
        self._size += 1

    def pop(self):
        if self._size == 0:
            raise IndexError("pop from empty array")
        self._size -= 1
        val = self._data[self._size]
        self._data[self._size] = None
        return val

    def _resize(self, new_capacity):
        new_data = [None] * new_capacity
        for i in range(self._size):
            new_data[i] = self._data[i]
        self._data = new_data
        self._capacity = new_capacity
