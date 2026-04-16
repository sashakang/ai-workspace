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


INFRASTRUCTURE_PLUGIN_IDS = ("core-aiws", "memory-aiws")
DEFAULT_MARKETPLACE = "ai-workspace"
MANAGED_HOOK_COMMAND = "aiws-host-memory refresh-shared"
MANAGED_HOOK_EVENT = "SessionEnd"
MANAGED_HOOK_GROUP = {
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
    host_kind: str
    claude_home: Path
    helper_home: Path
    config_path: Path
    state_path: Path
    settings_path: Path | None
    installed_plugins_path: Path
    plugin_data_root: Path

    @property
    def bootstrap_command(self) -> str:
        return "aiws-host-memory bootstrap-cowork" if self.host_kind == "cowork" else "aiws-host-memory bootstrap"

    @property
    def refresh_command(self) -> str:
        return "aiws-host-memory refresh-cowork" if self.host_kind == "cowork" else "aiws-host-memory refresh-shared"


def helper_paths(
    helper_home: Path | None = None,
    settings_path: Path | None = None,
    claude_home: Path | None = None,
) -> HelperPaths:
    claude_root = claude_home or Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
    helper_root = helper_home or Path(os.environ.get("AIWS_HOST_MEMORY_HOME", claude_root / "aiws-host-memory"))
    return HelperPaths(
        host_kind="claude",
        claude_home=claude_root,
        helper_home=helper_root,
        config_path=helper_root / "config.json",
        state_path=helper_root / "state.json",
        settings_path=settings_path or Path(os.environ.get("AIWS_HOST_MEMORY_SETTINGS_PATH", claude_root / "settings.json")),
        installed_plugins_path=claude_root / "plugins" / "installed_plugins.json",
        plugin_data_root=claude_root / "plugins" / "data",
    )


def cowork_helper_paths(
    helper_home: Path | None = None,
    cowork_home: Path | None = None,
    claude_home: Path | None = None,
) -> HelperPaths:
    cowork_root = cowork_home or Path(os.environ.get("COWORK_HOME", Path.home() / ".cowork"))
    helper_root = helper_home or Path(os.environ.get("AIWS_HOST_MEMORY_COWORK_HOME", cowork_root / "aiws-host-memory"))
    resolved_claude_home = claude_home or Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude"))
    return HelperPaths(
        host_kind="cowork",
        claude_home=resolved_claude_home,
        helper_home=helper_root,
        config_path=helper_root / "config.json",
        state_path=helper_root / "state.json",
        settings_path=None,
        installed_plugins_path=cowork_root / "plugins" / "installed_plugins.json",
        plugin_data_root=cowork_root / "plugins" / "data",
    )


def default_contract_path(plugin_root: Path, plugin_id: str) -> Path:
    return plugin_root / "contracts" / f"{plugin_id}.contract.json"


def parse_plugin_assignment(raw: str, *, field_name: str) -> tuple[str, Path]:
    plugin_id, sep, value = raw.partition("=")
    if not sep or not plugin_id or not value:
        raise BootstrapError(
            f"{field_name} must use the form <plugin_id>=<path>."
        )
    return plugin_id, Path(value)


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
    payload = {
        "version": 1,
        "host_kind": paths.host_kind,
        "created_ts": created_ts,
        "updated_ts": now,
        "plugins": {
            plugin_id: install.to_payload()
            for plugin_id, install in installs.items()
        },
    }
    if paths.settings_path is not None:
        payload["settings_path"] = str(paths.settings_path)
    return payload


def load_config(paths: HelperPaths) -> dict[str, Any]:
    payload = load_json(paths.config_path, {})
    if not payload:
        raise BootstrapError(
            f"Helper config not found at {paths.config_path}. Run `{paths.bootstrap_command}` first."
        )
    return payload


def load_installs_from_config(paths: HelperPaths) -> dict[str, PluginInstall]:
    payload = load_config(paths)
    installs_payload = payload.get("plugins", {})
    installs = {
        plugin_id: parse_install_from_payload(plugin_id, plugin_payload)
        for plugin_id, plugin_payload in installs_payload.items()
    }
    missing = [plugin_id for plugin_id in INFRASTRUCTURE_PLUGIN_IDS if plugin_id not in installs]
    if missing:
        raise BootstrapError(
            "Helper config is incomplete. Missing infrastructure plugin installs for: "
            + ", ".join(sorted(missing))
        )
    return installs


def canonical_owner_payload(owner: CanonicalOwner) -> dict[str, str]:
    return {
        "claude_home": str(owner.claude_paths.claude_home),
        "memory_plugin_root": str(owner.memory_install.plugin_root),
        "memory_plugin_data": str(owner.memory_install.plugin_data),
        "canonical_root": str(owner.canonical_root),
        "export_root": str(owner.export_root),
        "lock_path": str(owner.lock_path),
        "processed_ids_path": str(owner.processed_ids_path),
    }


def cowork_config_payload(
    paths: HelperPaths,
    installs: dict[str, PluginInstall],
    owner: CanonicalOwner,
) -> dict[str, Any]:
    payload = config_payload(paths, installs)
    payload["claude_owner"] = canonical_owner_payload(owner)
    return payload


def canonical_owner_identity(owner_payload: dict[str, str]) -> dict[str, str]:
    return {
        "claude_home": owner_payload["claude_home"],
        "memory_plugin_root": owner_payload["memory_plugin_root"],
        "memory_plugin_data": owner_payload["memory_plugin_data"],
        "canonical_root": owner_payload["canonical_root"],
        "lock_path": owner_payload["lock_path"],
        "processed_ids_path": owner_payload["processed_ids_path"],
    }


def canonical_owner_from_cowork_config(paths: HelperPaths) -> CanonicalOwner:
    payload = load_config(paths)
    owner_payload = payload.get("claude_owner", {})
    required = {
        "claude_home",
        "memory_plugin_root",
        "memory_plugin_data",
        "canonical_root",
        "export_root",
        "lock_path",
        "processed_ids_path",
    }
    missing = sorted(required - owner_payload.keys())
    if missing:
        raise BootstrapError(
            "Cowork helper config is incomplete. Missing Claude canonical owner fields: "
            + ", ".join(missing)
        )

    claude_paths = helper_paths(claude_home=Path(owner_payload["claude_home"]))
    owner = CanonicalOwner(
        claude_paths=claude_paths,
        memory_install=PluginInstall(
            plugin_id="memory-aiws",
            plugin_root=Path(owner_payload["memory_plugin_root"]),
            plugin_data=Path(owner_payload["memory_plugin_data"]),
            contract_path=default_contract_path(Path(owner_payload["memory_plugin_root"]), "memory-aiws"),
        ),
        export_root=Path(owner_payload["export_root"]),
        lock_path=Path(owner_payload["lock_path"]),
        processed_ids_path=Path(owner_payload["processed_ids_path"]),
    )
    if not owner.canonical_root.exists():
        raise BootstrapError(
            f"Stored Claude canonical root is missing: {owner.canonical_root}. "
            f"Re-run `{paths.bootstrap_command}` and pass --claude-home if Claude moved."
        )
    if not owner.export_root.exists():
        raise BootstrapError(
            f"Stored Claude canonical export is missing: {owner.export_root}. "
            f"Re-run `{paths.bootstrap_command}` and pass --claude-home if Claude moved."
        )
    if not owner.processed_ids_path.exists():
        raise BootstrapError(
            f"Stored Claude processed-candidate ledger is missing: {owner.processed_ids_path}. "
            f"Re-run `{paths.bootstrap_command}` and pass --claude-home if Claude moved."
        )
    return owner


def assert_canonical_owner_matches(paths: HelperPaths, stored_owner: CanonicalOwner, live_owner: CanonicalOwner) -> None:
    stored_identity = canonical_owner_identity(canonical_owner_payload(stored_owner))
    live_identity = canonical_owner_identity(canonical_owner_payload(live_owner))
    if stored_identity == live_identity:
        return
    raise BootstrapError(
        "Stored Claude canonical owner no longer matches the live Claude memory-aiws install. "
        f"Re-run `{paths.bootstrap_command}` and pass --claude-home if Claude moved."
    )


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
    suffix = marketplace or DEFAULT_MARKETPLACE
    return data_root / f"{plugin_id}-{suffix}"


def detect_installs(paths: HelperPaths) -> dict[str, PluginInstall]:
    payload = load_json(paths.installed_plugins_path, {})
    plugins = payload.get("plugins", {})
    detected: dict[str, PluginInstall] = {}
    for key, installs in plugins.items():
        plugin_name, _, marketplace = key.partition("@")
        if marketplace and marketplace != DEFAULT_MARKETPLACE:
            continue
        if not installs:
            continue
        install_root = Path(installs[0]["installPath"])
        contract_path = default_contract_path(install_root, plugin_name)
        if not contract_path.exists():
            continue
        plugin_data = guess_marketplace_data_dir(plugin_name, marketplace or None, paths.plugin_data_root)
        detected[plugin_name] = PluginInstall(
            plugin_id=plugin_name,
            plugin_root=install_root,
            plugin_data=plugin_data,
            contract_path=contract_path,
        )
    return detected


def explicit_install_overrides(args: argparse.Namespace) -> dict[str, dict[str, Path | None]]:
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
    for raw in getattr(args, "plugin_root", []) or []:
        plugin_id, path = parse_plugin_assignment(raw, field_name="--plugin-root")
        explicit.setdefault(plugin_id, {"root": None, "data": None})["root"] = path
    for raw in getattr(args, "plugin_data", []) or []:
        plugin_id, path = parse_plugin_assignment(raw, field_name="--plugin-data")
        explicit.setdefault(plugin_id, {"root": None, "data": None})["data"] = path
    return explicit


def resolve_claude_memory_install(args: argparse.Namespace) -> tuple[HelperPaths, PluginInstall]:
    claude_paths = helper_paths(claude_home=args.claude_home)
    explicit = explicit_install_overrides(args).get("memory-aiws", {})
    explicit_root = explicit.get("root")
    explicit_data = explicit.get("data")

    if explicit_root or explicit_data:
        if not (explicit_root and explicit_data):
            raise BootstrapError(
                "Cowork Claude memory-aiws overrides require both --memory-plugin-root and --memory-plugin-data."
            )
        install = PluginInstall(
            plugin_id="memory-aiws",
            plugin_root=explicit_root,
            plugin_data=explicit_data,
            contract_path=default_contract_path(explicit_root, "memory-aiws"),
        )
        validate_contract(install)
        return claude_paths, install

    if claude_paths.config_path.exists():
        try:
            configured = load_installs_from_config(claude_paths)
            install = configured.get("memory-aiws")
            if install is not None:
                validate_contract(install)
                return claude_paths, install
        except BootstrapError:
            pass

    detected = detect_installs(claude_paths)
    install = detected.get("memory-aiws")
    if install is None:
        raise BootstrapError(
            f"Claude memory-aiws install could not be resolved from {claude_paths.installed_plugins_path} "
            f"or {claude_paths.config_path}. Bootstrap Claude first, or point Cowork at the right Claude home with --claude-home."
        )
    validate_contract(install)
    return claude_paths, install


def resolve_installs(args: argparse.Namespace, paths: HelperPaths) -> dict[str, PluginInstall]:
    detected = detect_installs(paths)
    explicit = explicit_install_overrides(args)
    installs: dict[str, PluginInstall] = {}

    for plugin_id in sorted(set(detected) | set(explicit)):
        candidate = detected.get(plugin_id)
        root = explicit.get(plugin_id, {}).get("root") or (candidate.plugin_root if candidate else None)
        data = explicit.get(plugin_id, {}).get("data") or (candidate.plugin_data if candidate else None)
        if root and data:
            installs[plugin_id] = PluginInstall(
                plugin_id=plugin_id,
                plugin_root=root,
                plugin_data=data,
                contract_path=default_contract_path(root, plugin_id),
            )

    missing = [plugin_id for plugin_id in INFRASTRUCTURE_PLUGIN_IDS if plugin_id not in installs]
    if missing:
        raise BootstrapError(
            "Could not resolve infrastructure plugin installs for: "
            + ", ".join(missing)
            + ". Re-run bootstrap with explicit --*-plugin-root/--*-plugin-data flags or "
            + "--plugin-root/--plugin-data assignments."
        )
    return installs


def resolved_contracts(installs: dict[str, PluginInstall]) -> tuple[dict[str, PluginInstall], dict[str, dict[str, Any]], dict[str, str]]:
    contracts = {
        plugin_id: validate_contract(install)
        for plugin_id, install in installs.items()
    }
    active = dict(installs)
    skipped: dict[str, str] = {}

    changed = True
    while changed:
        changed = False
        for plugin_id in sorted(list(active)):
            missing = sorted(
                dependency
                for dependency in contracts[plugin_id].get("dependencies", [])
                if dependency not in active
            )
            if not missing:
                continue
            if plugin_id in INFRASTRUCTURE_PLUGIN_IDS:
                raise BootstrapError(
                    f"{plugin_id} is missing required dependencies: {', '.join(missing)}"
                )
            skipped[plugin_id] = "missing dependencies: " + ", ".join(missing)
            del active[plugin_id]
            changed = True

    active_contracts = {plugin_id: contracts[plugin_id] for plugin_id in active}
    return active, active_contracts, skipped


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


def load_snapshot_version(export_root: Path, *, command_hint: str) -> str:
    metadata = load_json(export_root / "metadata.json", {})
    snapshot_version = metadata.get("snapshot_version")
    if not isinstance(snapshot_version, str) or not snapshot_version:
        raise BootstrapError(
            f"Canonical export metadata at {export_root / 'metadata.json'} is missing a valid snapshot_version. "
            f"Re-run `{command_hint}`."
        )
    return snapshot_version


def consolidate_with_memory_runtime(
    *,
    script_path: Path,
    plugin_data: Path,
    seed_root: Path,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    with tempfile.NamedTemporaryFile("w", delete=False) as handle:
        temp_path = Path(handle.name)
        for candidate in candidates:
            handle.write(json.dumps(candidate, sort_keys=True) + "\n")
    try:
        return run_command(
            [
                sys.executable,
                str(script_path),
                "consolidate",
                "--plugin-data",
                str(plugin_data),
                "--seed-root",
                str(seed_root),
                "--candidates-file",
                str(temp_path),
            ]
        )
    finally:
        temp_path.unlink(missing_ok=True)


def consolidate_with_memory_plugin(installs: dict[str, PluginInstall], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    memory_install = installs["memory-aiws"]
    return consolidate_with_memory_runtime(
        script_path=memory_script(installs),
        plugin_data=memory_install.plugin_data,
        seed_root=memory_install.plugin_root / "memory",
        candidates=candidates,
    )


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


def remove_path(path: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
        return
    shutil.rmtree(path)


def backup_plugin_data_roots(installs: dict[str, PluginInstall]) -> tuple[Path, dict[Path, Path | None]]:
    backup_root = Path(tempfile.mkdtemp(prefix="cowork-bootstrap.", dir=Path(tempfile.gettempdir())))
    backups: dict[Path, Path | None] = {}
    for plugin_data in sorted({install.plugin_data for install in installs.values()}, key=str):
        if plugin_data.exists():
            backup_path = backup_root / f"{plugin_data.name}-{uuid.uuid4().hex[:8]}"
            shutil.copytree(plugin_data, backup_path, symlinks=True)
            backups[plugin_data] = backup_path
        else:
            backups[plugin_data] = None
    return backup_root, backups


def restore_plugin_data_roots(backups: dict[Path, Path | None]) -> None:
    for plugin_data, backup_path in backups.items():
        remove_path(plugin_data)
        if backup_path is not None:
            ensure_dir(plugin_data.parent)
            shutil.copytree(backup_path, plugin_data, symlinks=True)


def owner_resolution_args(claude_home: Path) -> argparse.Namespace:
    return argparse.Namespace(
        claude_home=claude_home,
        core_plugin_root=None,
        core_plugin_data=None,
        memory_plugin_root=None,
        memory_plugin_data=None,
        data_analysis_plugin_root=None,
        data_analysis_plugin_data=None,
        plugin_root=[],
        plugin_data=[],
    )


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


@dataclass
class CanonicalOwner:
    claude_paths: HelperPaths
    memory_install: PluginInstall
    export_root: Path
    lock_path: Path
    processed_ids_path: Path

    @property
    def canonical_root(self) -> Path:
        return self.memory_install.plugin_data / "shared-memory"


def resolve_claude_owner(args: argparse.Namespace) -> CanonicalOwner:
    claude_paths, memory_install = resolve_claude_memory_install(args)

    export_root = (memory_install.plugin_data / "exports" / "latest")
    lock_path = memory_install.plugin_data / "state" / "refresh.lock"
    processed_ids_path = memory_install.plugin_data / "state" / "processed-candidate-ids.jsonl"

    if not memory_install.plugin_data.exists() or not (memory_install.plugin_data / "shared-memory").exists():
        raise BootstrapError(
            "Claude memory-aiws is installed but canonical shared memory has not been bootstrapped yet. "
            "Run `aiws-host-memory bootstrap` first."
        )
    if not export_root.exists():
        raise BootstrapError(
            "Claude memory-aiws canonical export is missing. Run `aiws-host-memory bootstrap` first."
        )
    if not processed_ids_path.exists():
        raise BootstrapError(
            f"Claude processed-candidate ledger is missing or unreadable: {processed_ids_path}. "
            "Re-run `aiws-host-memory bootstrap`."
        )

    return CanonicalOwner(
        claude_paths=claude_paths,
        memory_install=memory_install,
        export_root=export_root.resolve(),
        lock_path=lock_path,
        processed_ids_path=processed_ids_path,
    )


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


def bootstrap_cowork(paths: HelperPaths, args: argparse.Namespace) -> dict[str, Any]:
    phases = {
        "claude_owner_resolved": False,
        "registry_populated": False,
        "imports_written": False,
        "config_written": False,
    }
    installs, contracts, skipped_plugins = resolved_contracts(resolve_installs(args, paths))
    owner = resolve_claude_owner(args)
    phases["claude_owner_resolved"] = True
    backup_root, backups = backup_plugin_data_roots(installs)

    update_state(
        paths,
        "last_bootstrap",
        {
            "attempted_ts": utc_now_iso(),
            "status": "running",
            "phases": phases.copy(),
        },
    )

    try:
        registered = populate_registry(installs)
        phases["registry_populated"] = True

        snapshot_version = load_snapshot_version(
            owner.export_root,
            command_hint="aiws-host-memory bootstrap",
        )
        for plugin_id, contract in contracts.items():
            if plugin_id == "memory-aiws":
                continue
            if contract.get("shared_memory_read_scope"):
                write_consumer_snapshot(installs[plugin_id], contract, owner.export_root, snapshot_version)
            if contract.get("shared_memory_write_scope"):
                stable_outbox_root(installs[plugin_id].plugin_data)
        phases["imports_written"] = True

        ensure_dir(paths.helper_home)
        write_json_atomic(paths.config_path, cowork_config_payload(paths, installs, owner))
        phases["config_written"] = True

        result = {
            "status": "ok",
            "config_path": str(paths.config_path),
            "registered_plugins": registered,
            "skipped_plugins": skipped_plugins,
            "contracts": {
                plugin_id: compute_contract_digest(install.contract_path)
                for plugin_id, install in installs.items()
            },
            "snapshot_version": snapshot_version,
            "canonical_owner": canonical_owner_payload(owner),
            "phases": phases,
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
        shutil.rmtree(backup_root, ignore_errors=True)
        return result
    except Exception as exc:
        restore_plugin_data_roots(backups)
        shutil.rmtree(backup_root, ignore_errors=True)
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


def refresh_cowork_shared_memory(paths: HelperPaths, installs: dict[str, PluginInstall], owner: CanonicalOwner) -> dict[str, Any]:
    live_owner = resolve_claude_owner(owner_resolution_args(paths.claude_home))
    assert_canonical_owner_matches(paths, owner, live_owner)
    owner = live_owner
    contracts = load_registry_contracts(installs)
    lease = acquire_lease(owner.lock_path)
    files_to_remove: list[Path] = []
    refresh_state = {
        "started_ts": utc_now_iso(),
        "status": "running",
    }
    update_state(paths, "last_refresh", refresh_state)
    try:
        gathered = gather_outbox_files(installs, contracts)
        lease.assert_owned()
        processed_rows = read_jsonl(owner.processed_ids_path)
        processed_ids = {row["candidate_id"] for row in processed_rows}
        valid_candidates: list[dict[str, Any]] = []
        quarantine_count = 0
        duplicate_count = 0

        for candidate, outbox_file, _, reason in gathered:
            raw_content = outbox_file.read_text()
            if reason:
                quarantine_candidate(owner.memory_install.plugin_data, outbox_file, reason, raw_content)
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
        consolidate_result = consolidate_with_memory_runtime(
            script_path=owner.memory_install.plugin_root / "scripts" / "aiws_memory_canonical.py",
            plugin_data=owner.memory_install.plugin_data,
            seed_root=owner.memory_install.plugin_root / "memory",
            candidates=valid_candidates,
        )
        lease.assert_owned()

        export_root = (owner.memory_install.plugin_data / "exports" / "latest").resolve()
        snapshot_version = load_snapshot_version(
            export_root,
            command_hint="aiws-host-memory refresh-shared",
        )

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
    return json.loads(json.dumps(MANAGED_HOOK_GROUP))


def hook_group_status(group: dict[str, Any]) -> str:
    if group == MANAGED_HOOK_GROUP:
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


def managed_hook_groups(settings_payload: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = settings_payload.get("hooks", {})
    event_groups = hooks.get(MANAGED_HOOK_EVENT, [])
    managed = []
    for group in event_groups:
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
    managed = managed_hook_groups(payload)
    if not managed:
        return {"status": "missing", "details": f"managed {MANAGED_HOOK_EVENT} hook is not present"}
    if len(managed) > 1:
        return {"status": "duplicate", "details": f"found {len(managed)} managed {MANAGED_HOOK_EVENT} hook groups"}
    status = hook_group_status(managed[0])
    details = (
        f"managed {MANAGED_HOOK_EVENT} hook matches the canonical config"
        if status == "healthy"
        else f"managed {MANAGED_HOOK_EVENT} hook exists but drifted from the canonical config"
    )
    return {"status": status, "details": details}


def upsert_managed_hook(paths: HelperPaths) -> dict[str, Any]:
    payload = read_settings_object(paths.settings_path)
    hooks = payload.setdefault("hooks", {})
    event_groups = hooks.setdefault(MANAGED_HOOK_EVENT, [])
    if not isinstance(event_groups, list):
        raise BootstrapError(f"`hooks.{MANAGED_HOOK_EVENT}` must be a JSON array in settings.json.")

    unmanaged: list[Any] = []
    for group in event_groups:
        is_managed = False
        if isinstance(group, dict):
            for hook in group.get("hooks", []):
                if hook.get("command") == MANAGED_HOOK_COMMAND:
                    is_managed = True
                    break
        if not is_managed:
            unmanaged.append(group)

    hooks[MANAGED_HOOK_EVENT] = unmanaged + [canonical_hook_group()]
    legacy_stop_groups = hooks.get("Stop", [])
    if not isinstance(legacy_stop_groups, list):
        raise BootstrapError("`hooks.Stop` must be a JSON array in settings.json.")
    unmanaged_stop_groups: list[Any] = []
    for group in legacy_stop_groups:
        is_managed = False
        if isinstance(group, dict):
            for hook in group.get("hooks", []):
                if hook.get("command") == MANAGED_HOOK_COMMAND:
                    is_managed = True
                    break
        if not is_managed:
            unmanaged_stop_groups.append(group)
    hooks["Stop"] = unmanaged_stop_groups

    write_json_atomic(paths.settings_path, payload)
    return hook_health(paths.settings_path)


def bootstrap(paths: HelperPaths, args: argparse.Namespace) -> dict[str, Any]:
    phases = {
        "config_written": False,
        "registry_populated": False,
        "canonical_bootstrapped": False,
        "hook_upserted": False,
    }
    installs, contracts, skipped_plugins = resolved_contracts(resolve_installs(args, paths))

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

        hook = upsert_managed_hook(paths)
        phases["hook_upserted"] = True
        result = {
            "status": "ok",
            "config_path": str(paths.config_path),
            "settings_path": str(paths.settings_path),
            "registered_plugins": registered,
            "skipped_plugins": skipped_plugins,
            "contracts": {
                plugin_id: compute_contract_digest(install.contract_path)
                for plugin_id, install in installs.items()
            },
            "snapshot_version": snapshot_version,
            "canonical_bootstrap": bootstrap_result,
            "hook": hook,
            "phases": phases,
            "verification": f"Run `/hooks` if Claude does not pick up the new {MANAGED_HOOK_EVENT} hook until restart/reload.",
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
        configured_installs = load_installs_from_config(paths)
        installs, _, skipped_plugins = resolved_contracts(configured_installs)
        details["plugins"] = {
            plugin_id: install.to_payload()
            for plugin_id, install in installs.items()
        }
        details["skipped_plugins"] = skipped_plugins
    except Exception as exc:
        issues.append(str(exc))

    if installs:
        registry = registry_root(installs)
        registry_files = sorted(path.name for path in registry.glob("*.json")) if registry.exists() else []
        details["registry_files"] = registry_files
        missing_registry = [plugin_id for plugin_id in installs if f"{plugin_id}.json" not in registry_files]
        if missing_registry:
            issues.append("Registry is missing entries for: " + ", ".join(missing_registry))

        memory_export = installs["memory-aiws"].plugin_data / "exports" / "latest" / "metadata.json"
        if not memory_export.exists():
            issues.append("memory-aiws canonical export is missing. Re-run `aiws-host-memory bootstrap`.")
        try:
            details["hook"] = hook_health(paths.settings_path)
            if details["hook"]["status"] != "healthy":
                issues.append(f"Managed {MANAGED_HOOK_EVENT} hook is not healthy. Re-run `aiws-host-memory bootstrap`.")
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


def doctor_cowork(paths: HelperPaths) -> tuple[dict[str, Any], int]:
    issues: list[str] = []
    details: dict[str, Any] = {
        "config_path": str(paths.config_path),
        "state": helper_state(paths),
    }
    installs: dict[str, PluginInstall] = {}

    try:
        configured_installs = load_installs_from_config(paths)
        installs, _, skipped_plugins = resolved_contracts(configured_installs)
        details["plugins"] = {
            plugin_id: install.to_payload()
            for plugin_id, install in installs.items()
        }
        details["skipped_plugins"] = skipped_plugins
    except Exception as exc:
        issues.append(str(exc))

    try:
        owner = canonical_owner_from_cowork_config(paths)
        details["canonical_owner"] = canonical_owner_payload(owner)
    except Exception as exc:
        issues.append(str(exc))
        owner = None

    if owner is not None:
        try:
            live_owner = resolve_claude_owner(owner_resolution_args(paths.claude_home))
            assert_canonical_owner_matches(paths, owner, live_owner)
            details["live_canonical_owner"] = canonical_owner_payload(live_owner)
        except Exception as exc:
            issues.append(str(exc))

    if installs:
        registry = registry_root(installs)
        registry_files = sorted(path.name for path in registry.glob("*.json")) if registry.exists() else []
        details["registry_files"] = registry_files
        missing_registry = [plugin_id for plugin_id in installs if f"{plugin_id}.json" not in registry_files]
        if missing_registry:
            issues.append("Registry is missing entries for: " + ", ".join(missing_registry))

    if owner is not None and not owner.export_root.joinpath("metadata.json").exists():
        issues.append(
            f"Stored Claude canonical export metadata is missing: {owner.export_root / 'metadata.json'}. "
            f"Re-run `{paths.bootstrap_command}`."
        )

    details["issues"] = issues
    details["status"] = "ok" if not issues else "error"
    return details, 0 if not issues else 1


def status(paths: HelperPaths) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "config_path": str(paths.config_path),
        "state": helper_state(paths),
    }
    if paths.settings_path is not None:
        payload["settings_path"] = str(paths.settings_path)
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
    parser.add_argument("--cowork-home", type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_bootstrap_overrides(command: argparse.ArgumentParser) -> None:
        command.add_argument("--core-plugin-root", type=Path)
        command.add_argument("--core-plugin-data", type=Path)
        command.add_argument("--memory-plugin-root", type=Path)
        command.add_argument("--memory-plugin-data", type=Path)
        command.add_argument("--data-analysis-plugin-root", type=Path)
        command.add_argument("--data-analysis-plugin-data", type=Path)
        command.add_argument(
            "--plugin-root",
            action="append",
            default=[],
            help="Optional plugin root override in the form <plugin_id>=<path>.",
        )
        command.add_argument(
            "--plugin-data",
            action="append",
            default=[],
            help="Optional plugin data override in the form <plugin_id>=<path>.",
        )

    bootstrap_cmd = subparsers.add_parser("bootstrap")
    add_bootstrap_overrides(bootstrap_cmd)
    bootstrap_cowork_cmd = subparsers.add_parser("bootstrap-cowork")
    add_bootstrap_overrides(bootstrap_cowork_cmd)

    subparsers.add_parser("refresh-shared")
    subparsers.add_parser("refresh-cowork")
    subparsers.add_parser("doctor")
    subparsers.add_parser("doctor-cowork")
    subparsers.add_parser("status")
    subparsers.add_parser("status-cowork")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "bootstrap":
            paths = helper_paths(helper_home=args.helper_home, settings_path=args.settings_path, claude_home=args.claude_home)
            result = bootstrap(paths, args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "bootstrap-cowork":
            paths = cowork_helper_paths(helper_home=args.helper_home, cowork_home=args.cowork_home, claude_home=args.claude_home)
            result = bootstrap_cowork(paths, args)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "refresh-shared":
            paths = helper_paths(helper_home=args.helper_home, settings_path=args.settings_path, claude_home=args.claude_home)
            installs = load_installs_from_config(paths)
            result = refresh_shared_memory(paths, installs)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "refresh-cowork":
            paths = cowork_helper_paths(helper_home=args.helper_home, cowork_home=args.cowork_home, claude_home=args.claude_home)
            installs = load_installs_from_config(paths)
            owner = canonical_owner_from_cowork_config(paths)
            result = refresh_cowork_shared_memory(paths, installs, owner)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "doctor":
            paths = helper_paths(helper_home=args.helper_home, settings_path=args.settings_path, claude_home=args.claude_home)
            result, exit_code = doctor(paths)
            print(json.dumps(result, indent=2, sort_keys=True))
            return exit_code
        if args.command == "doctor-cowork":
            paths = cowork_helper_paths(helper_home=args.helper_home, cowork_home=args.cowork_home, claude_home=args.claude_home)
            result, exit_code = doctor_cowork(paths)
            print(json.dumps(result, indent=2, sort_keys=True))
            return exit_code
        if args.command == "status":
            paths = helper_paths(helper_home=args.helper_home, settings_path=args.settings_path, claude_home=args.claude_home)
            result = status(paths)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        paths = cowork_helper_paths(helper_home=args.helper_home, cowork_home=args.cowork_home, claude_home=args.claude_home)
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
