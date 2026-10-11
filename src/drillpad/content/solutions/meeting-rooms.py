# ruff: noqa
def can_attend_meetings(intervals):
    ivs = sorted(intervals)
    for i in range(1, len(ivs)):
        if ivs[i][0] < ivs[i - 1][1]:
            return False
    return True
