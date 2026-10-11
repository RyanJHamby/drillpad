# ruff: noqa
def num_distinct(s, t):
    n = len(t)
    ways = [1] + [0] * n
    for ch in s:
        for j in range(n, 0, -1):
            if t[j - 1] == ch:
                ways[j] += ways[j - 1]
    return ways[n]
