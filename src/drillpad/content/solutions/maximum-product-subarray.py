# ruff: noqa
def max_product(nums):
    hi = lo = best = nums[0]
    for x in nums[1:]:
        c = (x, hi * x, lo * x)
        hi, lo = max(c), min(c)
        best = max(best, hi)
    return best
