# ruff: noqa
class MinStack:
    def __init__(self):
        self.st = []

    def push(self, x):
        m = x if not self.st else min(x, self.st[-1][1])
        self.st.append((x, m))

    def pop(self):
        return self.st.pop()[0]

    def top(self):
        return self.st[-1][0]

    def get_min(self):
        return self.st[-1][1]
