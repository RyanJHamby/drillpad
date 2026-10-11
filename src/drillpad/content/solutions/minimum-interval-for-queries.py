# ruff: noqa
import heapq
def min_interval(intervals, queries):
    ivs = sorted(intervals)
    order = sorted(range(len(queries)), key=lambda i: queries[i])
    res = [-1] * len(queries)
    h = []
    j = 0
    for qi in order:
        q = queries[qi]
        while j < len(ivs) and ivs[j][0] <= q:
            l, r = ivs[j]
            heapq.heappush(h, (r - l + 1, r))
            j += 1
        while h and h[0][1] < q:
            heapq.heappop(h)
        if h:
            res[qi] = h[0][0]
    return res
