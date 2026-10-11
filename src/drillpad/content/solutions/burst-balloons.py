# ruff: noqa
def max_coins(nums):
    a = [1] + list(nums) + [1]
    n = len(a)
    best = [[0] * n for _ in range(n)]
    for gap in range(2, n):
        for l in range(n - gap):
            r = l + gap
            m = 0
            for k in range(l + 1, r):
                v = best[l][k] + best[k][r] + a[l] * a[k] * a[r]
                if v > m:
                    m = v
            best[l][r] = m
    return best[0][n - 1]
