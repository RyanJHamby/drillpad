# ruff: noqa
# gen
class Trie:
    def __init__(self):
        self.root = {}
    def insert(self, word):
        n = self.root
        for ch in word:
            n = n.setdefault(ch, {})
        n["$"] = True
    def _walk(self, s):
        n = self.root
        for ch in s:
            n = n.get(ch)
            if n is None:
                return None
        return n
    def search(self, word):
        n = self._walk(word)
        return n is not None and "$" in n
    def starts_with(self, prefix):
        return self._walk(prefix) is not None
