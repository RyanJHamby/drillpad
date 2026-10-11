# ruff: noqa
def evaluate(expr):
    tokens = _tokenize(expr)
    pos = [0]

    def peek():
        return tokens[pos[0]] if pos[0] < len(tokens) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def parse_expr():
        value = parse_term()
        while peek() in ("+", "-"):
            op = take()
            rhs = parse_term()
            value = value + rhs if op == "+" else value - rhs
        return value

    def parse_term():
        value = parse_factor()
        while peek() in ("*", "/"):
            op = take()
            rhs = parse_factor()
            value = value * rhs if op == "*" else value / rhs
        return value

    def parse_factor():
        t = take()
        if t is None:
            raise ValueError("unexpected end")
        if t in ("+", "-"):
            v = parse_factor()
            return v if t == "+" else -v
        if t == "(":
            v = parse_expr()
            if take() != ")":
                raise ValueError("expected )")
            return v
        if isinstance(t, (int, float)):
            return t
        raise ValueError("unexpected token %r" % (t,))

    value = parse_expr()
    if pos[0] != len(tokens):
        raise ValueError("trailing input")
    return value


def _tokenize(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
        elif c in "+-*/()":
            out.append(c)
            i += 1
        elif c.isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ".":
                k = j + 1
                while k < len(s) and s[k].isdigit():
                    k += 1
                if k == j + 1:
                    raise ValueError("digits expected after '.'")
                out.append(float(s[i:k]))
                i = k
            else:
                out.append(int(s[i:j]))
                i = j
        else:
            raise ValueError("bad character %r" % c)
    if not out:
        raise ValueError("empty expression")
    return out
