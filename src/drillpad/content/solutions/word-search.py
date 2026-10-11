# ruff: noqa
# gen
def exist(board, word):
    if not word:
        return True
    if not board or not board[0]:
        return False
    R, C = len(board), len(board[0])
    def dfs(r, c, i):
        if i == len(word):
            return True
        if not (0 <= r < R and 0 <= c < C) or board[r][c] != word[i]:
            return False
        ch = board[r][c]
        board[r][c] = "#"
        found = (dfs(r+1, c, i+1) or dfs(r-1, c, i+1) or dfs(r, c+1, i+1) or dfs(r, c-1, i+1))
        board[r][c] = ch
        return found
    return any(dfs(r, c, 0) for r in range(R) for c in range(C))
