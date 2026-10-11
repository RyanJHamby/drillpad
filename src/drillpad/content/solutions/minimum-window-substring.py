# ruff: noqa
# gen
from collections import Counter
def min_window(s, t):
    if not t or not s:
        return ""
    need = Counter(t)
    missing = len(t)
    l = 0
    best = (float("inf"), 0, 0)
    for r, ch in enumerate(s):
        if need[ch] > 0:
            missing -= 1
        need[ch] -= 1
        if missing == 0:
            while need[s[l]] < 0:
                need[s[l]] += 1
                l += 1
            if r - l + 1 < best[0]:
                best = (r - l + 1, l, r + 1)
            need[s[l]] += 1
            missing += 1
            l += 1
    return "" if best[0] == float("inf") else s[best[1]:best[2]]
