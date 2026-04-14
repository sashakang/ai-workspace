#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = PLUGIN_ROOT / "contracts" / "data-analysis-aiws.contract.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_compact_json_atomic(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stage-shared-memory-candidate")
    parser.add_argument("--plugin-data", type=Path, default=Path(os.environ.get("CLAUDE_PLUGIN_DATA", "")) if os.environ.get("CLAUDE_PLUGIN_DATA") else None)
    parser.add_argument("--category", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--confidence", type=float, required=True)
    parser.add_argument("--source-project")
    parser.add_argument("--candidate-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.plugin_data is None:
        parser.error("Provide --plugin-data or set CLAUDE_PLUGIN_DATA.")

    contract = load_contract()
    if args.scope not in contract.get("shared_memory_write_scope", []):
        parser.error(f"Scope {args.scope} is outside data-analysis-aiws shared_memory_write_scope.")
    if args.confidence < 0.0:
        parser.error("confidence must be >= 0.0")

    outbox_root = args.plugin_data / "shared-memory" / "outbox"
    if not outbox_root.exists():
        parser.error(
            f"Outbox path is unavailable at {outbox_root}. Run `aiws-host-memory bootstrap` first."
        )

    candidate = {
        "candidate_id": args.candidate_id or uuid.uuid4().hex,
        "ts": utc_now_iso(),
        "plugin_id": contract["plugin_id"],
        "category": args.category,
        "scope": args.scope,
        "summary": args.summary,
        "evidence": args.evidence,
        "confidence": args.confidence,
    }
    if args.source_project:
        candidate["source_project"] = args.source_project

    filename = f"{candidate['ts'].replace(':', '').replace('-', '')}--{candidate['candidate_id']}.json"
    target = outbox_root / filename
    if target.exists():
        parser.error(f"Candidate file already exists: {target}")
    write_compact_json_atomic(target, candidate)
    print(json.dumps({"candidate": candidate, "outbox_file": str(target)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
