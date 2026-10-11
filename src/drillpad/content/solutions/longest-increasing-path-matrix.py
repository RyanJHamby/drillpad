# ruff: noqa
def longest_increasing_path(matrix):
    if not matrix or not matrix[0]:
        return 0
    rows, cols = len(matrix), len(matrix[0])
    cells = sorted((matrix[r][c], r, c) for r in range(rows) for c in range(cols))
    best = [[1] * cols for _ in range(rows)]
    ans = 1
    for v, r, c in cells:
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and matrix[nr][nc] < v:
                if best[nr][nc] + 1 > best[r][c]:
                    best[r][c] = best[nr][nc] + 1
        ans = max(ans, best[r][c])
    return ans
