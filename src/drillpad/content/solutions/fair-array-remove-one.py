# ruff: noqa
def fair_indices(masses):
    total = [0, 0]
    for i, m in enumerate(masses):
        total[i % 2] += m
    left = [0, 0]
    out = []
    for i, m in enumerate(masses):
        suf = [total[0] - left[0], total[1] - left[1]]
        suf[i % 2] -= m
        if left[0] + suf[1] == left[1] + suf[0]:
            out.append(i)
        left[i % 2] += m
    return out
