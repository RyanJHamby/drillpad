# ruff: noqa
def reverse(x):
    sign = -1 if x < 0 else 1
    n = abs(x)
    r = 0
    while n:
        n, d = divmod(n, 10)
        r = r * 10 + d
    r *= sign
    if r < -2**31 or r > 2**31 - 1:
        return 0
    return r
