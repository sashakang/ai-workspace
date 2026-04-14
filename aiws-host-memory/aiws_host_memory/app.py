from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_PLUGIN_IDS = ("core-aiws", "memory-aiws", "data-analysis-aiws")
MANAGED_HOOK_COMMAND = "aiws-host-memory refresh-shared"
MANAGED_STOP_GROUP = {
    "hooks": [
        {
            "type": "command",
            "command": MANAGED_HOOK_COMMAND,
            "async": True,
            "timeout": 120,
        }
    ]
}


class BootstrapError(RuntimeError):
    """Raised when bootstrap cannot complete safely."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def atomic_symlink(link_path: Path, target_path: Path) -> None:
    ensure_dir(link_path.parent)
    temp_link = link_path.parent / f".{link_path.name}.tmp.{uuid.uuid4().hex}"
    if temp_link.exists() or temp_link.is_symlink():
        temp_link.unlink()
    relative_target = os.path.relpath(target_path, start=link_path.parent)
    os.symlink(relative_target, temp_link)
    os.replace(temp_link, link_path)


@dataclass
class PluginInstall:
    plugin_id: str
    plugin_root: Path
    plugin_data: Path
    contract_path: Path

    def to_payload(self) -> dict[str, str]:
        return {
            "plugin_root": str(self.plugin_root),
            "plugin_data": str(self.plugin_data),
            "contract_path": str(self.contract_path),
        }


@dataclass
class HelperPaths:
    claude_home: Path
    helper_home: Path
    config_path: Path
    state_path: Path
    settings_path: Path
    installed_plugins_path: Path
    plugin_data_root: Path


def helper_paths(
    helper_home: Path | None = None,
    settings_path: Path | None = None,
    claude_home: Path | None = None,
) -> HelperPaths:
    claude_root = claude_home or Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
    helper_root = helper_home or Path(os.environ.get("AIWS_HOST_MEMORY_HOME", claude_root / "aiws-host-memory"))
    return HelperPaths(
        claude_home=claude_root,
        helper_home=helper_root,
        config_path=helper_root / "config.json",
        state_path=helper_root / "state.json",
        settings_path=settings_path or Path(os.environ.get("AIWS_HOST_MEMORY_SETTINGS_PATH", claude_root / "settings.json")),
        installed_plugins_path=claude_root / "plugins" / "installed_plugins.json",
        plugin_data_root=claude_root / "plugins" / "data",
    )


def default_contract_path(plugin_root: Path, plugin_id: str) -> Path:
    return plugin_root / "contracts" / f"{plugin_id}.contract.json"


def parse_install_from_payload(plugin_id: str, payload: dict[str, Any]) -> PluginInstall:
    return PluginInstall(
        plugin_id=plugin_id,
        plugin_root=Path(payload["plugin_root"]),
        plugin_data=Path(payload["plugin_data"]),
        contract_path=Path(payload["contract_path"]),
    )


def config_payload(paths: HelperPaths, installs: dict[str, PluginInstall]) -> dict[str, Any]:
    now = utc_now_iso()
    existing = load_json(paths.config_path, {})
    created_ts = existing.get("created_ts", now)
    return {
        "version": 1,
        "created_ts": created_ts,
        "updated_ts": now,
        "settings_path": str(paths.settings_path),
        "plugins": {
            plugin_id: install.to_payload()
            for plugin_id, install in installs.items()
        },
    }


def load_config(paths: HelperPaths) -> dict[str, Any]:
    payload = load_json(paths.config_path, {})
    if not payload:
        raise BootstrapError(
            f"Helper config not found at {paths.config_path}. Run `aiws-host-memory bootstrap` first."
        )
    return payload


def load_installs_from_config(paths: HelperPaths) -> dict[str, PluginInstall]:
    payload = load_config(paths)
    installs_payload = payload.get("plugins", {})
    installs = {
        plugin_id: parse_install_from_payload(plugin_id, plugin_payload)
        for plugin_id, plugin_payload in installs_payload.items()
    }
    missing = [plugin_id for plugin_id in REQUIRED_PLUGIN_IDS if plugin_id not in installs]
    if missing:
        raise BootstrapError(
            "Helper config is incomplete. Missing plugin installs for: " + ", ".join(sorted(missing))
        )
    return installs


def validate_contract(install: PluginInstall) -> dict[str, Any]:
    if not install.plugin_root.exists():
        raise BootstrapError(f"{install.plugin_id} root does not exist: {install.plugin_root}")
    if not install.contract_path.exists():
        raise BootstrapError(f"{install.plugin_id} contract not found: {install.contract_path}")
    contract = load_json(install.contract_path, {})
    if contract.get("plugin_id") != install.plugin_id:
        raise BootstrapError(
            f"{install.contract_path} does not describe {install.plugin_id}."
        )
    return contract


def guess_marketplace_data_dir(plugin_id: str, marketplace: str | None, data_root: Path) -> Path:
    suffix = marketplace or "ai-workspace"
    return data_root / f"{plugin_id}-{suffix}"


def detect_installs(paths: HelperPaths) -> dict[str, PluginInstall]:
    payload = load_json(paths.installed_plugins_path, {})
    plugins = payload.get("plugins", {})
    detected: dict[str, PluginInstall] = {}
    for key, installs in plugins.items():
        plugin_name, _, marketplace = key.partition("@")
        if plugin_name not in REQUIRED_PLUGIN_IDS or not installs:
            continue
        install_root = Path(installs[0]["installPath"])
        plugin_data = guess_marketplace_data_dir(plugin_name, marketplace or None, paths.plugin_data_root)
        detected[plugin_name] = PluginInstall(
            plugin_id=plugin_name,
            plugin_root=install_root,
            plugin_data=plugin_data,
            contract_path=default_contract_path(install_root, plugin_name),
        )
    return detected


def resolve_installs(args: argparse.Namespace, paths: HelperPaths) -> dict[str, PluginInstall]:
    detected = detect_installs(paths)
    installs: dict[str, PluginInstall] = {}
    explicit: dict[str, dict[str, Path | None]] = {
        "core-aiws": {
            "root": getattr(args, "core_plugin_root", None),
            "data": getattr(args, "core_plugin_data", None),
        },
        "memory-aiws": {
            "root": getattr(args, "memory_plugin_root", None),
            "data": getattr(args, "memory_plugin_data", None),
        },
        "data-analysis-aiws": {
            "root": getattr(args, "data_analysis_plugin_root", None),
            "data": getattr(args, "data_analysis_plugin_data", None),
        },
    }

    for plugin_id in REQUIRED_PLUGIN_IDS:
        candidate = detected.get(plugin_id)
        root = explicit[plugin_id]["root"] or (candidate.plugin_root if candidate else None)
        data = explicit[plugin_id]["data"] or (candidate.plugin_data if candidate else None)
        if root and data:
            installs[plugin_id] = PluginInstall(
                plugin_id=plugin_id,
                plugin_root=root,
                plugin_data=data,
                contract_path=default_contract_path(root, plugin_id),
            )

    missing = [plugin_id for plugin_id in REQUIRED_PLUGIN_IDS if plugin_id not in installs]
    if missing:
        raise BootstrapError(
            "Could not resolve plugin installs for: "
            + ", ".join(missing)
            + ". Re-run bootstrap with explicit --*-plugin-root and --*-plugin-data flags."
        )
    return installs


def helper_state(paths: HelperPaths) -> dict[str, Any]:
    return load_json(paths.state_path, {"version": 1})


def write_helper_state(paths: HelperPaths, payload: dict[str, Any]) -> None:
    ensure_dir(paths.helper_home)
    write_json_atomic(paths.state_path, payload)


def update_state(paths: HelperPaths, section: str, payload: dict[str, Any]) -> None:
    state = helper_state(paths)
    state[section] = payload
    write_helper_state(paths, state)


def compute_contract_digest(contract_path: Path) -> str:
    return hashlib.sha256(contract_path.read_bytes()).hexdigest()


def registry_root(installs: dict[str, PluginInstall]) -> Path:
    return installs["core-aiws"].plugin_data / "registry" / "plugins"


def stable_outbox_root(plugin_data: Path) -> Path:
    return ensure_dir(plugin_data / "_shared_memory_outbox")


def imports_root(plugin_data: Path) -> Path:
    return ensure_dir(plugin_data / "imports")


def shared_memory_link(plugin_data: Path) -> Path:
    return plugin_data / "shared-memory"


def populate_registry(installs: dict[str, PluginInstall]) -> list[str]:
    root = ensure_dir(registry_root(installs))
    written: list[str] = []
    for plugin_id, install in installs.items():
        contract = validate_contract(install)
        output = root / f"{plugin_id}.json"
        write_json_atomic(output, contract)
        written.append(plugin_id)
    return sorted(written)


def load_registry_contracts(installs: dict[str, PluginInstall]) -> dict[str, dict[str, Any]]:
    contracts: dict[str, dict[str, Any]] = {}
    for path in sorted(registry_root(installs).glob("*.json")):
        contract = load_json(path, {})
        if contract:
            contracts[contract["plugin_id"]] = contract
    if not contracts:
        raise BootstrapError("Registry snapshot is empty. Run `aiws-host-memory bootstrap` first.")
    return contracts


def scope_to_target(scope: str) -> Path:
    global_scope_paths = {
        "global.user-preferences": Path("global/user-preferences.md"),
        "global.tool-quirks": Path("global/tool-quirks.md"),
        "global.workflow-patterns": Path("global/workflow-patterns.md"),
        "global.prompt-improvement-patterns": Path("global/prompt-improvement-patterns.md"),
    }
    if scope in global_scope_paths:
        return global_scope_paths[scope]
    if scope.startswith("domains."):
        return Path("domains") / scope.split(".", 1)[1] / "README.md"
    raise BootstrapError(f"Unsupported shared-memory scope: {scope}")


def rebuild_index(memory_root: Path) -> None:
    global_files = sorted((memory_root / "global").glob("*.md")) if (memory_root / "global").exists() else []
    domain_readmes = sorted((memory_root / "domains").glob("*/README.md")) if (memory_root / "domains").exists() else []
    lines = ["# Shared Memory Index", "", "This file is the top-level index for imported shared memory.", ""]
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


def project_scope_paths(rendered_root: Path, scopes: list[str]) -> set[Path]:
    paths: set[Path] = {Path("MEMORY.md")}
    for scope in scopes:
        target = scope_to_target(scope)
        paths.add(target)
        if target.name == "README.md":
            domain_root = rendered_root / target.parent
            if domain_root.exists():
                for item in domain_root.rglob("*"):
                    if item.is_file():
                        paths.add(item.relative_to(rendered_root))
    return paths


def write_consumer_snapshot(
    install: PluginInstall,
    contract: dict[str, Any],
    export_root: Path,
    snapshot_version: str,
) -> None:
    destination = imports_root(install.plugin_data) / snapshot_version
    temp_destination = Path(tempfile.mkdtemp(prefix="import.", dir=imports_root(install.plugin_data)))
    rendered_root = export_root / "rendered"
    included = project_scope_paths(rendered_root, contract.get("shared_memory_read_scope", []))

    for relative_path in included:
        source = rendered_root / relative_path
        if source.exists() and source.is_file():
            target = temp_destination / relative_path
            ensure_dir(target.parent)
            shutil.copy2(source, target)

    metadata = load_json(export_root / "metadata.json", {})
    write_json_atomic(temp_destination / "SNAPSHOT.json", metadata)
    rebuild_index(temp_destination)

    if contract.get("shared_memory_write_scope"):
        outbox_link = temp_destination / "outbox"
        relative_target = os.path.relpath(stable_outbox_root(install.plugin_data), start=temp_destination)
        os.symlink(relative_target, outbox_link)

    if destination.exists():
        shutil.rmtree(destination)
    os.replace(temp_destination, destination)
    atomic_symlink(shared_memory_link(install.plugin_data), destination)


def run_command(command: list[str], env: dict[str, str] | None = None) -> dict[str, Any]:
    result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
    return json.loads(result.stdout)


def memory_script(installs: dict[str, PluginInstall]) -> Path:
    return installs["memory-aiws"].plugin_root / "scripts" / "aiws_memory_canonical.py"


def bootstrap_canonical_runtime(installs: dict[str, PluginInstall]) -> dict[str, Any]:
    memory_install = installs["memory-aiws"]
    return run_command(
        [
            sys.executable,
            str(memory_script(installs)),
            "bootstrap-canonical",
            "--plugin-data",
            str(memory_install.plugin_data),
            "--seed-root",
            str(memory_install.plugin_root / "memory"),
        ]
    )


def consolidate_with_memory_plugin(installs: dict[str, PluginInstall], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    memory_install = installs["memory-aiws"]
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        temp_path = Path(handle.name)
        for candidate in candidates:
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")
    try:
        return run_command(
            [
                sys.executable,
                str(memory_script(installs)),
                "consolidate",
                "--plugin-data",
                str(memory_install.plugin_data),
                "--seed-root",
                str(memory_install.plugin_root / "memory"),
                "--candidates-file",
                str(temp_path),
            ]
        )
    finally:
        temp_path.unlink(missing_ok=True)


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def quarantine_candidate(memory_plugin_data: Path, outbox_file: Path, reason: str, raw_content: str) -> None:
    quarantine_dir = ensure_dir(memory_plugin_data / "quarantine")
    payload = {
        "reason": reason,
        "outbox_file": str(outbox_file),
        "captured_ts": utc_now_iso(),
        "raw_content": raw_content,
    }
    name = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
    write_json_atomic(quarantine_dir / name, payload)


def validate_candidate(
    candidate: Any,
    producer_contract: dict[str, Any],
    memory_contract: dict[str, Any],
) -> tuple[bool, str]:
    if not isinstance(candidate, dict):
        return False, "candidate payload must be a JSON object"
    required = {
        "candidate_id",
        "ts",
        "plugin_id",
        "category",
        "scope",
        "summary",
        "evidence",
        "confidence",
    }
    missing = sorted(required - candidate.keys())
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"
    if candidate["plugin_id"] != producer_contract["plugin_id"]:
        return False, "plugin_id does not match producer contract"
    if candidate["scope"] not in producer_contract.get("shared_memory_write_scope", []):
        return False, "scope is outside producer shared_memory_write_scope"
    if candidate["scope"] not in memory_contract.get("shared_memory_write_scope", []):
        return False, "scope is outside memory-aiws shared_memory_write_scope"
    try:
        parse_ts(candidate["ts"])
    except ValueError as exc:
        return False, f"invalid ts: {exc}"
    if not isinstance(candidate["confidence"], (int, float)):
        return False, "confidence must be numeric"
    if float(candidate["confidence"]) < 0.0:
        return False, "confidence must be >= 0.0"
    return True, ""


def gather_outbox_files(
    installs: dict[str, PluginInstall],
    contracts: dict[str, dict[str, Any]],
) -> list[tuple[dict[str, Any], Path, dict[str, Any], str]]:
    memory_contract = contracts["memory-aiws"]
    gathered = []
    for plugin_id, contract in contracts.items():
        if plugin_id == "memory-aiws" or not contract.get("shared_memory_write_scope"):
            continue
        install = installs[plugin_id]
        outbox = shared_memory_link(install.plugin_data) / "outbox"
        if not outbox.exists():
            outbox = stable_outbox_root(install.plugin_data)
        for outbox_file in sorted(outbox.glob("*.json")):
            raw = outbox_file.read_text()
            try:
                candidate = json.loads(raw)
            except json.JSONDecodeError as exc:
                gathered.append(({}, outbox_file, contract, f"invalid JSON: {exc}"))
                continue
            is_valid, reason = validate_candidate(candidate, contract, memory_contract)
            gathered.append((candidate, outbox_file, contract, "" if is_valid else reason))
    return gathered


@dataclass
class Lease:
    lock_path: Path
    owner_id: str
    lease_generation: int

    def assert_owned(self) -> None:
        payload = load_json(self.lock_path, {})
        if payload.get("owner_id") != self.owner_id or payload.get("lease_generation") != self.lease_generation:
            raise BootstrapError("Lease ownership lost during refresh.")

    def heartbeat(self) -> None:
        self.assert_owned()
        payload = load_json(self.lock_path, {})
        payload["last_heartbeat_ts"] = utc_now_iso()
        write_json_atomic(self.lock_path, payload)

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
                guard_age = datetime.now(timezone.utc).timestamp() - guard_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if guard_age > stale_after_seconds:
                shutil.rmtree(guard_path, ignore_errors=True)
                continue
            raise BootstrapError("Shared-memory refresh is already running.")
    else:
        raise BootstrapError("Timed out waiting for the refresh lock guard.")

    try:
        generation = 0
        if lock_path.exists():
            payload = load_json(lock_path, {})
            age_seconds = (datetime.now(timezone.utc) - parse_ts(payload["last_heartbeat_ts"])).total_seconds()
            if age_seconds <= stale_after_seconds:
                raise BootstrapError("A live shared-memory refresh already owns the lock.")
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


def refresh_shared_memory(paths: HelperPaths, installs: dict[str, PluginInstall]) -> dict[str, Any]:
    contracts = load_registry_contracts(installs)
    memory_install = installs["memory-aiws"]
    if not (memory_install.plugin_data / "exports" / "latest").exists():
        bootstrap_canonical_runtime(installs)

    lease = acquire_lease(memory_install.plugin_data / "state" / "refresh.lock")
    files_to_remove: list[Path] = []
    refresh_state = {
        "started_ts": utc_now_iso(),
        "status": "running",
    }
    update_state(paths, "last_refresh", refresh_state)
    try:
        gathered = gather_outbox_files(installs, contracts)
        lease.assert_owned()
        processed_rows = read_jsonl(memory_install.plugin_data / "state" / "processed-candidate-ids.jsonl")
        processed_ids = {row["candidate_id"] for row in processed_rows}
        valid_candidates: list[dict[str, Any]] = []
        quarantine_count = 0
        duplicate_count = 0

        for candidate, outbox_file, _, reason in gathered:
            raw_content = outbox_file.read_text()
            if reason:
                quarantine_candidate(memory_install.plugin_data, outbox_file, reason, raw_content)
                quarantine_count += 1
                files_to_remove.append(outbox_file)
                continue
            if candidate["candidate_id"] in processed_ids:
                duplicate_count += 1
                files_to_remove.append(outbox_file)
                continue
            valid_candidates.append(candidate)
            files_to_remove.append(outbox_file)

        lease.heartbeat()
        consolidate_result = consolidate_with_memory_plugin(installs, valid_candidates)
        lease.assert_owned()

        export_root = (memory_install.plugin_data / "exports" / "latest").resolve()
        snapshot_version = load_json(export_root / "metadata.json", {}).get("snapshot_version")

        for plugin_id, contract in contracts.items():
            if plugin_id == "memory-aiws":
                continue
            if contract.get("shared_memory_read_scope"):
                lease.assert_owned()
                write_consumer_snapshot(installs[plugin_id], contract, export_root, snapshot_version)
            lease.heartbeat()

        lease.assert_owned()
        for path in files_to_remove:
            path.unlink(missing_ok=True)

        result = {
            "accepted_candidates": consolidate_result["accepted_candidates"],
            "duplicate_candidates": duplicate_count,
            "quarantined_candidates": quarantine_count,
            "snapshot_version": snapshot_version,
        }
        update_state(
            paths,
            "last_refresh",
            {
                "started_ts": refresh_state["started_ts"],
                "completed_ts": utc_now_iso(),
                "status": "ok",
                **result,
            },
        )
        return result
    except Exception as exc:
        update_state(
            paths,
            "last_refresh",
            {
                "started_ts": refresh_state["started_ts"],
                "completed_ts": utc_now_iso(),
                "status": "error",
                "error": str(exc),
            },
        )
        raise
    finally:
        lease.release()


def canonical_hook_group() -> dict[str, Any]:
    return json.loads(json.dumps(MANAGED_STOP_GROUP))


def hook_group_status(group: dict[str, Any]) -> str:
    if group == MANAGED_STOP_GROUP:
        return "healthy"
    return "drifted"


def read_settings_object(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {}
    try:
        payload = json.loads(settings_path.read_text())
    except json.JSONDecodeError as exc:
        backup = settings_path.with_name(settings_path.name + f".bak-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}")
        shutil.copy2(settings_path, backup)
        raise BootstrapError(
            f"Settings file is invalid JSON: {settings_path}. Backed up to {backup}. Fix the file and rerun bootstrap."
        ) from exc
    if not isinstance(payload, dict):
        raise BootstrapError(f"Settings file must contain a JSON object: {settings_path}")
    return payload


def managed_stop_groups(settings_payload: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = settings_payload.get("hooks", {})
    stop_groups = hooks.get("Stop", [])
    managed = []
    for group in stop_groups:
        if not isinstance(group, dict):
            continue
        for hook in group.get("hooks", []):
            if hook.get("command") == MANAGED_HOOK_COMMAND:
                managed.append(group)
                break
    return managed


def hook_health(settings_path: Path) -> dict[str, Any]:
    if not settings_path.exists():
        return {"status": "missing", "details": "settings.json does not exist"}
    payload = read_settings_object(settings_path)
    managed = managed_stop_groups(payload)
    if not managed:
        return {"status": "missing", "details": "managed Stop hook is not present"}
    if len(managed) > 1:
        return {"status": "duplicate", "details": f"found {len(managed)} managed Stop hook groups"}
    status = hook_group_status(managed[0])
    details = "managed Stop hook matches the canonical config" if status == "healthy" else "managed Stop hook exists but drifted from the canonical config"
    return {"status": status, "details": details}


def upsert_managed_stop_hook(paths: HelperPaths) -> dict[str, Any]:
    payload = read_settings_object(paths.settings_path)
    hooks = payload.setdefault("hooks", {})
    stop_groups = hooks.setdefault("Stop", [])
    if not isinstance(stop_groups, list):
        raise BootstrapError("`hooks.Stop` must be a JSON array in settings.json.")

    unmanaged: list[Any] = []
    for group in stop_groups:
        is_managed = False
        if isinstance(group, dict):
            for hook in group.get("hooks", []):
                if hook.get("command") == MANAGED_HOOK_COMMAND:
                    is_managed = True
                    break
        if not is_managed:
            unmanaged.append(group)

    hooks["Stop"] = unmanaged + [canonical_hook_group()]
    write_json_atomic(paths.settings_path, payload)
    return hook_health(paths.settings_path)


def bootstrap(paths: HelperPaths, args: argparse.Namespace) -> dict[str, Any]:
    phases = {
        "config_written": False,
        "registry_populated": False,
        "canonical_bootstrapped": False,
        "hook_upserted": False,
    }
    installs = resolve_installs(args, paths)
    contracts = {plugin_id: validate_contract(install) for plugin_id, install in installs.items()}

    try:
        config = config_payload(paths, installs)
        ensure_dir(paths.helper_home)
        write_json_atomic(paths.config_path, config)
        phases["config_written"] = True
        update_state(
            paths,
            "last_bootstrap",
            {
                "attempted_ts": utc_now_iso(),
                "status": "running",
                "phases": phases.copy(),
            },
        )

        registered = populate_registry(installs)
        phases["registry_populated"] = True
        bootstrap_result = bootstrap_canonical_runtime(installs)
        phases["canonical_bootstrapped"] = True

        export_root = (installs["memory-aiws"].plugin_data / "exports" / "latest").resolve()
        snapshot_version = load_json(export_root / "metadata.json", {}).get("snapshot_version")
        for plugin_id, contract in contracts.items():
            if plugin_id == "memory-aiws":
                continue
            if contract.get("shared_memory_read_scope"):
                write_consumer_snapshot(installs[plugin_id], contract, export_root, snapshot_version)
            if contract.get("shared_memory_write_scope"):
                stable_outbox_root(installs[plugin_id].plugin_data)

        hook = upsert_managed_stop_hook(paths)
        phases["hook_upserted"] = True
        result = {
            "status": "ok",
            "config_path": str(paths.config_path),
            "settings_path": str(paths.settings_path),
            "registered_plugins": registered,
            "contracts": {
                plugin_id: compute_contract_digest(install.contract_path)
                for plugin_id, install in installs.items()
            },
            "snapshot_version": snapshot_version,
            "canonical_bootstrap": bootstrap_result,
            "hook": hook,
            "phases": phases,
            "verification": "Run `/hooks` if Claude does not pick up the new Stop hook until restart/reload.",
        }
        update_state(
            paths,
            "last_bootstrap",
            {
                "attempted_ts": utc_now_iso(),
                "completed_ts": utc_now_iso(),
                "status": "ok",
                "phases": phases,
            },
        )
        return result
    except Exception as exc:
        update_state(
            paths,
            "last_bootstrap",
            {
                "attempted_ts": utc_now_iso(),
                "completed_ts": utc_now_iso(),
                "status": "error",
                "error": str(exc),
                "phases": phases,
            },
        )
        raise


def doctor(paths: HelperPaths) -> tuple[dict[str, Any], int]:
    issues: list[str] = []
    details: dict[str, Any] = {
        "config_path": str(paths.config_path),
        "settings_path": str(paths.settings_path),
        "bootstrap_state": helper_state(paths).get("last_bootstrap"),
        "refresh_state": helper_state(paths).get("last_refresh"),
    }
    installs: dict[str, PluginInstall] = {}

    try:
        installs = load_installs_from_config(paths)
        details["plugins"] = {
            plugin_id: install.to_payload()
            for plugin_id, install in installs.items()
        }
        for install in installs.values():
            validate_contract(install)
    except Exception as exc:
        issues.append(str(exc))

    if installs:
        registry = registry_root(installs)
        registry_files = sorted(path.name for path in registry.glob("*.json")) if registry.exists() else []
        details["registry_files"] = registry_files
        missing_registry = [plugin_id for plugin_id in REQUIRED_PLUGIN_IDS if f"{plugin_id}.json" not in registry_files]
        if missing_registry:
            issues.append("Registry is missing entries for: " + ", ".join(missing_registry))

        memory_export = installs["memory-aiws"].plugin_data / "exports" / "latest" / "metadata.json"
        if not memory_export.exists():
            issues.append("memory-aiws canonical export is missing. Re-run `aiws-host-memory bootstrap`.")
        try:
            details["hook"] = hook_health(paths.settings_path)
            if details["hook"]["status"] != "healthy":
                issues.append("Managed Stop hook is not healthy. Re-run `aiws-host-memory bootstrap`.")
        except BootstrapError as exc:
            details["hook"] = {"status": "error", "details": str(exc)}
            issues.append(str(exc))
    else:
        if paths.settings_path.exists():
            try:
                details["hook"] = hook_health(paths.settings_path)
            except BootstrapError as exc:
                details["hook"] = {"status": "error", "details": str(exc)}
                issues.append(str(exc))
        else:
            details["hook"] = {"status": "missing"}

    details["issues"] = issues
    details["status"] = "ok" if not issues else "error"
    return details, 0 if not issues else 1


def status(paths: HelperPaths) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "config_path": str(paths.config_path),
        "settings_path": str(paths.settings_path),
        "state": helper_state(paths),
    }
    try:
        payload["hook"] = hook_health(paths.settings_path)
    except BootstrapError as exc:
        payload["hook"] = {"status": "error", "details": str(exc)}
    if paths.config_path.exists():
        payload["config"] = load_json(paths.config_path, {})
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aiws-host-memory")
    parser.add_argument("--helper-home", type=Path)
    parser.add_argument("--settings-path", type=Path)
    parser.add_argument("--claude-home", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_cmd = subparsers.add_parser("bootstrap")
    bootstrap_cmd.add_argument("--core-plugin-root", type=Path)
    bootstrap_cmd.add_argument("--core-plugin-data", type=Path)
    bootstrap_cmd.add_argument("--memory-plugin-root", type=Path)
    bootstrap_cmd.add_argument("--memory-plugin-data", type=Path)
    bootstrap_cmd.add_argument("--data-analysis-plugin-root", type=Path)
    bootstrap_cmd.add_argument("--data-analysis-plugin-data", type=Path)

    subparsers.add_parser("refresh-shared")
    subparsers.add_parser("doctor")
    subparsers.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = helper_paths(helper_home=args.helper_home, settings_path=args.settings_path, claude_home=args.claude_home)

    try:
        if args.command == "bootstrap":
            result = bootstrap(paths, args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "refresh-shared":
            installs = load_installs_from_config(paths)
            result = refresh_shared_memory(paths, installs)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "doctor":
            result, exit_code = doctor(paths)
            print(json.dumps(result, indent=2, sort_keys=True))
            return exit_code
        result = status(paths)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except subprocess.CalledProcessError as exc:
        message = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(json.dumps({"status": "error", "error": message}, indent=2, sort_keys=True))
        return exc.returncode or 1
    except Exception as exc:  # pragma: no cover - CLI safety net
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        return 1
