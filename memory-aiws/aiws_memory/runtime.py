from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

PLUGIN_ID = "memory-aiws"
GLOBAL_SCOPE_PATHS = {
    "global.user-preferences": Path("global/user-preferences.md"),
    "global.tool-quirks": Path("global/tool-quirks.md"),
    "global.workflow-patterns": Path("global/workflow-patterns.md"),
    "global.prompt-improvement-patterns": Path("global/prompt-improvement-patterns.md"),
}


class LeaseBusyError(RuntimeError):
    """Raised when a live lease already exists."""


class LostLeaseError(RuntimeError):
    """Raised when the caller no longer owns the lease."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_text_atomic(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_compact_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, sort_keys=True) + "\n")


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    write_text_atomic(path, content)


def atomic_symlink(link_path: Path, target_path: Path) -> None:
    ensure_dir(link_path.parent)
    temp_link = link_path.parent / f".{link_path.name}.tmp.{uuid.uuid4().hex}"
    if temp_link.exists() or temp_link.is_symlink():
        temp_link.unlink()
    relative_target = os.path.relpath(target_path, start=link_path.parent)
    os.symlink(relative_target, temp_link)
    os.replace(temp_link, link_path)


def temp_dir(parent: Path, prefix: str) -> Path:
    ensure_dir(parent)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=parent))


def scope_to_target(scope: str) -> Path:
    if scope in GLOBAL_SCOPE_PATHS:
        return GLOBAL_SCOPE_PATHS[scope]
    if scope.startswith("domains."):
        domain_name = scope.split(".", 1)[1]
        return Path("domains") / domain_name / "README.md"
    raise ValueError(f"Unsupported scope: {scope}")


def seed_memory_tree(seed_root: Path, output_root: Path) -> None:
    shutil.copytree(seed_root, output_root, dirs_exist_ok=True)


def format_entries(entries: list[dict[str, Any]]) -> str:
    lines = ["", "## Captured Entries", ""]
    for entry in sorted(entries, key=lambda item: item["ts"]):
        lines.extend(
            [
                f"### {entry['summary']}",
                f"- `entry_id`: `{entry['entry_id']}`",
                f"- `source_plugin_id`: `{entry['source_plugin_id']}`",
                f"- `category`: `{entry['category']}`",
                f"- `confidence`: `{entry['confidence']}`",
                f"- `ts`: `{entry['ts']}`",
                f"- `evidence`: {entry['evidence']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def rebuild_index(memory_root: Path) -> None:
    global_files = sorted((memory_root / "global").glob("*.md")) if (memory_root / "global").exists() else []
    domain_readmes = sorted((memory_root / "domains").glob("*/README.md")) if (memory_root / "domains").exists() else []
    lines = ["# Shared Memory Index", "", "This file is the top-level index for `memory-aiws`.", ""]
    if global_files:
        lines.extend(["## Global memory", ""])
        for path in global_files:
            lines.append(f"- [{path.stem}](./global/{path.name})")
        lines.append("")
    if domain_readmes:
        lines.extend(["## Domain memory", ""])
        for path in domain_readmes:
            lines.append(f"- [{path.parent.name}](./domains/{path.parent.name}/README.md)")
        lines.append("")
    write_text_atomic(memory_root / "MEMORY.md", "\n".join(lines).rstrip() + "\n")


def build_render_snapshot(
    plugin_data: Path,
    seed_root: Path,
    entries: list[dict[str, Any]],
    version: str,
) -> Path:
    snapshots_root = ensure_dir(plugin_data / "shared-memory-versions")
    snapshot_root = snapshots_root / version
    working_root = temp_dir(snapshots_root, prefix="shared-memory.")
    seed_memory_tree(seed_root, working_root)

    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        grouped.setdefault(entry["scope"], []).append(entry)

    for scope, scope_entries in grouped.items():
        target = working_root / scope_to_target(scope)
        ensure_dir(target.parent)
        if not target.exists():
            write_text_atomic(target, f"# {scope}\n")
        content = target.read_text().rstrip() + "\n"
        content += format_entries(scope_entries)
        write_text_atomic(target, content)

    rebuild_index(working_root)
    os.replace(working_root, snapshot_root)
    return snapshot_root


def build_export_snapshot(
    plugin_data: Path,
    version: str,
    rendered_root: Path,
    entries: list[dict[str, Any]],
    processed_candidate_ids: list[str],
) -> dict[str, Any]:
    exports_root = ensure_dir(plugin_data / "exports" / "versions")
    export_root = exports_root / version
    working_root = temp_dir(exports_root, prefix="export.")
    rendered_output = working_root / "rendered"
    shutil.copytree(rendered_root, rendered_output, dirs_exist_ok=True)
    metadata = {
        "snapshot_version": version,
        "generated_ts": utc_now_iso(),
        "source_plugin_id": PLUGIN_ID,
        "included_paths": sorted(
            str(path.relative_to(rendered_output))
            for path in rendered_output.rglob("*")
            if path.is_file()
        ),
        "committed_candidate_ids": processed_candidate_ids,
    }
    write_json_atomic(working_root / "metadata.json", metadata)
    write_json_atomic(working_root / "entries.json", entries)
    os.replace(working_root, export_root)
    latest_link = plugin_data / "exports" / "latest"
    atomic_symlink(latest_link, export_root)
    return metadata


def canonical_paths(plugin_data: Path) -> dict[str, Path]:
    return {
        "store_dir": ensure_dir(plugin_data / "store"),
        "state_dir": ensure_dir(plugin_data / "state"),
        "shared_memory_link": plugin_data / "shared-memory",
        "shared_memory_versions": ensure_dir(plugin_data / "shared-memory-versions"),
        "exports_dir": ensure_dir(plugin_data / "exports"),
        "quarantine_dir": ensure_dir(plugin_data / "quarantine"),
    }


def bootstrap_canonical(plugin_data: Path, seed_root: Path) -> dict[str, Any]:
    paths = canonical_paths(plugin_data)
    entries_path = paths["store_dir"] / "entries.json"
    events_path = paths["store_dir"] / "events.jsonl"
    processed_path = paths["state_dir"] / "processed-candidate-ids.jsonl"
    if not entries_path.exists():
        write_json_atomic(entries_path, [])
    if not events_path.exists():
        write_jsonl_atomic(events_path, [])
    if not processed_path.exists():
        write_jsonl_atomic(processed_path, [])

    entries = load_json(entries_path, [])
    processed_rows = read_jsonl(processed_path)
    processed_ids = [row["candidate_id"] for row in processed_rows]
    version = utc_now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    rendered_root = build_render_snapshot(plugin_data, seed_root, entries, version)
    atomic_symlink(paths["shared_memory_link"], rendered_root)
    metadata = build_export_snapshot(plugin_data, version, rendered_root, entries, processed_ids)
    return {
        "entries": len(entries),
        "processed_candidate_ids": len(processed_ids),
        "snapshot_version": metadata["snapshot_version"],
    }


def consolidate_candidates(
    plugin_data: Path,
    seed_root: Path,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    paths = canonical_paths(plugin_data)
    entries_path = paths["store_dir"] / "entries.json"
    events_path = paths["store_dir"] / "events.jsonl"
    processed_path = paths["state_dir"] / "processed-candidate-ids.jsonl"
    entries = load_json(entries_path, [])
    events = read_jsonl(events_path)
    processed_rows = read_jsonl(processed_path)

    processed_ids = {row["candidate_id"] for row in processed_rows}
    committed_ids = sorted(processed_ids)
    accepted = []
    for candidate in candidates:
        if candidate["candidate_id"] in processed_ids:
            continue
        entry = {
            "entry_id": candidate["candidate_id"],
            "candidate_id": candidate["candidate_id"],
            "source_plugin_id": candidate["plugin_id"],
            "scope": candidate["scope"],
            "category": candidate["category"],
            "summary": candidate["summary"],
            "evidence": candidate["evidence"],
            "confidence": candidate["confidence"],
            "ts": candidate["ts"],
            "source_project": candidate.get("source_project"),
        }
        entries.append(entry)
        events.append(candidate)
        processed_rows.append(
            {
                "candidate_id": candidate["candidate_id"],
                "committed_ts": utc_now_iso(),
                "entry_id": candidate["candidate_id"],
                "source_plugin_id": candidate["plugin_id"],
            }
        )
        processed_ids.add(candidate["candidate_id"])
        accepted.append(entry)

    committed_ids = sorted(processed_ids)
    write_json_atomic(entries_path, entries)
    write_jsonl_atomic(events_path, events)
    write_jsonl_atomic(processed_path, processed_rows)

    version = utc_now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    rendered_root = build_render_snapshot(plugin_data, seed_root, entries, version)
    atomic_symlink(paths["shared_memory_link"], rendered_root)
    metadata = build_export_snapshot(plugin_data, version, rendered_root, entries, committed_ids)

    return {
        "accepted_candidates": len(accepted),
        "entry_count": len(entries),
        "processed_candidate_ids": len(committed_ids),
        "snapshot_version": metadata["snapshot_version"],
        "metadata": metadata,
    }


def inspect_runtime(plugin_data: Path, stale_after_days: int = 180) -> dict[str, Any]:
    paths = canonical_paths(plugin_data)
    entries = load_json(paths["store_dir"] / "entries.json", [])
    processed_rows = read_jsonl(paths["state_dir"] / "processed-candidate-ids.jsonl")
    quarantine_files = sorted(paths["quarantine_dir"].glob("*.json"))
    latest_metadata = load_json(plugin_data / "exports" / "latest" / "metadata.json", {})
    stale_before = utc_now() - timedelta(days=stale_after_days)
    stale_entries = [
        entry["entry_id"]
        for entry in entries
        if parse_ts(entry["ts"]) < stale_before
    ]
    return {
        "entry_count": len(entries),
        "processed_candidate_count": len(processed_rows),
        "quarantine_count": len(quarantine_files),
        "snapshot_version": latest_metadata.get("snapshot_version"),
        "generated_ts": latest_metadata.get("generated_ts"),
        "stale_entries": stale_entries,
    }


@dataclass
class Lease:
    lock_path: Path
    owner_id: str
    lease_generation: int

    def heartbeat(self) -> None:
        payload = load_json(self.lock_path, {})
        if payload.get("owner_id") != self.owner_id or payload.get("lease_generation") != self.lease_generation:
            raise LostLeaseError("Lease ownership changed before heartbeat.")
        payload["last_heartbeat_ts"] = utc_now_iso()
        write_json_atomic(self.lock_path, payload)

    def assert_owned(self) -> None:
        payload = load_json(self.lock_path, {})
        if payload.get("owner_id") != self.owner_id or payload.get("lease_generation") != self.lease_generation:
            raise LostLeaseError("Lease ownership lost.")

    def release(self) -> None:
        if self.lock_path.exists():
            payload = load_json(self.lock_path, {})
            if payload.get("owner_id") == self.owner_id and payload.get("lease_generation") == self.lease_generation:
                self.lock_path.unlink()


def acquire_lease(lock_path: Path, stale_after_seconds: int = 60) -> Lease:
    ensure_dir(lock_path.parent)
    owner_id = uuid.uuid4().hex
    guard_path = lock_path.with_suffix(lock_path.suffix + ".guard")

    for _ in range(100):
        try:
            os.mkdir(guard_path)
            break
        except FileExistsError:
            try:
                guard_age = utc_now().timestamp() - guard_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if guard_age > stale_after_seconds:
                shutil.rmtree(guard_path, ignore_errors=True)
                continue
            time.sleep(0.01)
    else:
        raise LeaseBusyError("Timed out waiting to acquire the lease guard.")

    try:
        now = utc_now()
        generation = 0
        if lock_path.exists():
            payload = load_json(lock_path, {})
            last_heartbeat = parse_ts(payload["last_heartbeat_ts"])
            age_seconds = (now - last_heartbeat).total_seconds()
            if age_seconds <= stale_after_seconds:
                raise LeaseBusyError(f"Lease is still active for owner {payload['owner_id']}.")
            generation = int(payload["lease_generation"]) + 1

        payload = {
            "owner_id": owner_id,
            "lease_generation": generation,
            "acquired_ts": utc_now_iso(),
            "last_heartbeat_ts": utc_now_iso(),
        }
        write_json_atomic(lock_path, payload)
        return Lease(lock_path=lock_path, owner_id=owner_id, lease_generation=generation)
    finally:
        os.rmdir(guard_path)
