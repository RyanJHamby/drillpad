# ruff: noqa
class TicTacToe:
    def __init__(self, n):
        if n < 1:
            raise ValueError("n must be >= 1")
        self.n = n
        self.rows = {1: [0] * n, 2: [0] * n}
        self.cols = {1: [0] * n, 2: [0] * n}
        self.diag = {1: 0, 2: 0}
        self.anti = {1: 0, 2: 0}
        self.taken = set()
        self.winner = 0

    def move(self, row, col, player):
        n = self.n
        if player not in (1, 2) or not (0 <= row < n and 0 <= col < n):
            raise ValueError("bad move")
        if self.winner or (row, col) in self.taken:
            raise ValueError("illegal move")
        self.taken.add((row, col))
        self.rows[player][row] += 1
        self.cols[player][col] += 1
        if row == col:
            self.diag[player] += 1
        if row + col == n - 1:
            self.anti[player] += 1
        if n in (self.rows[player][row], self.cols[player][col], self.diag[player], self.anti[player]):
            self.winner = player
        return self.winner
