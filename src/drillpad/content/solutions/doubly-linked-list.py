# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class DNode:
    def __init__(self, val, prev=None, next=None):
        self.val = val
        self.prev = prev
        self.next = next

class DoublyLinkedList:
    def __init__(self):
        # sentinel head/tail avoid null-checks on every insert/delete
        self.head = DNode(None)
        self.tail = DNode(None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def push_front(self, val):
        node = DNode(val)
        self._insert_after(self.head, node)
        return node

    def push_back(self, val):
        node = DNode(val)
        self._insert_after(self.tail.prev, node)
        return node

    def remove(self, node):
        # O(1): no traversal needed, node carries its own neighbors
        node.prev.next = node.next
        node.next.prev = node.prev
        node.prev = node.next = None

    def move_to_front(self, node):
        self.remove_from_list_only(node)
        self._insert_after(self.head, node)

    def remove_from_list_only(self, node):
        node.prev.next = node.next
        node.next.prev = node.prev

    def _insert_after(self, anchor, node):
        node.prev = anchor
        node.next = anchor.next
        anchor.next.prev = node
        anchor.next = node

    def to_list(self):
        out, node = [], self.head.next
        while node is not self.tail:
            out.append(node.val)
            node = node.next
        return out
