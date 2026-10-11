# ruff: noqa
def get_sum(a, b):
    mask = 0xFFFFFFFF
    a &= mask
    b &= mask
    while b:
        a, b = (a ^ b) & mask, ((a & b) << 1) & mask
    return a if a <= 0x7FFFFFFF else ~(a ^ mask)
