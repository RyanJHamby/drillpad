# ruff: noqa
class Node:
    def __init__(self, key=None, val=None):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None


class DList:
    def __init__(self):
        self.head = Node()      # sentinels remove every empty-list / end-of-list special case
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size = 0

    def push_back(self, node):
        last = self.tail.prev
        last.next = node
        node.prev = last
        node.next = self.tail
        self.tail.prev = node
        self.size += 1

    def unlink(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = node.next = None
        self.size -= 1

    def pop_front(self):
        if self.size == 0:
            return None
        node = self.head.next
        self.unlink(node)
        return node

    def move_to_back(self, node):
        self.unlink(node)
        self.push_back(node)

    def __len__(self):
        return self.size

    def keys(self):
        out, n = [], self.head.next
        while n is not self.tail:
            out.append(n.key)
            n = n.next
        return out


class LRUCache:
    def __init__(self, capacity):
        self.capacity = capacity
        self.map = {}
        self.list = DList()

    def get(self, key):
        node = self.map.get(key)
        if node is None:
            return -1
        self.list.move_to_back(node)
        return node.val

    def put(self, key, val):
        if self.capacity <= 0:
            return
        node = self.map.get(key)
        if node is not None:
            node.val = val
            self.list.move_to_back(node)
            return
        node = Node(key, val)
        self.map[key] = node
        self.list.push_back(node)
        if len(self.list) > self.capacity:
            old = self.list.pop_front()
            del self.map[old.key]

    def order(self):
        return self.list.keys()
