# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class _Node:
    __slots__ = ("next", "val")
    def __init__(self, val):
        self.val = val
        self.next = None

class Queue:
    def __init__(self):
        self._head = None
        self._tail = None
        self._size = 0

    def enqueue(self, val):
        node = _Node(val)
        if self._tail is None:      # empty queue
            self._head = self._tail = node
        else:
            self._tail.next = node
            self._tail = node
        self._size += 1

    def dequeue(self):
        if self._head is None:
            raise IndexError("dequeue from empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:      # queue became empty
            self._tail = None
        self._size -= 1
        return node.val

    def peek(self):
        if self._head is None:
            raise IndexError("peek from empty queue")
        return self._head.val

    def __len__(self):
        return self._size
