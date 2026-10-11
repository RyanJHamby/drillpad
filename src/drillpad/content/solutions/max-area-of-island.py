# ruff: noqa
def max_area_of_island(grid):
    if not grid:
        return 0
    R, C = len(grid), len(grid[0])
    seen = [[False] * C for _ in range(R)]
    best = 0
    for r in range(R):
        for c in range(C):
            if grid[r][c] == 1 and not seen[r][c]:
                seen[r][c] = True
                stack = [(r, c)]
                area = 0
                while stack:
                    x, y = stack.pop()
                    area += 1
                    for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                        if 0 <= nx < R and 0 <= ny < C and grid[nx][ny] == 1 and not seen[nx][ny]:
                            seen[nx][ny] = True
                            stack.append((nx, ny))
                best = max(best, area)
    return best
