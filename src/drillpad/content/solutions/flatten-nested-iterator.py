# ruff: noqa
class NestedIterator:
    def __init__(self, nested):
        self.stack = [iter(nested)]
        self.ready = None
        self.has_ready = False

    def _advance(self):
        while self.stack:
            try:
                item = next(self.stack[-1])
            except StopIteration:
                self.stack.pop()
                continue
            if isinstance(item, list):
                self.stack.append(iter(item))
            else:
                self.ready = item
                self.has_ready = True
                return True
        return False

    def has_next(self):
        return self.has_ready or self._advance()

    def next(self):
        if not self.has_next():
            raise StopIteration
        self.has_ready = False
        return self.ready
