# ruff: noqa
def find_cheapest_price(n, flights, src, dst, k):
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    for _ in range(k + 1):
        nxt = dist[:]
        for u, v, p in flights:
            if dist[u] + p < nxt[v]:
                nxt[v] = dist[u] + p
        dist = nxt
    return dist[dst] if dist[dst] != INF else -1
