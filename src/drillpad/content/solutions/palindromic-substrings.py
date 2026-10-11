# ruff: noqa
def count_substrings(s):
    n = len(s)
    total = 0
    for c in range(2 * n - 1):
        lo = c // 2
        hi = lo + c % 2
        while lo >= 0 and hi < n and s[lo] == s[hi]:
            total += 1
            lo -= 1
            hi += 1
    return total
