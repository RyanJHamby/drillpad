# ruff: noqa
def reverse_bits(n):
    n &= 0xFFFFFFFF
    r = 0
    for _ in range(32):
        r = (r << 1) | (n & 1)
        n >>= 1
    return r
