# ruff: noqa
import heapq
import math


def candidates(logits, temperature=1.0, top_k=0, top_p=1.0):
    if not logits:
        raise ValueError("empty logits")
    if temperature < 0 or top_k < 0 or not (0 < top_p <= 1):
        raise ValueError("bad parameter")
    n = len(logits)
    if temperature == 0:
        best = max(range(n), key=lambda i: (logits[i], -i))
        return [(best, 1.0)]
    if top_k and top_k < n:
        idx = heapq.nlargest(top_k, range(n), key=lambda i: logits[i])
    else:
        idx = sorted(range(n), key=lambda i: -logits[i])
    scaled = [logits[i] / temperature for i in idx]
    m = max(scaled)
    es = [math.exp(x - m) for x in scaled]
    total = sum(es)
    probs = [e / total for e in es]
    if top_p < 1.0:
        cum, keep = 0.0, 0
        for p in probs:
            cum += p
            keep += 1
            if cum >= top_p:
                break
        idx, probs = idx[:keep], probs[:keep]
        s = sum(probs)
        probs = [p / s for p in probs]
    return list(zip(idx, probs))


def sample(logits, rng, temperature=1.0, top_k=0, top_p=1.0):
    cands = candidates(logits, temperature, top_k, top_p)
    u = rng.random()
    cum = 0.0
    for idx, p in cands:
        cum += p
        if u < cum:
            return idx
    return cands[-1][0]
