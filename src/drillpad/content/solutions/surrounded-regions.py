# ruff: noqa
def solve(board):
    if not board or not board[0]:
        return board
    R, C = len(board), len(board[0])
    stack = [(r, c) for r in range(R) for c in range(C)
             if (r in (0, R - 1) or c in (0, C - 1)) and board[r][c] == "O"]
    for r, c in stack:
        board[r][c] = "S"
    while stack:
        r, c = stack.pop()
        for nr, nc in ((r+1, c), (r-1, c), (r, c+1), (r, c-1)):
            if 0 <= nr < R and 0 <= nc < C and board[nr][nc] == "O":
                board[nr][nc] = "S"
                stack.append((nr, nc))
    for r in range(R):
        for c in range(C):
            if board[r][c] == "O":
                board[r][c] = "X"
            elif board[r][c] == "S":
                board[r][c] = "O"
    return board
