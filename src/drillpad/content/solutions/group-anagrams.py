# ruff: noqa
# gen
from collections import defaultdict
def group_anagrams(strs):
    d = defaultdict(list)
    for s in strs:
        c = [0] * 26
        for ch in s:
            c[ord(ch) - 97] += 1
        d[tuple(c)].append(s)
    return list(d.values())
