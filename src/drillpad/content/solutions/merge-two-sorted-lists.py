# ruff: noqa
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

def merge_two(l1, l2):
    dummy = tail = ListNode()
    while l1 and l2:
        if l2.val < l1.val:
            tail.next, l2 = l2, l2.next
        else:
            tail.next, l1 = l1, l1.next
        tail = tail.next
    tail.next = l1 or l2
    return dummy.next
