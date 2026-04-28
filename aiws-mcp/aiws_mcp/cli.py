from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import AiwsRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiws-mcp")
    parser.add_argument("--root", type=Path, help="AIWS runtime root. Defaults to ~/.aiws.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("serve")

    search = subparsers.add_parser("search")
    search.add_argument("query", nargs="?")
    search.add_argument("--host-kind")
    search.add_argument("--limit", type=int)

    materialize = subparsers.add_parser("materialize")
    materialize.add_argument("skill_id")
    materialize.add_argument("--host-kind")
    materialize.add_argument("--host-id")
    materialize.add_argument("--scope")
    materialize.add_argument("--version")

    subparsers.add_parser("list-local")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "serve":
        from .server import create_server

        server = create_server(root=args.root)
        server.run()
        return 0

    runtime = AiwsRuntime(root=args.root)
    if args.command == "search":
        result = runtime.search_skills(query=args.query, host_kind=args.host_kind, limit=args.limit)
    elif args.command == "materialize":
        result = runtime.materialize_skill(
            skill_id=args.skill_id,
            host_kind=args.host_kind,
            host_id=args.host_id,
            scope=args.scope,
            version=args.version,
        )
    else:
        result = runtime.list_local_skills()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
