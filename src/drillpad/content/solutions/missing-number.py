# ruff: noqa
def missing_number(nums):
    r = len(nums)
    for i, x in enumerate(nums):
        r ^= i ^ x
    return r
