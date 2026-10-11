# ruff: noqa
from collections import Counter
def check_inclusion(s1, s2):
    m = len(s1)
    if m > len(s2):
        return False
    need = Counter(s1)
    win = Counter(s2[:m])
    if win == need:
        return True
    for i in range(m, len(s2)):
        win[s2[i]] += 1
        out = s2[i - m]
        win[out] -= 1
        if win[out] == 0:
            del win[out]
        if win == need:
            return True
    return False
