# ruff: noqa
def can_jump(nums):
    far = 0
    last = len(nums) - 1
    for i, x in enumerate(nums):
        if i > far:
            return False
        far = max(far, i + x)
        if far >= last:
            return True
    return True
