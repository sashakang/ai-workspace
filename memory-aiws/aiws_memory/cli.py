from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import bootstrap_canonical, consolidate_candidates, inspect_runtime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiws-memory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap-canonical")
    bootstrap.add_argument("--plugin-data", type=Path, required=True)
    bootstrap.add_argument("--seed-root", type=Path, required=True)

    consolidate = subparsers.add_parser("consolidate")
    consolidate.add_argument("--plugin-data", type=Path, required=True)
    consolidate.add_argument("--seed-root", type=Path, required=True)
    consolidate.add_argument("--candidates-file", type=Path, required=True)

    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("--plugin-data", type=Path, required=True)
    inspect.add_argument("--json", action="store_true", dest="as_json")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "bootstrap-canonical":
        result = bootstrap_canonical(args.plugin_data, args.seed_root)
    elif args.command == "consolidate":
        candidates = [
            json.loads(line)
            for line in args.candidates_file.read_text().splitlines()
            if line.strip()
        ]
        result = consolidate_candidates(args.plugin_data, args.seed_root, candidates)
    else:
        result = inspect_runtime(args.plugin_data)

    if getattr(args, "as_json", False) or args.command != "inspect":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0
