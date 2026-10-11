# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
class Node:
    def __init__(self, val, next=None):
        self.val = val
        self.next = next

class SinglyLinkedList:
    def __init__(self):
        self.head = None

    def insert_at_head(self, val):
        self.head = Node(val, self.head)

    def insert_at_index(self, index, val):
        if index == 0:
            self.insert_at_head(val)
            return
        prev = self._node_at(index - 1)
        prev.next = Node(val, prev.next)

    def delete_at_index(self, index):
        if self.head is None:
            raise IndexError("delete from empty list")
        if index == 0:
            self.head = self.head.next
            return
        prev = self._node_at(index - 1)
        if prev.next is None:
            raise IndexError(index)
        prev.next = prev.next.next

    def _node_at(self, index):
        node = self.head
        for _ in range(index):
            if node is None:
                raise IndexError(index)
            node = node.next
        if node is None:
            raise IndexError(index)
        return node

    def reverse(self):
        prev, curr = None, self.head
        while curr:
            nxt = curr.next   # save before overwriting
            curr.next = prev
            prev = curr
            curr = nxt
        self.head = prev

    def to_list(self):
        out, node = [], self.head
        while node:
            out.append(node.val)
            node = node.next
        return out
