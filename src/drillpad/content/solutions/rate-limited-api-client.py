# ruff: noqa
class ApiError(Exception):
    pass


def fetch_all(call, sleep, max_retries=5, base_delay=1, max_delay=30):
    results = []
    seen_ids = set()
    requested = set()
    cursor = None
    while True:
        requested.add(cursor)
        failures = 0
        while True:
            status, body = call(cursor)
            if status == 200:
                break
            if status == 429 or 500 <= status <= 599:
                failures += 1
                if failures > max_retries:
                    raise ApiError("too many failures")
                delay = None
                if status == 429 and isinstance(body, dict):
                    ra = body.get("retry_after")
                    if type(ra) is int and ra >= 0:
                        delay = ra
                if delay is None:
                    delay = min(max_delay, base_delay * 2 ** (failures - 1))
                sleep(delay)
                continue
            raise ApiError("permanent error %s" % status)
        for item in body["items"]:
            if item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                results.append(item)
        nxt = body["next"]
        if nxt is None:
            return results
        if nxt in requested:
            raise ApiError("cursor loop")
        cursor = nxt
