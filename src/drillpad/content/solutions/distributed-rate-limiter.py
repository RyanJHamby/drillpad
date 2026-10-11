# ruff: noqa
# Reference solution copied from the interview-prep markdown (see tests/test_packs.py).
# --- What's real vs. mocked ---
# Real: the Lua script logic and the overall protocol (fixed-window counter
# backed by shared state) — this is exactly what you'd ship against real Redis.
# Mocked: FakeRedis below only implements INCR/EXPIRE/EVAL enough to demonstrate
# atomicity; a real deployment uses redis-py + actual Redis (or a managed
# equivalent) which guarantees single-threaded command execution.

class FakeRedis:
    """Minimal stand-in: single-threaded execution model, matching Redis's
    real guarantee that one command (or one Lua script) runs to completion
    before the next command starts — this is what makes atomicity free."""
    def __init__(self):
        self.store = {}  # key -> [count, expire_at]

    def eval_incr_with_expire(self, key, window_sec, now):
        # This whole block is what a Lua script does atomically in real Redis.
        entry = self.store.get(key)
        if entry is None or entry[1] <= now:
            self.store[key] = [1, now + window_sec]
            return 1
        entry[0] += 1
        return entry[0]


# The unsafe version (DO NOT DO THIS) — three separate round trips:
#   count = redis.get(key)              # <-- another server can interleave here
#   if count is None: redis.set(key, 0, ex=window_sec)
#   count = redis.incr(key)
# Between GET and INCR, two concurrent requests can both read count=9 (limit=10),
# both decide "allowed", both INCR -> actual count becomes 11. Classic
# check-then-act race, worse the more app servers you have.

# The safe version: push the whole check-and-increment into ONE atomic
# operation, either a single INCR+EXPIRE via a Lua script (guaranteed atomic
# in real Redis since scripts run without interleaving) or Redis's native
# INCR (which is itself atomic) combined with EXPIRE NX (also atomic, one op).

LUA_FIXED_WINDOW = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, window)
end
if count > limit then
    return 0
end
return 1
"""

def is_allowed(fake_redis, key, limit, window_sec, now):
    count = fake_redis.eval_incr_with_expire(key, window_sec, now)
    return count <= limit
