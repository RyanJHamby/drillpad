# ruff: noqa
def longest_palindrome(s):
    best_lo, best_len = 0, 0
    n = len(s)
    for c in range(2 * n - 1):
        lo = c // 2
        hi = lo + c % 2
        while lo >= 0 and hi < n and s[lo] == s[hi]:
            lo -= 1
            hi += 1
        if hi - lo - 1 > best_len:
            best_len = hi - lo - 1
            best_lo = lo + 1
    return s[best_lo:best_lo + best_len]
