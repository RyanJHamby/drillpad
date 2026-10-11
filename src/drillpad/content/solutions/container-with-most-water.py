# ruff: noqa
# gen
def max_water(heights):
    i, j, best = 0, len(heights) - 1, 0
    while i < j:
        best = max(best, min(heights[i], heights[j]) * (j - i))
        if heights[i] < heights[j]:
            i += 1
        else:
            j -= 1
    return best
