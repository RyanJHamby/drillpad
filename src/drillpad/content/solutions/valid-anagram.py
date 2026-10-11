# ruff: noqa
from collections import Counter
def is_anagram(s, t):
    if len(s) != len(t):
        return False
    c = Counter(s)
    for ch in t:
        c[ch] -= 1
        if c[ch] < 0:
            return False
    return True
