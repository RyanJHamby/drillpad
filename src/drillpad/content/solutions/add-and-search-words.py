# ruff: noqa
# gen
class WordDictionary:
    def __init__(self):
        self.root = {}
    def add_word(self, word):
        n = self.root
        for ch in word:
            n = n.setdefault(ch, {})
        n["$"] = True
    def search(self, pattern):
        def go(n, i):
            if i == len(pattern):
                return "$" in n
            ch = pattern[i]
            if ch == ".":
                return any(go(c, i + 1) for k, c in n.items() if k != "$")
            return ch in n and go(n[ch], i + 1)
        return go(self.root, 0)
