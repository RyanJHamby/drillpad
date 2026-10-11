# ruff: noqa
import heapq


def k_closest(points, k):
    if k <= 0:
        return []
    heap = []
    for x, y in points:
        d = x * x + y * y
        if len(heap) < k:
            heapq.heappush(heap, (-d, x, y))
        elif -d > heap[0][0]:
            heapq.heapreplace(heap, (-d, x, y))
    return [[x, y] for _, x, y in heap]
