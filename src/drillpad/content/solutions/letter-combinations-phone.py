# ruff: noqa
def letter_combinations(digits):
    if not digits:
        return []
    m = {"2": "abc", "3": "def", "4": "ghi", "5": "jkl",
         "6": "mno", "7": "pqrs", "8": "tuv", "9": "wxyz"}
    res = []
    def go(i, cur):
        if i == len(digits):
            res.append("".join(cur))
            return
        for ch in m[digits[i]]:
            cur.append(ch)
            go(i + 1, cur)
            cur.pop()
    go(0, [])
    return res
