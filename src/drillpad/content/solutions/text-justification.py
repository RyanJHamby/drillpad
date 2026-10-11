# ruff: noqa
def full_justify(words, max_width):
    lines = []
    i, n = 0, len(words)
    while i < n:
        j, length = i, 0
        while j < n and length + len(words[j]) + (j - i) <= max_width:
            length += len(words[j])
            j += 1
        line_words = words[i:j]
        gaps = j - i - 1
        if j == n or gaps == 0:
            line = " ".join(line_words)
            line += " " * (max_width - len(line))
        else:
            spaces = max_width - length
            base, extra = divmod(spaces, gaps)
            parts = []
            for k, w in enumerate(line_words[:-1]):
                parts.append(w)
                parts.append(" " * (base + (1 if k < extra else 0)))
            parts.append(line_words[-1])
            line = "".join(parts)
        lines.append(line)
        i = j
    return lines
