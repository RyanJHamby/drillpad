# ruff: noqa
def multiply(num1, num2):
    if num1 == '0' or num2 == '0':
        return '0'
    n, m = len(num1), len(num2)
    res = [0] * (n + m)
    for i in range(n - 1, -1, -1):
        a = ord(num1[i]) - 48
        for j in range(m - 1, -1, -1):
            cur = res[i + j + 1] + a * (ord(num2[j]) - 48)
            res[i + j + 1] = cur % 10
            res[i + j] += cur // 10
    s = ''.join(map(str, res)).lstrip('0')
    return s or '0'
