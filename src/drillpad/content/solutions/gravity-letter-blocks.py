# ruff: noqa
def apply_gravity_blocks(grid):
    rows = len(grid)
    if rows == 0:
        return grid
    cols = len(grid[0])
    present = 0  # bit i set means chr(97 + i) occurs in the grid: one int, O(1) space
    for row in grid:
        for ch in row:
            if "a" <= ch <= "z":
                present |= 1 << (ord(ch) - 97)
    moved = True
    while moved:  # a block resting on another can only fall after the one below it does, so repeat until stable
        moved = False
        for i in range(26):
            if not (present >> i) & 1:
                continue
            letter = chr(97 + i)
            drop = rows  # shortest free run below the block, taken over every column the block occupies
            for c in range(cols):
                r = rows - 1
                while r >= 0 and grid[r][c] != letter:
                    r -= 1  # lowest cell of this block in column c
                if r < 0:
                    continue
                free = 0
                k = r + 1
                while k < rows and grid[k][c] == ".":
                    free += 1
                    k += 1
                if free < drop:
                    drop = free
                if drop == 0:
                    break
            if drop > 0:
                for r in range(rows - 1, -1, -1):  # bottom row first, so a cell never lands on an unmoved cell of itself
                    for c in range(cols):
                        if grid[r][c] == letter:
                            grid[r + drop][c] = letter
                            grid[r][c] = "."
                moved = True
    return grid
