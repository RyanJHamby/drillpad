"""Build a static, read-and-score copy of the open course for free hosting (GitHub Pages / Cloudflare Pages).

Run from a checkout that contains only public content. The private overlay is excluded by pointing
DRILLPAD_DATA_DIR at an empty temp dir; the script then refuses to continue if any module is flagged private.

    python scripts/build_static.py --dest dist-site [--base-path /drillpad/]
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "src" / "drillpad" / "web" / "static"
SITE = Path(__file__).resolve().parent / "static_site"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", required=True)
    args = ap.parse_args()
    dest = Path(args.dest).resolve()
    tmp = tempfile.mkdtemp(prefix="drillpad-static-")
    os.environ["DRILLPAD_DATA_DIR"] = tmp
    os.environ["DRILLPAD_PRIVATE_DIR"] = str(Path(tmp) / "private")
    os.environ["DRILLPAD_DB"] = str(Path(tmp) / "build.db")
    sys.path.insert(0, str(ROOT / "src"))
    from fastapi.testclient import TestClient

    from drillpad.web.app import create_app

    c = TestClient(create_app(db_path=Path(tmp) / "build.db"))
    mods = c.get("/api/modules").json()
    curs = c.get("/api/curricula").json()
    if any(m.get("private") for m in mods) or any(x["id"] == "private" or x.get("source") == "private" for x in curs):
        print("refusing to build: private content detected", file=sys.stderr)
        return 1

    if dest.exists():
        shutil.rmtree(dest)
    (dest / "data" / "lessons").mkdir(parents=True)
    (dest / "static").mkdir()
    shutil.copytree(STATIC / "vendor", dest / "static" / "vendor")
    shutil.copytree(STATIC / "icons", dest / "static" / "icons")
    n = 0
    for m in mods:
        for les in m["lessons"]:
            r = c.get(f"/api/modules/{m['id']}/{les['id']}")
            if r.status_code == 200:
                (dest / "data" / "lessons" / f"{m['id']}__{les['id']}.json").write_text(json.dumps(r.json()))
                n += 1
    (dest / "data" / "modules.json").write_text(json.dumps(mods))
    (dest / "data" / "curricula.json").write_text(json.dumps(curs))

    html = (STATIC / "learn.html").read_text()
    html = re.sub(r'(<meta name="viewport"[^>]*>)', r'\1<script src="shim.js"></script>', html, count=1)
    html = html.replace('href="/static/', 'href="static/').replace('src="/static/', 'src="static/')
    html = html.replace('href="/static/manifest.webmanifest"', 'href="manifest.webmanifest"')
    html = html.replace('href="/home"', 'href="./"')
    html = html.replace("</body>", "<script>if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js')</script></body>")
    (dest / "index.html").write_text(html)
    (dest / ".nojekyll").write_text("")
    shutil.copy(SITE / "shim.js", dest / "shim.js")
    sw = (SITE / "sw.js").read_text().replace("__BUILD__", str(int(os.path.getmtime(dest / "index.html"))))
    (dest / "sw.js").write_text(sw)
    man = json.loads((STATIC / "manifest.webmanifest").read_text())
    man.update(start_url="./", scope="./")
    for i in man["icons"]:
        i["src"] = i["src"].removeprefix("/")
    (dest / "manifest.webmanifest").write_text(json.dumps(man, indent=2))
    shutil.copy(STATIC / "icons" / "apple-touch-icon.png", dest / "apple-touch-icon.png")
    print(f"built {dest}: {len(mods)} modules, {n} lessons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
