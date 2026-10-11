# ruff: noqa
def single_number(nums):
    r = 0
    for x in nums:
        r ^= x
    return r
