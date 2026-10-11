# ruff: noqa
def my_pow(x, n):
    if n < 0:
        x = 1.0 / x
        n = -n
    result = 1.0
    base = x
    while n:
        if n & 1:
            result *= base
        base *= base
        n >>= 1
    return result
