"""Fixed vocabularies shared by problem packs, firm profiles, and the evaluator."""

# Edge-case categories a test can be tagged with. A miss in a category feeds the edge-case map.
EDGE_TAGS = {
    "empty": "empty / zero-element input or state",
    "single": "exactly one element",
    "boundary": "off-by-one, capacity/size boundary, first/last index",
    "duplicate": "repeated keys/values, re-insertion, update-in-place",
    "invalid": "out-of-range, negative, wrong-type, missing key",
    "zero-capacity": "capacity/limit of 0 or 1",
    "scale": "large input where complexity matters",
    "ordering": "order/recency/FIFO/priority semantics",
    "state-reuse": "behaviour after clear/evict/reset/reuse",
    "concurrency": "threads, races, blocking, shutdown",
    "time": "clock, expiry, window, refill semantics",
}

# Rubric dimensions scored for every attempt.
DIMENSIONS = ["correctness", "edge_cases", "complexity", "pace", "communication", "extensions", "quality"]
