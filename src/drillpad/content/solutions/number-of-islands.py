# ruff: noqa
# gen
def num_islands(grid):
    if not grid or not grid[0]:
        return 0
    R, C = len(grid), len(grid[0])
    seen = set()
    count = 0
    for r in range(R):
        for c in range(C):
            if grid[r][c] == 1 and (r, c) not in seen:
                count += 1
                st = [(r, c)]
                seen.add((r, c))
                while st:
                    x, y = st.pop()
                    for nx, ny in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
                        if 0 <= nx < R and 0 <= ny < C and grid[nx][ny] == 1 and (nx, ny) not in seen:
                            seen.add((nx, ny))
                            st.append((nx, ny))
    return count
