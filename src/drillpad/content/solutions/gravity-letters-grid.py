# ruff: noqa
def apply_gravity(grid):
    rows = len(grid)
    if rows == 0:
        return grid
    for c in range(len(grid[0])):
        write = rows - 1  # lowest free cell in the current segment of this column
        for r in range(rows - 1, -1, -1):
            cell = grid[r][c]
            if cell == "#":
                write = r - 1  # nothing falls through an obstacle
            elif cell != ".":
                if r != write:
                    grid[write][c] = cell
                    grid[r][c] = "."
                write -= 1
    return grid
