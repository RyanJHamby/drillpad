# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
# Array-based (reuses the doubling-resize idea from the dynamic array)
class ArrayStack:
    def __init__(self):
        self._data = [None] * 1
        self._capacity = 1
        self._size = 0

    def is_empty(self):
        return self._size == 0

    def push(self, val):
        if self._size == self._capacity:
            self._resize(self._capacity * 2)
        self._data[self._size] = val
        self._size += 1

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        self._size -= 1
        val = self._data[self._size]
        self._data[self._size] = None
        return val

    def peek(self):
        if self.is_empty():
            raise IndexError("peek on empty stack")
        return self._data[self._size - 1]

    def _resize(self, new_capacity):
        new_data = [None] * new_capacity
        for i in range(self._size):
            new_data[i] = self._data[i]
        self._data = new_data
        self._capacity = new_capacity


# Linked-list-based: push/pop at head, no resizing ever needed
class LinkedStackNode:
    def __init__(self, val, next=None):
        self.val = val
        self.next = next

class LinkedStack:
    def __init__(self):
        self._top = None
        self._size = 0

    def is_empty(self):
        return self._top is None

    def push(self, val):
        self._top = LinkedStackNode(val, self._top)
        self._size += 1

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from empty stack")
        node = self._top
        self._top = node.next
        self._size -= 1
        return node.val

    def peek(self):
        if self.is_empty():
            raise IndexError("peek on empty stack")
        return self._top.val
