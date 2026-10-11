# ruff: noqa
# gen
import heapq
from collections import Counter
def top_k_frequent(nums, k):
    if k <= 0:
        return []
    h = []
    for v, c in Counter(nums).items():
        heapq.heappush(h, (c, v))
        if len(h) > k:
            heapq.heappop(h)
    return [v for _, v in h]
