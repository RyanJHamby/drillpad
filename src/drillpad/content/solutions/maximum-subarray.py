# ruff: noqa
def max_subarray(nums):
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        if cur > best:
            best = cur
    return best
