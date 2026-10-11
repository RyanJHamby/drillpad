# ruff: noqa
from collections import Counter
def is_n_straight_hand(hand, group_size):
    if len(hand) % group_size:
        return False
    cnt = Counter(hand)
    for v in sorted(cnt):
        c = cnt[v]
        if c:
            for k in range(v, v + group_size):
                if cnt.get(k, 0) < c:
                    return False
                cnt[k] -= c
    return True
