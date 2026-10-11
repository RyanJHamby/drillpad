# ruff: noqa
import math


def find_arbitrage(rates):
    nodes = []
    seen = set()
    edges = []
    for a, b, r in rates:
        if not r > 0:
            raise ValueError("rates must be positive")
        for x in (a, b):
            if x not in seen:
                seen.add(x)
                nodes.append(x)
        edges.append((a, b, -math.log(r)))
    n = len(nodes)
    if n == 0:
        return []
    dist = {x: 0.0 for x in nodes}
    pred = {x: None for x in nodes}
    last = None
    for _ in range(n):
        last = None
        for a, b, w in edges:
            if dist[a] + w < dist[b] - 1e-12:
                dist[b] = dist[a] + w
                pred[b] = a
                last = b
        if last is None:
            return []
    x = last
    for _ in range(n):
        x = pred[x]
    cycle = [x]
    y = pred[x]
    while y != x:
        cycle.append(y)
        y = pred[y]
    cycle.append(x)
    cycle.reverse()
    return cycle
