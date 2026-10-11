# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class LFUNode:
    __slots__ = ("freq", "key", "next", "prev", "val")
    def __init__(self, key=None, val=None):
        self.key, self.val, self.freq = key, val, 1
        self.prev = self.next = None

class DLL:
    def __init__(self):
        self.head, self.tail = LFUNode(), LFUNode()
        self.head.next, self.tail.prev = self.tail, self.head
        self.size = 0

    def remove(self, node):
        node.prev.next, node.next.prev = node.next, node.prev
        self.size -= 1

    def insert_front(self, node):
        node.next, node.prev = self.head.next, self.head
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def pop_lru(self):  # tail is least-recently-used within this frequency
        node = self.tail.prev
        self.remove(node)
        return node

class LFUCache:
    def __init__(self, capacity: int):
        self.cap = capacity
        self.key_map = {}       # key -> node
        self.freq_map = {}      # freq -> DLL of keys at that freq
        self.min_freq = 0

    def _bump(self, node):
        old_bucket = self.freq_map[node.freq]
        old_bucket.remove(node)
        if old_bucket.size == 0 and self.min_freq == node.freq:
            self.min_freq += 1
        node.freq += 1
        self.freq_map.setdefault(node.freq, DLL()).insert_front(node)

    def get(self, key: int) -> int:
        if key not in self.key_map:
            return -1
        node = self.key_map[key]
        self._bump(node)
        return node.val

    def put(self, key: int, val: int) -> None:
        if self.cap == 0:
            return
        if key in self.key_map:
            node = self.key_map[key]
            node.val = val
            self._bump(node)
            return
        if len(self.key_map) >= self.cap:
            evict_bucket = self.freq_map[self.min_freq]
            evicted = evict_bucket.pop_lru()
            del self.key_map[evicted.key]
        node = LFUNode(key, val)
        self.key_map[key] = node
        self.freq_map.setdefault(1, DLL()).insert_front(node)
        self.min_freq = 1  # any new insert resets global min freq to 1
