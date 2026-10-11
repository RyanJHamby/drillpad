import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="drillpad")
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="run the local web UI (binds 127.0.0.1 only)")
    serve.add_argument("--port", type=int, default=8765)
    sub.add_parser("paths", help="print where your data, backups, and private overlay live")
    sub.add_parser("backup", help="take a consistent snapshot of the database now")
    sub.add_parser("curricula", help="list curricula, where they load from, and how much of each is written")
    svc = sub.add_parser("service", help="macOS login item so the UI runs without a terminal")
    svc.add_argument("action", choices=["install", "status", "uninstall"])
    args = parser.parse_args()

    if args.cmd == "serve":
        import uvicorn

        from drillpad.core import paths
        from drillpad.web.app import create_app
        from drillpad.web.backup import start_periodic_backup

        db_file = paths.db_path()
        print(f"drillpad: database {db_file}", file=sys.stderr, flush=True)
        app = create_app()
        start_periodic_backup(db_file)
        uvicorn.run(app, host="127.0.0.1", port=args.port)
    elif args.cmd == "paths":
        from drillpad.core import paths

        print(f"data dir:     {paths.data_dir()}\ndatabase:     {paths.db_path()}\n"
              f"backups:      {paths.backup_dir(paths.db_path())}\nprivate dir:  {paths.private_dir()}\n"
              f"offsite copy: {paths.offsite_backup_dir() or '(DRILLPAD_BACKUP_DIR not set)'}")
    elif args.cmd == "backup":
        from drillpad.core import paths
        from drillpad.web.backup import backup_database

        dest = backup_database(paths.db_path())
        print(f"backup written: {dest}" if dest else "nothing new to back up")
    elif args.cmd == "curricula":
        from drillpad.core import curricula as cur
        from drillpad.web.modules import _load_all

        _mods, found = _load_all()
        for c in found.values():
            ready = sum(1 for u in c.units() if u.status == "ready")
            planned = sum(1 for u in c.units() if u.status == "planned")
            where = f" [{c.root}]" if c.root else ""
            print(f"{c.id:<22} {c.title}  ({c.source}; {ready} ready, {planned} planned){where}")
        print("\nroots searched:", ", ".join(f"{s}={p}" for s, p in cur.roots()))
    elif args.cmd == "service":
        from drillpad import service

        root = Path(__file__).resolve().parent.parent.parent
        project = root if (root / "pyproject.toml").exists() else None  # None: an installed tool, not a source checkout
        raise SystemExit({"install": lambda: service.install(project), "status": service.status,
                          "uninstall": service.uninstall}[args.action]())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
