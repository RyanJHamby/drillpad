# ruff: noqa
def rob(nums):
    def line(lo, hi):
        a = b = 0
        for i in range(lo, hi):
            a, b = b, max(b, a + nums[i])
        return b
    n = len(nums)
    if n == 1:
        return nums[0]
    return max(line(0, n - 1), line(1, n))
