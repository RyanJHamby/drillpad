# ruff: noqa
import re

_CELL = re.compile(r"^[A-Z]+[0-9]+$")
_TOKEN = re.compile(r"(\d+(?:\.\d+)?)|([A-Z]+[0-9]+)|([-+*()])")


def _tokenize(s):
    toks = []
    pos = 0
    s = s.strip()
    while pos < len(s):
        if s[pos].isspace():
            pos += 1
            continue
        m = _TOKEN.match(s, pos)
        if not m:
            raise ValueError("bad token at %d" % pos)
        if m.group(1) is not None:
            v = m.group(1)
            toks.append(("num", float(v) if "." in v else int(v)))
        elif m.group(2) is not None:
            toks.append(("ref", m.group(2)))
        else:
            toks.append(("op", m.group(3)))
        pos = m.end()
    return toks


def _parse(text):
    toks = _tokenize(text)
    refs = set()
    i = 0

    def peek():
        return toks[i] if i < len(toks) else (None, None)

    def expr():
        nonlocal i
        node = term()
        while peek() in (("op", "+"), ("op", "-")):
            op = toks[i][1]
            i += 1
            node = (op, node, term())
        return node

    def term():
        nonlocal i
        node = unary()
        while peek() == ("op", "*"):
            i += 1
            node = ("*", node, unary())
        return node

    def unary():
        nonlocal i
        if peek() == ("op", "-"):
            i += 1
            return ("neg", unary())
        return atom()

    def atom():
        nonlocal i
        kind, val = peek()
        if kind == "num":
            i += 1
            return ("num", val)
        if kind == "ref":
            i += 1
            refs.add(val)
            return ("ref", val)
        if (kind, val) == ("op", "("):
            i += 1
            node = expr()
            if peek() != ("op", ")"):
                raise ValueError("missing )")
            i += 1
            return node
        raise ValueError("unexpected token")

    node = expr()
    if i != len(toks):
        raise ValueError("trailing tokens")
    return node, refs


class Spreadsheet:
    def __init__(self):
        self.evaluations = 0
        self._formula = {}  # cell -> ast
        self._value = {}
        self._parents = {}
        self._children = {}

    def _eval(self, node):
        k = node[0]
        if k == "num":
            return node[1]
        if k == "ref":
            return self._value.get(node[1], 0)
        if k == "neg":
            return -self._eval(node[1])
        a = self._eval(node[1])
        b = self._eval(node[2])
        return a + b if k == "+" else a - b if k == "-" else a * b

    def _dependents(self, cell):
        seen = {cell}
        stack = [cell]
        while stack:
            for ch in self._children.get(stack.pop(), ()):
                if ch not in seen:
                    seen.add(ch)
                    stack.append(ch)
        return seen

    def _topo(self, cell):
        order = []
        seen = {cell}
        stack = [(cell, iter(self._children.get(cell, ())))]
        while stack:
            node, it = stack[-1]
            for ch in it:
                if ch not in seen:
                    seen.add(ch)
                    stack.append((ch, iter(self._children.get(ch, ()))))
                    break
            else:
                order.append(node)
                stack.pop()
        order.reverse()
        return order

    def set(self, cell, content):
        if not isinstance(cell, str) or not _CELL.match(cell):
            raise ValueError("bad cell name")
        ast = None
        refs = set()
        if isinstance(content, str):
            if not content.startswith("="):
                raise ValueError("formula must start with =")
            ast, refs = _parse(content[1:])
            if refs & self._dependents(cell):
                raise ValueError("cycle")
        elif isinstance(content, bool) or not isinstance(content, (int, float)):
            raise ValueError("bad content")
        for p in self._parents.pop(cell, ()):
            kids = self._children.get(p)
            if kids is not None:
                kids.discard(cell)
                if not kids:
                    del self._children[p]
        if ast is None:
            self._formula.pop(cell, None)
            self._value[cell] = content
        else:
            self._formula[cell] = ast
            self._parents[cell] = refs
            for p in refs:
                self._children.setdefault(p, set()).add(cell)
        for c in self._topo(cell):
            f = self._formula.get(c)
            if f is not None:
                self._value[c] = self._eval(f)
                self.evaluations += 1

    def get(self, cell):
        if not isinstance(cell, str) or not _CELL.match(cell):
            raise ValueError("bad cell name")
        return self._value.get(cell, 0)
