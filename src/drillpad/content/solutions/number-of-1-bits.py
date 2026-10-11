# ruff: noqa
def hamming_weight(n):
    n &= 0xFFFFFFFF
    c = 0
    while n:
        n &= n - 1
        c += 1
    return c
