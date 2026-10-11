# ruff: noqa
# gen
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def build_list(vals):
    head = None
    for v in reversed(vals):
        head = ListNode(v, head)
    return head

def to_list(head):
    out = []
    while head:
        out.append(head.val)
        head = head.next
    return out

import heapq
def merge_k(lists):
    h = [(n.val, i, n) for i, n in enumerate(lists) if n]
    heapq.heapify(h)
    dummy = tail = ListNode()
    while h:
        _, i, n = heapq.heappop(h)
        tail.next = n
        tail = n
        if n.next:
            heapq.heappush(h, (n.next.val, i, n.next))
    return dummy.next
