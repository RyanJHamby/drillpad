# ruff: noqa
def spiral_order(matrix):
    if not matrix or not matrix[0]:
        return []
    top, bot = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1
    out = []
    while top <= bot and left <= right:
        for j in range(left, right + 1):
            out.append(matrix[top][j])
        for i in range(top + 1, bot + 1):
            out.append(matrix[i][right])
        if top < bot and left < right:
            for j in range(right - 1, left - 1, -1):
                out.append(matrix[bot][j])
            for i in range(bot - 1, top, -1):
                out.append(matrix[i][left])
        top += 1
        bot -= 1
        left += 1
        right -= 1
    return out
