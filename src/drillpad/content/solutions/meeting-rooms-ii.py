# ruff: noqa
# gen
import heapq
def min_rooms(intervals):
    h = []
    for s, e in sorted(intervals):
        if h and h[0] <= s:
            heapq.heappop(h)
        heapq.heappush(h, e)
    return len(h)
