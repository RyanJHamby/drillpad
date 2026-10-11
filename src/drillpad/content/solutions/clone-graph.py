# ruff: noqa
# gen
class Node:
    def __init__(self, val=0, neighbors=None):
        self.val = val
        self.neighbors = neighbors if neighbors is not None else []

def build_graph(adj):
    """adj[i] lists the neighbor values of node i+1. Returns node 1 (or None if adj is empty)."""
    if not adj:
        return None
    nodes = [Node(i + 1) for i in range(len(adj))]
    for i, nb in enumerate(adj):
        nodes[i].neighbors = [nodes[j - 1] for j in nb]
    return nodes[0]

def graph_to_adj(node):
    """Inverse of build_graph (nodes must be labelled 1..n)."""
    if node is None:
        return []
    seen, stack = {node.val: node}, [node]
    while stack:
        n = stack.pop()
        for m in n.neighbors:
            if m.val not in seen:
                seen[m.val] = m
                stack.append(m)
    return [[m.val for m in seen[v].neighbors] for v in sorted(seen)]

def clone_graph(node):
    if node is None:
        return None
    copies = {node: Node(node.val)}
    stack = [node]
    while stack:
        n = stack.pop()
        for m in n.neighbors:
            if m not in copies:
                copies[m] = Node(m.val)
                stack.append(m)
            copies[n].neighbors.append(copies[m])
    return copies[node]
