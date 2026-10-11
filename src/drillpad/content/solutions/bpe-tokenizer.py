# ruff: noqa
from collections import Counter


def _merge_word(word, pair, merged):
    out, i = [], 0
    while i < len(word):
        if i + 1 < len(word) and word[i] == pair[0] and word[i + 1] == pair[1]:
            out.append(merged)
            i += 2
        else:
            out.append(word[i])
            i += 1
    return tuple(out)


def train_bpe(text, num_merges):
    words = Counter(tuple(w) for w in text.split())
    merges = []
    for _ in range(num_merges):
        pairs = Counter()
        for w, f in words.items():
            for a, b in zip(w, w[1:]):
                pairs[(a, b)] += f
        if not pairs:
            break
        best = min(pairs, key=lambda p: (-pairs[p], p))
        merges.append(best)
        merged = best[0] + best[1]
        words = _apply(words, best, merged)
    return merges


def _apply(words, pair, merged):
    out = Counter()
    for w, f in words.items():
        out[_merge_word(w, pair, merged)] += f
    return out


def encode_word(word, merges):
    rank = {p: i for i, p in enumerate(merges)}
    toks = list(word)
    while len(toks) > 1:
        best = min(((rank[p], p) for p in zip(toks, toks[1:]) if p in rank), default=None)
        if best is None:
            break
        pair = best[1]
        toks = list(_merge_word(toks, pair, pair[0] + pair[1]))
    return toks


def tokenize(text, merges):
    cache, out = {}, []
    for w in text.split():
        if w not in cache:
            cache[w] = encode_word(w, merges)
        out.extend(cache[w])
    return out
