# ruff: noqa
class Node:
    def __init__(self, val=0, next=None, random=None):
        self.val = val
        self.next = next
        self.random = random

def build_random_list(vals, randoms):
    """randoms[i] is the index of node i's random target, or None."""
    nodes = [Node(v) for v in vals]
    for i, node in enumerate(nodes):
        node.next = nodes[i + 1] if i + 1 < len(nodes) else None
        node.random = nodes[randoms[i]] if randoms[i] is not None else None
    return nodes[0] if nodes else None

def random_pairs(head):
    """[[val, index-of-random-or-None], ...] describing the list."""
    index, cur, i = {}, head, 0
    while cur:
        index[id(cur)] = i
        cur, i = cur.next, i + 1
    out, cur = [], head
    while cur:
        out.append([cur.val, index[id(cur.random)] if cur.random else None])
        cur = cur.next
    return out

def is_deep_copy(orig, copy):
    """True if no node reachable from copy (next or random) is a node of orig."""
    orig_ids, n = set(), orig
    while n:
        orig_ids.add(id(n))
        n = n.next
    n = copy
    while n:
        if id(n) in orig_ids or (n.random is not None and id(n.random) in orig_ids):
            return False
        n = n.next
    return True

def copy_random_list(head):
    m = {None: None}
    cur = head
    while cur:
        m[cur] = Node(cur.val)
        cur = cur.next
    cur = head
    while cur:
        m[cur].next = m[cur.next]
        m[cur].random = m[cur.random]
        cur = cur.next
    return m[head]
