# ruff: noqa
def trap(height):
    l, r = 0, len(height) - 1
    lm = rm = 0
    total = 0
    while l < r:
        if height[l] < height[r]:
            lm = max(lm, height[l])
            total += lm - height[l]
            l += 1
        else:
            rm = max(rm, height[r])
            total += rm - height[r]
            r -= 1
    return total
