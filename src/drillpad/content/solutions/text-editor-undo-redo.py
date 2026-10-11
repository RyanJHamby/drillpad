# ruff: noqa
class TextEditor:
    def __init__(self):
        self._text = ""
        self._undo = []   # commands: ("ins", pos, s) / ("del", pos, s)
        self._redo = []

    @property
    def text(self):
        return self._text

    def _apply(self, cmd):
        kind, pos, s = cmd
        if kind == "ins":
            self._text = self._text[:pos] + s + self._text[pos:]
        else:
            self._text = self._text[:pos] + self._text[pos + len(s):]

    @staticmethod
    def _invert(cmd):
        kind, pos, s = cmd
        return ("del" if kind == "ins" else "ins", pos, s)

    def insert(self, pos, text):
        if not 0 <= pos <= len(self._text):
            raise IndexError("pos out of range")
        if not text:
            return
        cmd = ("ins", pos, text)
        self._apply(cmd)
        self._undo.append(cmd)
        self._redo.clear()

    def delete(self, pos, length):
        if length < 1 or pos < 0 or pos + length > len(self._text):
            raise IndexError("range out of bounds")
        cmd = ("del", pos, self._text[pos:pos + length])
        self._apply(cmd)
        self._undo.append(cmd)
        self._redo.clear()

    def undo(self):
        if not self._undo:
            return False
        cmd = self._undo.pop()
        self._apply(self._invert(cmd))
        self._redo.append(cmd)
        return True

    def redo(self):
        if not self._redo:
            return False
        cmd = self._redo.pop()
        self._apply(cmd)
        self._undo.append(cmd)
        return True
