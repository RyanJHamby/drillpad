# ruff: noqa
from collections import deque, defaultdict

def ladder_length(begin_word, end_word, word_list):
    words = set(word_list)
    if end_word not in words:
        return 0
    buckets = defaultdict(list)
    for w in words:
        for i in range(len(w)):
            buckets[w[:i] + "*" + w[i+1:]].append(w)
    q = deque([(begin_word, 1)])
    seen = {begin_word}
    while q:
        w, d = q.popleft()
        if w == end_word:
            return d
        for i in range(len(w)):
            key = w[:i] + "*" + w[i+1:]
            for nxt in buckets.get(key, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append((nxt, d + 1))
            buckets[key] = []
    return 0
