# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
import time

class Node:
    __slots__ = ("key", "next", "prev", "val")
    def __init__(self, key=None, val=None):
        self.key, self.val = key, val
        self.prev = self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.map = {}  # key -> Node
        # sentinel head/tail avoid null checks at boundaries
        self.head, self.tail = Node(), Node()
        self.head.next, self.tail.prev = self.tail, self.head
        self.deadline = {}  # key -> monotonic expiry time, only for keys set with a ttl

    def _remove(self, node):
        node.prev.next, node.next.prev = node.next, node.prev

    def _insert_front(self, node):
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: int) -> int:
        if key not in self.map:
            return -1
        if self._expired(key):
            self._drop(key)
            return -1
        node = self.map[key]
        self._remove(node)
        self._insert_front(node)  # mark most-recently-used
        return node.val

    def _expired(self, key) -> bool:
        d = self.deadline.get(key)
        return d is not None and time.monotonic() >= d

    def _drop(self, key) -> None:
        self._remove(self.map.pop(key))
        self.deadline.pop(key, None)

    def set_with_ttl(self, key, val, ttl_ms) -> None:
        self.put(key, val)
        self.deadline[key] = time.monotonic() + ttl_ms / 1000

    def put(self, key: int, val: int) -> None:
        self.deadline.pop(key, None)  # an overwrite resets any earlier ttl
        if key in self.map:
            self._remove(self.map[key])
        node = Node(key, val)
        self.map[key] = node
        self._insert_front(node)
        if len(self.map) > self.cap:
            lru = self.tail.prev
            self._remove(lru)
            del self.map[lru.key]
            self.deadline.pop(lru.key, None)
