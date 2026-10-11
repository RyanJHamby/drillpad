# ruff: noqa
import math

NEG_INF = float("-inf")


def softmax(xs):
    if not xs:
        return []
    m = max(xs)
    if m == NEG_INF:
        raise ValueError("all entries are -inf")
    es = [math.exp(x - m) for x in xs]
    total = sum(es)
    return [e / total for e in es]


def attention(Q, K, V, causal=False):
    n, m = len(Q), len(K)
    if len(V) != m:
        raise ValueError("K and V must have the same length")
    if n == 0:
        return []
    if m == 0:
        raise ValueError("no keys")
    d = len(Q[0])
    if any(len(q) != d for q in Q) or any(len(k) != d for k in K):
        raise ValueError("dimension mismatch")
    if causal and n != m:
        raise ValueError("causal needs n == m")
    scale = 1.0 / math.sqrt(d) if d else 1.0
    out = []
    for i, q in enumerate(Q):
        keys = K[: i + 1] if causal else K
        scores = [sum(a * b for a, b in zip(q, k)) * scale for k in keys]
        w = softmax(scores)
        dv = len(V[0])
        row = [0.0] * dv
        for wj, vj in zip(w, V):
            for t in range(dv):
                row[t] += wj * vj[t]
        out.append(row)
    return out
