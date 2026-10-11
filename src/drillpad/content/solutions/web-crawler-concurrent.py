# ruff: noqa
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.parse import urlparse


def crawl(start_url, fetch, max_workers=4):
    host = urlparse(start_url).netloc
    seen = {start_url}          # only the coordinating thread touches these structures
    ok = set()
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        pending = {pool.submit(fetch, start_url): start_url}
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for fut in done:
                url = pending.pop(fut)
                try:
                    links = fut.result()
                except Exception:
                    continue
                ok.add(url)
                for link in links:
                    if link not in seen and urlparse(link).netloc == host:
                        seen.add(link)
                        pending[pool.submit(fetch, link)] = link
    return ok
