# ruff: noqa
def parse(text):
    p = _Parser(text)
    p.ws()
    v = p.value()
    p.ws()
    if p.i != len(text):
        raise ValueError("trailing data at %d" % p.i)
    return v


class _Parser:
    ESC = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}

    def __init__(self, s):
        self.s = s
        self.i = 0

    def ws(self):
        s = self.s
        while self.i < len(s) and s[self.i] in " \t\r\n":
            self.i += 1

    def value(self):
        s = self.s
        if self.i >= len(s):
            raise ValueError("unexpected end")
        c = s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"':
            return self.string()
        if c == "-" or c.isdigit():
            return self.number()
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if s.startswith(lit, self.i):
                self.i += len(lit)
                return val
        raise ValueError("unexpected %r at %d" % (c, self.i))

    def obj(self):
        self.i += 1
        out = {}
        self.ws()
        if self.s[self.i:self.i + 1] == "}":
            self.i += 1
            return out
        while True:
            self.ws()
            if self.s[self.i:self.i + 1] != '"':
                raise ValueError("object key expected")
            k = self.string()
            self.ws()
            if self.s[self.i:self.i + 1] != ":":
                raise ValueError("colon expected")
            self.i += 1
            self.ws()
            out[k] = self.value()
            self.ws()
            c = self.s[self.i:self.i + 1]
            self.i += 1
            if c == "}":
                return out
            if c != ",":
                raise ValueError("comma or } expected")

    def arr(self):
        self.i += 1
        out = []
        self.ws()
        if self.s[self.i:self.i + 1] == "]":
            self.i += 1
            return out
        while True:
            self.ws()
            out.append(self.value())
            self.ws()
            c = self.s[self.i:self.i + 1]
            self.i += 1
            if c == "]":
                return out
            if c != ",":
                raise ValueError("comma or ] expected")

    def string(self):
        s = self.s
        self.i += 1
        out = []
        while True:
            if self.i >= len(s):
                raise ValueError("unterminated string")
            c = s[self.i]
            self.i += 1
            if c == '"':
                return "".join(out)
            if c == "\\":
                if self.i >= len(s):
                    raise ValueError("bad escape")
                e = s[self.i]
                self.i += 1
                if e in self.ESC:
                    out.append(self.ESC[e])
                elif e == "u":
                    hexd = s[self.i:self.i + 4]
                    if len(hexd) != 4 or any(h not in "0123456789abcdefABCDEF" for h in hexd):
                        raise ValueError("bad unicode escape")
                    out.append(chr(int(hexd, 16)))
                    self.i += 4
                else:
                    raise ValueError("bad escape")
            elif ord(c) < 0x20:
                raise ValueError("control character in string")
            else:
                out.append(c)

    def number(self):
        s = self.s
        start = self.i
        if s[self.i] == "-":
            self.i += 1
        if self.i >= len(s) or not s[self.i].isdigit():
            raise ValueError("bad number")
        if s[self.i] == "0":
            self.i += 1
        else:
            while self.i < len(s) and s[self.i].isdigit():
                self.i += 1
        is_float = False
        if self.i < len(s) and s[self.i] == ".":
            is_float = True
            self.i += 1
            if self.i >= len(s) or not s[self.i].isdigit():
                raise ValueError("bad fraction")
            while self.i < len(s) and s[self.i].isdigit():
                self.i += 1
        if self.i < len(s) and s[self.i] in "eE":
            is_float = True
            self.i += 1
            if self.i < len(s) and s[self.i] in "+-":
                self.i += 1
            if self.i >= len(s) or not s[self.i].isdigit():
                raise ValueError("bad exponent")
            while self.i < len(s) and s[self.i].isdigit():
                self.i += 1
        text = s[start:self.i]
        return float(text) if is_float else int(text)
