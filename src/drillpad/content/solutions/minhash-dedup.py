# ruff: noqa
import hashlib
import random

P = (1 << 61) - 1


def shingles(text, k=3):
    if k < 1:
        raise ValueError("k")
    words = text.split()
    if not words:
        return set()
    if len(words) < k:
        return {" ".join(words)}
    return {" ".join(words[i:i + k]) for i in range(len(words) - k + 1)}


def _base(s):
    return int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")


def _params(num_perm, seed):
    rng = random.Random(seed)
    out = []
    for _ in range(num_perm):
        a = rng.randrange(1, P)
        b = rng.randrange(0, P)
        out.append((a, b))
    return out


def _signature(hs, params):
    if not hs:
        return [P] * len(params)
    return [min((a * h + b) % P for h in hs) for a, b in params]


def minhash_signature(shingle_set, num_perm=64, seed=0):
    if num_perm < 1:
        raise ValueError("num_perm")
    return _signature([_base(s) for s in shingle_set], _params(num_perm, seed))


def estimate_jaccard(sig_a, sig_b):
    if len(sig_a) != len(sig_b) or not sig_a:
        raise ValueError("signature length mismatch")
    return sum(x == y for x, y in zip(sig_a, sig_b)) / len(sig_a)


def near_duplicates(docs, k=3, num_perm=64, bands=16, threshold=0.5, seed=0):
    if bands < 1 or num_perm % bands:
        raise ValueError("bands must divide num_perm")
    rows = num_perm // bands
    params = _params(num_perm, seed)
    sigs = {}
    for i, text in enumerate(docs):
        sh = shingles(text, k)
        if sh:
            sigs[i] = _signature([_base(s) for s in sh], params)
    buckets = {}
    for i, sig in sigs.items():
        for b in range(bands):
            buckets.setdefault((b, tuple(sig[b * rows:(b + 1) * rows])), []).append(i)
    cands = set()
    for members in buckets.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                cands.add((members[x], members[y]))
    return sorted(p for p in cands if estimate_jaccard(sigs[p[0]], sigs[p[1]]) >= threshold)
