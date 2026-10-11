# ruff: noqa
class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

def build_cycle(vals, pos):
    """Build a list from vals whose tail links to the node at index pos (pos=-1 for no cycle)."""
    nodes = [ListNode(v) for v in vals]
    for a, b in zip(nodes, nodes[1:]):
        a.next = b
    if nodes and pos >= 0:
        nodes[-1].next = nodes[pos]
    return nodes[0] if nodes else None

def has_cycle(head):
    slow = fast = head
    while fast and fast.next:
        slow = slow.next
        fast = fast.next.next
        if slow is fast:
            return True
    return False
