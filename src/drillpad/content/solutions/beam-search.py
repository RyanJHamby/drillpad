# ruff: noqa
import heapq


def beam_search(step_fn, beam_width, max_len, eos):
    if beam_width < 1 or max_len < 0:
        raise ValueError("bad parameters")
    beams = [((), 0.0)]
    for _ in range(max_len):
        if all(t and t[-1] == eos for t, _ in beams):
            break
        cands = []
        for toks, score in beams:
            if toks and toks[-1] == eos:
                cands.append((toks, score, None))
                continue
            for tok, lp in step_fn(toks):
                cands.append((toks, score + lp, tok))
        best = heapq.nsmallest(beam_width, cands, key=lambda c: -c[1])
        beams = [(t if tok is None else t + (tok,), s) for t, s, tok in best]
    return beams
