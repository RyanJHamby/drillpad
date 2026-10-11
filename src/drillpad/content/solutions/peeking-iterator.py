# ruff: noqa
_SENTINEL = object()


class PeekingIterator:
    def __init__(self, iterator):
        self.it = iterator
        self.buf = next(self.it, _SENTINEL)

    def peek(self):
        if self.buf is _SENTINEL:
            raise StopIteration
        return self.buf

    def next(self):
        if self.buf is _SENTINEL:
            raise StopIteration
        val = self.buf
        self.buf = next(self.it, _SENTINEL)
        return val

    def has_next(self):
        return self.buf is not _SENTINEL
