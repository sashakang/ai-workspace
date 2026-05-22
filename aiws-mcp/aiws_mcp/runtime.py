from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import tempfile
import uuid
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import skill_manager
from .builtins import BUILTIN_SKILLS, RESOURCES


NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
HOST_KINDS = {"claude-code", "cowork", "codex"}
AIWS_MANAGED_MARKER = ".aiws-managed.json"
AIWS_MANAGED_BY = "aiws"
AIWS_INSTALLED_BY = "aiws-mcp"
AIWS_MANAGED_SCHEMA_VERSION = 1


class SkillValidationError(ValueError):
    """Raised when an Agent Skills bundle is invalid."""


def surface_path_state(path: Path, kind: str, *, wants_writable: bool) -> dict[str, Any]:
    expanded = path.expanduser()
    exists = expanded.exists()
    payload: dict[str, Any] = {
        "exists": exists,
        "is_symlink": expanded.is_symlink(),
        "is_file": expanded.is_file() if exists else False,
        "is_directory": expanded.is_dir() if exists else False,
        "writable_effective": False,
    }
    if not exists:
        return payload
    if kind == "directory":
        payload["writable_effective"] = expanded.is_dir() and os.access(expanded, os.W_OK)
    elif kind in {"file", "jsonl"}:
        payload["writable_effective"] = expanded.is_file() and os.access(expanded, os.W_OK)
    else:
        payload["writable_effective"] = wants_writable and os.access(expanded, os.W_OK)
    return payload


@dataclass(frozen=True)
class HostEvidenceSurface:
    name: str
    kind: str
    path: Path | None = None
    resource_uri: str | None = None
    writable: bool = False
    required: bool = False

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "writable": self.writable,
            "required": self.required,
        }
        if self.path is not None:
            payload["path"] = str(self.path)
            payload.update(surface_path_state(self.path, self.kind, wants_writable=self.writable))
        if self.resource_uri is not None:
            payload["resource_uri"] = self.resource_uri
        return payload


@dataclass(frozen=True)
class HostAdapter:
    host_kind: str
    default_home_env: str
    default_home: str
    capability_exposure: str
    supports_direct_install: bool

    def default_config_root(self, env: dict[str, str]) -> Path:
        return Path(env.get(self.default_home_env, self.default_home)).expanduser().resolve()

    def evidence_surfaces(self, config_root: Path, aiws_root: Path, host_id: str) -> list[HostEvidenceSurface]:
        host_root = aiws_root / "hosts" / host_id
        common = [
            HostEvidenceSurface("host_identity", "file", host_root / "host.json", writable=True, required=True),
            HostEvidenceSurface("staged_skill_changes", "directory", host_root / "staged-writes" / "skills", writable=True),
            HostEvidenceSurface("materialized_skills", "directory", host_root / "shared-cache" / "skills", writable=True),
            HostEvidenceSurface("skill_adapter", "directory", host_root / "adapter", writable=True),
            HostEvidenceSurface("skill_catalog", "mcp-resource", resource_uri="aiws://skills"),
        ]
        if self.host_kind == "codex":
            return [
                *common,
                HostEvidenceSurface("session_history", "jsonl", config_root / "history.jsonl"),
                HostEvidenceSurface("installed_skills", "directory", config_root / "skills"),
            ]
        if self.host_kind == "claude-code":
            return [
                *common,
                HostEvidenceSurface("observations", "jsonl", config_root / "improve" / "observations.jsonl", writable=True),
                HostEvidenceSurface("project_daily_logs", "directory", config_root / "project-memory" / "current", writable=True),
                HostEvidenceSurface("installed_contracts", "directory", config_root / "registry" / "plugins"),
                HostEvidenceSurface("shared_memory_outbox", "directory", config_root / "shared-memory" / "outbox", writable=True),
            ]
        if self.host_kind == "cowork":
            return [
                *common,
                HostEvidenceSurface("installed_plugins", "directory", config_root / "plugins"),
                HostEvidenceSurface("package_uploads", "directory", config_root / "packages", writable=True),
            ]
        return common

    def capability_map(self) -> dict[str, Any]:
        return {
            "capability_exposure": self.capability_exposure,
            "direct_host_install_supported": self.supports_direct_install,
            "skill_adapter_supported": True,
        }


HOST_ADAPTERS = {
    "claude-code": HostAdapter(
        host_kind="claude-code",
        default_home_env="CLAUDE_HOME",
        default_home="~/.claude",
        capability_exposure="slash-command-or-skill",
        supports_direct_install=False,
    ),
    "cowork": HostAdapter(
        host_kind="cowork",
        default_home_env="COWORK_HOME",
        default_home="~/.cowork",
        capability_exposure="plugin-package",
        supports_direct_install=False,
    ),
    "codex": HostAdapter(
        host_kind="codex",
        default_home_env="CODEX_HOME",
        default_home="~/.codex",
        capability_exposure="skill",
        supports_direct_install=True,
    ),
}


@dataclass(frozen=True)
class HostIdentity:
    host_id: str
    host_kind: str
    config_root: Path


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    name: str
    description: str
    scope: str
    version: str
    source: str
    root: Path | None
    entrypoint_content: str | None
    supported_hosts: tuple[str, ...]
    materialized: bool = False
    downloadable: bool = True
    marketplace_id: str | None = None
    plugin_id: str | None = None

    def manifest(self) -> dict[str, Any]:
        payload = {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "version": self.version,
            "artifact_kind": "aiws-skill-bundle-v1",
            "entrypoint": "SKILL.md",
            "supported_hosts": list(self.supported_hosts),
            "required_tools": [],
            "artifact_ref": self.source,
            "integrity_hash": None,
            "scripts_supported": False,
        }
        if self.marketplace_id is not None:
            payload["marketplace_id"] = self.marketplace_id
        if self.plugin_id is not None:
            payload["plugin_id"] = self.plugin_id
        return payload

    def summary(self) -> dict[str, Any]:
        payload = {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "scope": self.scope,
            "version": self.version,
            "source": self.source,
            "supported_hosts": list(self.supported_hosts),
            "scripts_supported": False,
            "materialized": self.materialized,
        }
        if self.marketplace_id is not None:
            payload["marketplace_id"] = self.marketplace_id
        if self.plugin_id is not None:
            payload["plugin_id"] = self.plugin_id
        return payload


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text_atomic(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, path)


def write_json_atomic(path: Path, payload: Any) -> None:
    write_text_atomic(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text())


def parse_skill_markdown(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        raise SkillValidationError("SKILL.md must start with YAML frontmatter.")
    try:
        _, frontmatter, body = content.split("---", 2)
    except ValueError as exc:
        raise SkillValidationError("SKILL.md frontmatter is not closed.") from exc

    metadata: dict[str, str] = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise SkillValidationError(f"Invalid frontmatter line: {raw_line}")
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, body


def validate_skill_content(content: str, expected_name: str) -> dict[str, str]:
    metadata, _ = parse_skill_markdown(content)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if name != expected_name:
        raise SkillValidationError(f"Skill name {name!r} must match directory {expected_name!r}.")
    if not NAME_RE.fullmatch(name) or "--" in name:
        raise SkillValidationError("Skill name must be lowercase alphanumeric plus single hyphens.")
    if not (1 <= len(name) <= 64):
        raise SkillValidationError("Skill name must be 1-64 characters.")
    if not (1 <= len(description) <= 1024):
        raise SkillValidationError("Skill description must be 1-1024 characters.")
    return {"name": name, "description": description}


def validate_skill_dir(skill_root: Path) -> dict[str, str]:
    entrypoint = skill_root / "SKILL.md"
    if not entrypoint.exists() or not entrypoint.is_file():
        raise SkillValidationError(f"Missing SKILL.md: {skill_root}")
    return validate_skill_content(entrypoint.read_text(), skill_root.name)


def default_config_root(host_kind: str, env: dict[str, str]) -> Path:
    return host_adapter(host_kind).default_config_root(env)


def host_adapter(host_kind: str) -> HostAdapter:
    try:
        return HOST_ADAPTERS[host_kind]
    except KeyError as exc:
        raise ValueError(f"Unsupported host kind: {host_kind}") from exc


def derived_host_id(host_kind: str, config_root: Path) -> str:
    digest = hashlib.sha256(str(config_root).encode("utf-8")).hexdigest()[:12]
    return f"{host_kind}-{digest}"


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_skill_id_component(skill_id: str) -> None:
    if (
        not skill_id
        or skill_id in {".", ".."}
        or skill_id.startswith(".")
        or "/" in skill_id
        or "\\" in skill_id
        or Path(skill_id).is_absolute()
        or Path(skill_id).name != skill_id
        or not NAME_RE.fullmatch(skill_id)
        or "--" in skill_id
    ):
        raise SkillValidationError(f"Invalid skill id for host install: {skill_id!r}")


def validate_host_id_component(host_id: str) -> None:
    if (
        not host_id
        or host_id in {".", ".."}
        or host_id.startswith(".")
        or "/" in host_id
        or "\\" in host_id
        or Path(host_id).is_absolute()
        or Path(host_id).name != host_id
    ):
        raise ValueError(f"Invalid host_id: {host_id!r}")


def safe_copytree(source: Path, destination: Path) -> None:
    if source.is_symlink():
        raise ValueError(f"Skill bundle source must not be a symlink: {source}")
    if not source.is_dir():
        raise ValueError(f"Skill bundle source must be a directory: {source}")
    for item in source.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Symlinks are not allowed in skill bundles: {item}")
        if not is_relative_to(item.resolve(), source.resolve()):
            raise ValueError(f"Skill bundle path escapes its root: {item}")
    if source.resolve() == destination.resolve():
        return
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def bundle_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed in skill bundles: {path}")
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def tree_digest(root: Path, *, exclude_root_marker: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not allowed in skill bundles: {path}")
        relative_path = path.relative_to(root).as_posix()
        if exclude_root_marker and relative_path == AIWS_MANAGED_MARKER:
            continue
        relative = relative_path.encode("utf-8")
        if path.is_dir():
            digest.update(b"D")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            continue
        if path.is_file():
            content = path.read_bytes()
            digest.update(b"F")
            digest.update(len(relative).to_bytes(8, "big"))
            digest.update(relative)
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return "sha256:" + digest.hexdigest()


class AiwsRuntime:
    def __init__(self, root: Path | None = None, env: dict[str, str] | None = None) -> None:
        self.root = (root or Path("~/.aiws").expanduser()).resolve()
        self.env = dict(os.environ if env is None else env)

    def get_resource(self, uri: str) -> str:
        try:
            return RESOURCES[uri]
        except KeyError as exc:
            raise KeyError(f"Unknown AIWS resource: {uri}") from exc

    def ensure_host(
        self,
        *,
        host_kind: str | None = None,
        host_id: str | None = None,
        config_root: Path | None = None,
    ) -> HostIdentity:
        if host_kind is not None and host_kind not in HOST_KINDS:
            raise ValueError(f"Unsupported host kind: {host_kind}")
        if host_id is not None:
            validate_host_id_component(host_id)

        if host_id is None:
            if host_kind is None:
                raise ValueError("host_kind is required when host_id is omitted.")
            resolved_config_root = (config_root or default_config_root(host_kind, self.env)).resolve()
            host_id = derived_host_id(host_kind, resolved_config_root)
        host_root = self.root / "hosts" / host_id
        host_json = host_root / "host.json"

        if host_json.exists():
            payload = load_json(host_json, {})
            validate_host_id_component(payload["host_id"])
            if payload["host_id"] != host_id:
                raise ValueError("Stored host_id conflicts with host directory.")
            existing = HostIdentity(
                host_id=payload["host_id"],
                host_kind=payload["host_kind"],
                config_root=Path(payload["config_root"]),
            )
            if host_kind is not None and host_kind != existing.host_kind:
                raise ValueError("Supplied host_kind conflicts with existing host.json.")
            if "capabilities" not in payload or "evidence_surfaces" not in payload:
                write_json_atomic(host_json, self._host_json_payload(existing))
            return existing

        if host_kind is None:
            raise ValueError("host_kind is required for first registration of a host_id.")

        resolved_config_root = (config_root or default_config_root(host_kind, self.env)).resolve()
        host = HostIdentity(host_id=host_id, host_kind=host_kind, config_root=resolved_config_root)
        ensure_dir(host_root)
        write_json_atomic(
            host_json,
            self._host_json_payload(host),
        )
        return host

    def _host_json_payload(self, host: HostIdentity) -> dict[str, Any]:
        adapter = host_adapter(host.host_kind)
        return {
            "host_id": host.host_id,
            "host_kind": host.host_kind,
            "config_root": str(host.config_root),
            "capabilities": adapter.capability_map(),
            "evidence_surfaces": [
                surface.to_json()
                for surface in adapter.evidence_surfaces(host.config_root, self.root, host.host_id)
            ],
        }

    def host_surfaces(self, *, host_kind: str | None = None, host_id: str | None = None) -> dict[str, Any]:
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        payload = self._host_json_payload(host)
        return {
            "host_id": host.host_id,
            "host_kind": host.host_kind,
            "config_root": str(host.config_root),
            "capabilities": payload["capabilities"],
            "evidence_surfaces": payload["evidence_surfaces"],
        }

    def _cowork_package_upload_surface(self, host: HostIdentity) -> Path | None:
        if host.host_kind != "cowork":
            return None
        payload = self._host_json_payload(host)
        for surface in payload["evidence_surfaces"]:
            if surface.get("name") != "package_uploads":
                continue
            if (
                surface.get("kind") == "directory"
                and surface.get("writable") is True
                and surface.get("exists") is True
                and surface.get("is_symlink") is False
                and surface.get("is_directory") is True
                and surface.get("writable_effective") is True
            ):
                path = surface.get("path")
                if isinstance(path, str) and path:
                    return Path(path)
        return None

    def built_in_records(self) -> list[SkillRecord]:
        records = []
        for skill_id, content in BUILTIN_SKILLS.items():
            metadata = validate_skill_content(content, skill_id)
            records.append(
                SkillRecord(
                    skill_id=skill_id,
                    name=metadata["name"],
                    description=metadata["description"],
                    scope="bundled",
                    version="1.0.0",
                    source=f"builtin:{skill_id}",
                    root=None,
                    entrypoint_content=content,
                    supported_hosts=tuple(sorted(HOST_KINDS)),
                )
            )
        return records

    def personal_records(self) -> list[SkillRecord]:
        personal_root = self.root / "personal" / "skills"
        if not personal_root.exists():
            return []
        records = []
        for skill_root in sorted(item for item in personal_root.iterdir() if item.is_dir()):
            metadata = validate_skill_dir(skill_root)
            records.append(
                SkillRecord(
                    skill_id=skill_root.name,
                    name=metadata["name"],
                    description=metadata["description"],
                    scope="personal",
                    version="1.0.0",
                    source=str(skill_root),
                    root=skill_root,
                    entrypoint_content=None,
                    supported_hosts=tuple(sorted(HOST_KINDS)),
                )
            )
        return records

    def remote_fixture_records(self) -> list[SkillRecord]:
        fixture_root = self.root / "fixtures" / "remote-skills"
        if not fixture_root.exists():
            return []
        records = []
        for path in sorted(fixture_root.glob("*.json")):
            payload = load_json(path, {})
            records.append(
                SkillRecord(
                    skill_id=payload["skill_id"],
                    name=payload.get("name", payload["skill_id"]),
                    description=payload["description"],
                    scope=payload["scope"],
                    version=payload.get("version", "1.0.0"),
                    source=f"remote-fixture:{path.name}",
                    root=None,
                    entrypoint_content=None,
                    supported_hosts=tuple(payload.get("supported_hosts", sorted(HOST_KINDS))),
                    downloadable=False,
                )
            )
        return records

    def drive_published_records(self) -> list[SkillRecord]:
        registry = skill_manager.load_marketplace_registry(self.root)
        marketplaces = registry.get("marketplaces", {})
        if not isinstance(marketplaces, dict) or not marketplaces:
            return []
        token = skill_manager.google_drive_api_token(self.root, env=self.env)
        if token is None:
            return []
        client = skill_manager.GoogleDriveApiClient(token=token)
        records: list[SkillRecord] = []
        for marketplace_id in sorted(marketplaces):
            marketplace = marketplaces[marketplace_id]
            if not isinstance(marketplace, dict):
                continue
            if marketplace.get("backend_kind") != "google_drive":
                continue
            backend_ref = marketplace.get("backend_ref")
            scope_id = marketplace.get("scope_id")
            if not isinstance(backend_ref, str) or not backend_ref.strip():
                continue
            if not isinstance(scope_id, str) or not scope_id.strip():
                continue
            try:
                plugins_folder = client.find_child(
                    backend_ref.strip(),
                    "plugins",
                    mime_type="application/vnd.google-apps.folder",
                )
                if plugins_folder is None:
                    continue
                plugin_folders = client.list_children(
                    str(plugins_folder["id"]),
                    mime_type="application/vnd.google-apps.folder",
                )
                for plugin_folder in plugin_folders:
                    plugin_id = plugin_folder.get("name")
                    if not isinstance(plugin_id, str) or not plugin_id:
                        continue
                    index_payload = skill_manager.read_drive_json_file(client, str(plugin_folder["id"]), "index.json")
                    if index_payload is None:
                        continue
                    current_version = index_payload.get("current_version")
                    package_file_id = index_payload.get("package_file_id")
                    if not isinstance(current_version, str) or not current_version.strip():
                        continue
                    if not isinstance(package_file_id, str) or not package_file_id.strip():
                        continue
                    package_bytes = client.download_file_bytes(package_file_id.strip())
                    with zipfile.ZipFile(io.BytesIO(package_bytes)) as package:
                        for name in sorted(package.namelist()):
                            if not name.startswith("skills/") or not name.endswith("/SKILL.md"):
                                continue
                            parts = Path(name).parts
                            if len(parts) != 3:
                                continue
                            skill_id = parts[1]
                            content = package.read(name).decode("utf-8")
                            metadata = validate_skill_content(content, skill_id)
                            records.append(
                                SkillRecord(
                                    skill_id=skill_id,
                                    name=metadata["name"],
                                    description=metadata["description"],
                                    scope=scope_id.strip(),
                                    version=current_version.strip(),
                                    source=f"google-drive:{marketplace_id}:{plugin_id}:{package_file_id.strip()}",
                                    root=None,
                                    entrypoint_content=content,
                                    supported_hosts=tuple(sorted(HOST_KINDS)),
                                    marketplace_id=marketplace_id,
                                    plugin_id=plugin_id,
                                )
                            )
            except skill_manager.SkillManagerError:
                continue
        return records

    def materialized_records(self) -> list[SkillRecord]:
        records: list[SkillRecord] = []
        for skill_root in sorted((self.root / "hosts").glob("*/shared-cache/skills/*/*/*")):
            if not skill_root.is_dir():
                continue
            entrypoint = skill_root / "SKILL.md"
            if not entrypoint.exists():
                continue
            skill_id = skill_root.parent.name
            content = entrypoint.read_text()
            try:
                metadata = validate_skill_content(content, skill_id)
            except SkillValidationError:
                # Older MVP caches used <scope>/<version>/<skill-id>. Ignore those
                # generated artifacts instead of crashing catalog reads after upgrade.
                validate_skill_content(content, skill_root.name)
                continue
            manifest_payload = load_json(skill_root / ".aiws-skill-manifest.json", {})
            marketplace_id = manifest_payload.get("marketplace_id")
            plugin_id = manifest_payload.get("plugin_id")
            source = manifest_payload.get("artifact_ref")
            canonical_scope = manifest_payload.get("scope")
            scope = (
                canonical_scope
                if isinstance(canonical_scope, str) and canonical_scope.strip()
                else skill_root.parent.parent.name
            )
            records.append(
                SkillRecord(
                    skill_id=skill_id,
                    name=metadata["name"],
                    description=metadata["description"],
                    scope=scope,
                    version=skill_root.name,
                    source=source if isinstance(source, str) and source else str(skill_root),
                    root=skill_root,
                    entrypoint_content=None,
                    supported_hosts=tuple(sorted(HOST_KINDS)),
                    materialized=True,
                    marketplace_id=marketplace_id if isinstance(marketplace_id, str) and marketplace_id else None,
                    plugin_id=plugin_id if isinstance(plugin_id, str) and plugin_id else None,
                )
            )
        return records

    def catalog_records(self) -> list[SkillRecord]:
        materialized = self.materialized_records()
        materialized_ids = {record.skill_id for record in materialized}
        built_ins = [
            record
            for record in self.built_in_records()
            if record.skill_id not in materialized_ids
        ]
        return [
            *built_ins,
            *self.personal_records(),
            *materialized,
            *self.remote_fixture_records(),
            *self.drive_published_records(),
        ]

    def _dedupe_display_records(self, records: list[SkillRecord]) -> list[SkillRecord]:
        deduped: dict[tuple[str, str, str, str, str], SkillRecord] = {}
        for record in records:
            key = (
                record.marketplace_id or "",
                record.plugin_id or "",
                record.skill_id,
                record.version,
                record.scope,
            )
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = record
                continue
            materialized = existing.materialized or record.materialized
            preferred = existing
            if (
                not record.materialized
                and record.source.startswith("google-drive:")
                and existing.materialized
            ):
                preferred = record
            if preferred.materialized != materialized:
                preferred = replace(preferred, materialized=materialized)
            deduped[key] = preferred
        return list(deduped.values())

    def _version_sort_key(self, version: str) -> tuple[tuple[int, Any], ...]:
        parts: list[tuple[int, Any]] = []
        for part in re.split(r"([0-9]+)", version):
            if not part:
                continue
            parts.append((1, int(part)) if part.isdigit() else (0, part))
        return tuple(parts)

    def _latest_display_records(self, records: list[SkillRecord]) -> list[SkillRecord]:
        latest: dict[tuple[str, str, str, str], SkillRecord] = {}
        for record in records:
            key = (
                record.marketplace_id or "",
                record.plugin_id or "",
                record.skill_id,
                record.scope,
            )
            existing = latest.get(key)
            if existing is None or self._version_sort_key(record.version) > self._version_sort_key(existing.version):
                latest[key] = record
                continue
            if record.version == existing.version and record.materialized and not existing.materialized:
                latest[key] = record
        return list(latest.values())

    def search_skills(
        self,
        *,
        query: str | None = None,
        scopes: list[str] | None = None,
        marketplace_id: str | None = None,
        host_kind: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        records = self.catalog_records()
        if query:
            needle = query.lower()
            records = [
                record
                for record in records
                if needle in record.skill_id.lower() or needle in record.description.lower()
            ]
        if scopes:
            records = [record for record in records if record.scope in scopes]
        if marketplace_id:
            records = [record for record in records if record.marketplace_id == marketplace_id]
        if host_kind:
            records = [record for record in records if host_kind in record.supported_hosts]
        records = self._dedupe_display_records(records)
        records = records[:limit] if limit is not None else records
        return {"results": [record.summary() for record in records]}

    def list_local_skills(self, scope: str | None = None, host_kind: str | None = None) -> dict[str, Any]:
        records = [
            record
            for record in self.catalog_records()
            if record.scope in {"personal", "bundled"} or record.materialized
        ]
        if scope:
            records = [record for record in records if record.scope == scope]
        if host_kind:
            records = [record for record in records if host_kind in record.supported_hosts]
        return {"skills": [record.summary() for record in records]}

    def resolve_skill(
        self,
        skill_id: str,
        *,
        scope: str | None = None,
        marketplace_id: str | None = None,
        version: str | None = None,
        host_kind: str | None = None,
    ) -> dict[str, Any]:
        records = [record for record in self.catalog_records() if record.skill_id == skill_id]
        if scope:
            records = [record for record in records if record.scope == scope]
        if marketplace_id:
            records = [record for record in records if record.marketplace_id == marketplace_id]
        if version:
            records = [record for record in records if record.version == version]
        if host_kind:
            records = [record for record in records if host_kind in record.supported_hosts]
        if not records:
            return {"status": "not_found", "reason": f"No skill found for {skill_id}."}
        if marketplace_id and version is None:
            marketplace_published = [
                record
                for record in records
                if record.marketplace_id == marketplace_id
                and not record.materialized
                and record.source.startswith("google-drive:")
            ]
            if marketplace_published:
                records = marketplace_published
        unique: dict[tuple[str, str], SkillRecord] = {}
        for record in records:
            key = (record.marketplace_id or "", record.scope, record.version)
            existing = unique.get(key)
            if existing is None or (record.materialized and not existing.materialized):
                unique[key] = record
        records = list(unique.values())
        if len(records) > 1 and not (scope or marketplace_id or version):
            return {"status": "ambiguous", "candidates": [record.summary() for record in records]}
        return {"status": "ok", "manifest": records[0].manifest()}

    def get_skill(
        self,
        skill_id: str,
        *,
        scope: str | None = None,
        marketplace_id: str | None = None,
        version: str | None = None,
        include_content: bool = False,
    ) -> dict[str, Any]:
        resolved = self.resolve_skill(skill_id, scope=scope, marketplace_id=marketplace_id, version=version)
        if resolved["status"] != "ok":
            return resolved
        record = self._record_from_manifest(resolved["manifest"])
        payload: dict[str, Any] = {"manifest": record.manifest()}
        if include_content:
            payload["entrypoint_content"] = self._entrypoint_content(record)
            payload["references"] = self._references(record)
        return payload

    def _record_from_manifest(self, manifest: dict[str, Any]) -> SkillRecord:
        for record in self.catalog_records():
            if record.skill_id != manifest["skill_id"]:
                continue
            if record.scope != manifest["scope"] or record.version != manifest["version"]:
                continue
            if "marketplace_id" in manifest and record.marketplace_id != manifest.get("marketplace_id"):
                continue
            if "plugin_id" in manifest and record.plugin_id != manifest.get("plugin_id"):
                continue
            return record
        raise KeyError(f"Manifest no longer resolves: {manifest['skill_id']}")

    def _entrypoint_content(self, record: SkillRecord) -> str | None:
        if record.entrypoint_content is not None:
            return record.entrypoint_content
        if record.root is None:
            return None
        return (record.root / "SKILL.md").read_text()

    def _references(self, record: SkillRecord) -> list[str]:
        if record.root is None:
            return []
        references_root = record.root / "references"
        if not references_root.exists():
            return []
        return [
            str(path.relative_to(record.root))
            for path in sorted(references_root.rglob("*"))
            if path.is_file()
        ]

    def _materialize_google_drive_skill(self, record: SkillRecord, target_root: Path, plugin_root: Path | None = None) -> None:
        parts = record.source.split(":")
        if len(parts) != 4 or parts[0] != "google-drive":
            raise ValueError(f"Unsupported Google Drive artifact ref: {record.source}")
        _prefix, _marketplace_id, _plugin_id, package_file_id = parts
        token = skill_manager.google_drive_api_token(self.root, env=self.env)
        if token is None:
            raise ValueError("Google Drive credentials are not configured for package download.")
        client = skill_manager.GoogleDriveApiClient(token=token)
        package_bytes = client.download_file_bytes(package_file_id)
        skill_prefix = f"skills/{record.skill_id}/"
        if target_root.exists():
            shutil.rmtree(target_root)
        ensure_dir(target_root)
        if plugin_root is not None:
            if plugin_root.exists():
                shutil.rmtree(plugin_root)
            ensure_dir(plugin_root)
        extracted = False
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as package:
            for info in package.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"Unsafe Google Drive package entry: {name}")
                if plugin_root is not None:
                    plugin_destination = plugin_root / name
                    ensure_dir(plugin_destination.parent)
                    with package.open(info) as source, plugin_destination.open("wb") as handle:
                        shutil.copyfileobj(source, handle)
                if name.startswith(skill_prefix):
                    relative = name.removeprefix(skill_prefix)
                    if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                        raise ValueError(f"Unsafe Google Drive package entry: {name}")
                    destination = target_root / relative
                    ensure_dir(destination.parent)
                    with package.open(info) as source, destination.open("wb") as handle:
                        shutil.copyfileobj(source, handle)
                    extracted = True
        if not extracted:
            raise ValueError(f"Google Drive package does not contain skills/{record.skill_id}/")
        entrypoint = target_root / "SKILL.md"
        if not entrypoint.is_file():
            raise ValueError(f"Google Drive package does not contain skills/{record.skill_id}/SKILL.md")
        validate_skill_content(entrypoint.read_text(), record.skill_id)
        write_json_atomic(target_root / ".aiws-skill-manifest.json", record.manifest())
        if plugin_root is not None and record.plugin_id is not None:
            manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
            if not manifest_path.exists():
                write_json_atomic(
                    manifest_path,
                    {
                        "name": record.plugin_id,
                        "description": f"Materialized Google Drive plugin {record.plugin_id}.",
                        "version": record.version,
                    },
                )
            skill_manager.validate_plugin(plugin_root, expected_name=record.plugin_id)

    def materialize_skill(
        self,
        *,
        skill_id: str,
        host_kind: str | None = None,
        host_id: str | None = None,
        scope: str | None = None,
        marketplace_id: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        resolved = self.resolve_skill(
            skill_id,
            scope=scope,
            marketplace_id=marketplace_id,
            version=version,
            host_kind=host.host_kind,
        )
        if resolved["status"] != "ok":
            return resolved
        record = self._record_from_manifest(resolved["manifest"])
        if not record.downloadable:
            return {"status": "unavailable", "reason": "Remote fixture records are metadata-only in MVP."}

        cache_root = self.root / "hosts" / host.host_id / "shared-cache" / "skills"
        target_root = cache_root / self._safe_scope(record.scope) / record.skill_id / record.version
        ensure_dir(target_root.parent)
        plugin_root = self._drive_plugin_cache_root(host, record)

        if record.root is not None:
            safe_copytree(record.root, target_root)
        elif record.source.startswith("google-drive:"):
            self._materialize_google_drive_skill(record, target_root, plugin_root=plugin_root)
        else:
            if target_root.exists():
                shutil.rmtree(target_root)
            ensure_dir(target_root)
            write_text_atomic(target_root / "SKILL.md", record.entrypoint_content or "")
            write_json_atomic(target_root / ".aiws-skill-manifest.json", record.manifest())

        integrity_hash = bundle_digest(target_root)
        adapter_root = self.root / "hosts" / host.host_id / "adapter"
        self._write_adapter(host.host_kind, adapter_root, target_root, record)
        verified_hash = bundle_digest(target_root)
        if verified_hash != integrity_hash:
            raise ValueError("Skill integrity changed during materialization.")

        manifest = record.manifest()
        manifest["integrity_hash"] = integrity_hash
        return {
            "status": "materialized",
            "manifest": manifest,
            "cache_path": str(target_root),
            "adapter_path": str(adapter_root),
            "plugin_cache_path": str(plugin_root) if plugin_root is not None else None,
            "integrity_hash": integrity_hash,
        }

    def install_host(
        self,
        *,
        host_kind: str,
        host_id: str | None = None,
        config_root: Path | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        if host_kind not in {"codex", "cowork"}:
            raise ValueError("install-host currently supports only host_kind='codex' or host_kind='cowork'.")
        if host_id is not None:
            validate_host_id_component(host_id)

        host = self._resolve_host_for_install(
            host_kind=host_kind,
            host_id=host_id,
            config_root=(config_root.resolve() if config_root is not None else None),
            dry_run=True,
        )
        resolved_config_root = host.config_root
        host_root = self.root / "hosts" / host.host_id
        hosts_root = self.root / "hosts"
        adapter_root = host_root / "adapter"
        if host_kind == "cowork":
            default_plugin_root = adapter_root / "aiws-generated-plugin"
            plugin_root = default_plugin_root
            package_output_dir = host_root / "package-output"
            package_upload_dir = self._cowork_package_upload_surface(host)
            declared_package_upload_dir = resolved_config_root / "packages"
            result: dict[str, Any] = {
                "status": "ok",
                "host_id": host.host_id,
                "host_kind": host_kind,
                "plugin_root": str(plugin_root),
                "package_output_dir": str(package_output_dir),
                "package_upload_surface": str(package_upload_dir or declared_package_upload_dir),
                "package_path": None,
                "copied_package_path": None,
                "planned_writes": [],
                "write_paths": [],
                "errors": [],
                "requires_cowork_confirmation": False,
                "requires_manual_upload": False,
                "activation_effective": False,
                "dry_run": dry_run,
            }
            if hosts_root.is_symlink() or host_root.is_symlink():
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(host_root),
                        "reason": "AIWS host path must not contain symlinks.",
                    }
                ]
                return result
            host_root_resolved = host_root.resolve() if host_root.exists() else host_root.absolute()
            if host_root.exists() and not is_relative_to(host_root_resolved, self.root):
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(host_root),
                        "reason": "AIWS host root escapes AIWS runtime root.",
                    }
                ]
                return result
            if adapter_root.is_symlink() or default_plugin_root.is_symlink():
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(default_plugin_root),
                        "reason": "Cowork adapter plugin path must not contain symlinks.",
                    }
                ]
                return result
            if adapter_root.exists() and not is_relative_to(adapter_root.resolve(), host_root_resolved):
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(adapter_root),
                        "reason": "Adapter root escapes AIWS host root.",
                    }
                ]
                return result
            if not default_plugin_root.exists() and adapter_root.is_dir():
                plugin_roots = sorted(
                    child
                    for child in adapter_root.iterdir()
                    if child.is_dir() and (child / ".claude-plugin" / "plugin.json").is_file()
                )
                if len(plugin_roots) == 1:
                    plugin_root = plugin_roots[0]
                    result["plugin_root"] = str(plugin_root)
                elif len(plugin_roots) > 1:
                    result["status"] = "multiple_adapter_plugins"
                    result["errors"] = [
                        {
                            "path": str(adapter_root),
                            "reason": "Cowork adapter contains multiple plugin roots; install one at a time.",
                        }
                    ]
                    return result
            if plugin_root.is_symlink():
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(plugin_root),
                        "reason": "Cowork adapter plugin path must not contain symlinks.",
                    }
                ]
                return result
            if not plugin_root.exists():
                result["status"] = "no_skills"
                return result
            manifest = load_json(plugin_root / ".claude-plugin" / "plugin.json", {})
            package_name = manifest.get("name")
            if not isinstance(package_name, str) or not package_name.strip():
                result["status"] = "failed"
                result["errors"] = [
                    {
                        "path": str(plugin_root / ".claude-plugin" / "plugin.json"),
                        "reason": "Cowork adapter plugin manifest name is invalid.",
                    }
                ]
                return result
            planned_package_path = package_output_dir / f"{package_name.strip()}.zip"
            result["planned_writes"] = [str(planned_package_path)]
            if package_upload_dir is not None:
                result["planned_writes"].append(str(package_upload_dir / planned_package_path.name))
            if dry_run:
                result["status"] = "planned"
                result["requires_cowork_confirmation"] = package_upload_dir is not None
                result["requires_manual_upload"] = package_upload_dir is None
                return result

            host = self._resolve_host_for_install(
                host_kind=host_kind,
                host_id=host_id,
                config_root=resolved_config_root,
                dry_run=False,
            )
            package_path = self._build_cowork_adapter_package(
                plugin_root=plugin_root,
                package_output_dir=package_output_dir,
            )
            result["package_path"] = str(package_path)
            result["write_paths"].append(str(package_path))
            if package_upload_dir is not None:
                handoff = skill_manager.copy_package_to_upload_surface(package_path, package_upload_dir)
                result["status"] = "handoff_prepared"
                result["package_upload_surface"] = handoff["package_upload_surface"]
                result["copied_package_path"] = handoff["copied_package_path"]
                result["write_paths"].append(handoff["copied_package_path"])
                result["requires_cowork_confirmation"] = True
                return result
            result["status"] = "host_capability_missing"
            result["requires_manual_upload"] = True
            return result

        adapter_skills_root = adapter_root / "skills"
        skills_root = resolved_config_root / "skills"

        result: dict[str, Any] = {
            "status": "ok",
            "host_id": host.host_id,
            "codex_skills_root": str(skills_root),
            "adapter_skills_root": str(adapter_skills_root),
            "installed": [],
            "unchanged": [],
            "conflicts": [],
            "errors": [],
            "planned_writes": [],
            "write_paths": [],
            "stale_aiws_managed": [],
            "restart_required": False,
            "dry_run": dry_run,
        }

        if not is_relative_to(skills_root.absolute(), resolved_config_root.absolute()) or skills_root.is_symlink():
            return {
                **result,
                "status": "conflict",
                "conflicts": [
                    {
                        "path": str(skills_root),
                        "reason": "Codex skills root is a symlink.",
                    }
                ],
            }

        if hosts_root.is_symlink() or host_root.is_symlink():
            result["status"] = "failed"
            result["errors"] = [
                {
                    "path": str(host_root),
                    "reason": "AIWS host path must not contain symlinks.",
                }
            ]
            return result
        host_root_resolved = host_root.resolve() if host_root.exists() else host_root.absolute()
        if host_root.exists() and not is_relative_to(host_root_resolved, self.root):
            result["status"] = "failed"
            result["errors"] = [
                {
                    "path": str(host_root),
                    "reason": "AIWS host root escapes AIWS runtime root.",
                }
            ]
            return result
        if adapter_root.is_symlink() or adapter_skills_root.is_symlink():
            result["status"] = "failed"
            result["errors"] = [
                {
                    "path": str(adapter_skills_root),
                    "reason": "Adapter skills path must not contain symlinks.",
                }
            ]
            return result
        if adapter_root.exists() and not is_relative_to(adapter_root.resolve(), host_root_resolved):
            result["status"] = "failed"
            result["errors"] = [
                {
                    "path": str(adapter_root),
                    "reason": "Adapter root escapes AIWS host root.",
                }
            ]
            return result
        if adapter_skills_root.exists() and not is_relative_to(adapter_skills_root.resolve(), host_root_resolved):
            result["status"] = "failed"
            result["errors"] = [
                {
                    "path": str(adapter_skills_root),
                    "reason": "Adapter skills root escapes AIWS host root.",
                }
            ]
            return result

        actions = self._codex_install_actions(
            host=host,
            adapter_skills_root=adapter_skills_root,
            skills_root=skills_root,
        )
        result["stale_aiws_managed"] = actions["stale_aiws_managed"]
        result["unchanged"] = actions["unchanged"]
        result["conflicts"] = actions["conflicts"]
        result["planned_writes"] = actions["planned_writes"]

        if actions["errors"]:
            result["status"] = "failed"
            result["errors"] = actions["errors"]
            return result
        if actions["conflicts"]:
            result["status"] = "conflict"
            return result
        if not actions["install"]:
            result["status"] = "unchanged" if actions["unchanged"] else "no_skills"
            if not dry_run and host_id is not None:
                self._resolve_host_for_install(
                    host_kind=host_kind,
                    host_id=host_id,
                    config_root=resolved_config_root,
                    dry_run=False,
                )
            return result
        if dry_run:
            result["status"] = "planned"
            result["restart_required"] = bool(actions["install"])
            return result

        if host_id is not None:
            validate_host_id_component(host_id)
        host = self._resolve_host_for_install(
            host_kind=host_kind,
            host_id=host_id,
            config_root=resolved_config_root,
            dry_run=False,
        )
        ensure_dir(skills_root)
        if skills_root.is_symlink() or not is_relative_to(skills_root.resolve(), resolved_config_root.resolve()):
            result["status"] = "conflict"
            result["conflicts"].append(
                {
                    "path": str(skills_root),
                    "reason": "Codex skills root changed to an unsafe path before install.",
                }
            )
            return result
        for action in actions["install"]:
            try:
                self._install_codex_skill(
                    source=Path(action["source_path"]),
                    target=Path(action["target_path"]),
                    marker=action["marker"],
                )
            except Exception as exc:  # pragma: no cover - hard to trigger without platform-specific faults
                result["status"] = "failed"
                result["errors"].append(
                    {
                        "skill_id": action["skill_id"],
                        "path": action["target_path"],
                        "reason": str(exc),
                    }
                )
                return result
            result["installed"].append(action["skill_id"])
            result["write_paths"].append(action["target_path"])

        result["restart_required"] = bool(result["installed"])
        return result

    def _resolve_host_for_install(
        self,
        *,
        host_kind: str,
        host_id: str | None,
        config_root: Path | None,
        dry_run: bool,
    ) -> HostIdentity:
        resolved_config_root = (config_root or default_config_root(host_kind, self.env)).resolve()
        if host_id is None:
            if dry_run:
                return HostIdentity(
                    host_id=derived_host_id(host_kind, resolved_config_root),
                    host_kind=host_kind,
                    config_root=resolved_config_root,
                )
            return self.ensure_host(host_kind=host_kind, config_root=resolved_config_root)

        validate_host_id_component(host_id)
        host_json = self.root / "hosts" / host_id / "host.json"
        if host_json.exists():
            payload = load_json(host_json, {})
            validate_host_id_component(payload["host_id"])
            if payload["host_id"] != host_id:
                raise ValueError("Stored host_id conflicts with host directory.")
            existing = HostIdentity(
                host_id=payload["host_id"],
                host_kind=payload["host_kind"],
                config_root=Path(payload["config_root"]).resolve(),
            )
            if existing.host_kind != host_kind:
                raise ValueError("Supplied host_kind conflicts with existing host.json.")
            if config_root is not None and existing.config_root != resolved_config_root:
                raise ValueError("Supplied config_root conflicts with existing host.json.")
            if not dry_run and ("capabilities" not in payload or "evidence_surfaces" not in payload):
                write_json_atomic(host_json, self._host_json_payload(existing))
            return existing

        if dry_run:
            return HostIdentity(host_id=host_id, host_kind=host_kind, config_root=resolved_config_root)
        return self.ensure_host(host_kind=host_kind, host_id=host_id, config_root=resolved_config_root)

    def _codex_install_actions(
        self,
        *,
        host: HostIdentity,
        adapter_skills_root: Path,
        skills_root: Path,
    ) -> dict[str, Any]:
        actions: dict[str, Any] = {
            "install": [],
            "unchanged": [],
            "conflicts": [],
            "errors": [],
            "planned_writes": [],
            "stale_aiws_managed": [],
        }
        source_skill_ids: set[str] = set()

        adapter_root = adapter_skills_root.parent
        manifest_path = adapter_root / "aiws-codex-export.json"
        adapter_skills_root_resolved = adapter_skills_root.resolve() if adapter_skills_root.exists() else adapter_skills_root.absolute()
        if manifest_path.is_symlink():
            actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest is a symlink."})
        if manifest_path.exists() and not is_relative_to(manifest_path.resolve(), adapter_root.resolve()):
            actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest escapes adapter root."})
        if adapter_skills_root.exists() and not adapter_skills_root.is_dir():
            actions["errors"].append({"path": str(adapter_skills_root), "reason": "Adapter skills path is not a directory."})
        elif manifest_path.exists() and manifest_path.is_file():
            try:
                manifest = load_json(manifest_path, {"skills": []})
            except json.JSONDecodeError as exc:
                actions["errors"].append({"path": str(manifest_path), "reason": str(exc)})
                manifest = {"skills": []}
            if not isinstance(manifest, dict):
                actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest must be a JSON object."})
                manifest = {"skills": []}
            manifest_skills = manifest.get("skills", [])
            if not isinstance(manifest_skills, list):
                actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest skills must be a list."})
                manifest_skills = []
            seen_skill_ids: set[str] = set()
            for item in manifest_skills:
                if not isinstance(item, dict):
                    actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest skill entries must be objects."})
                    continue
                skill_id = item.get("skill_id", "")
                relative_source = item.get("path", "")
                if not isinstance(skill_id, str) or not isinstance(relative_source, str):
                    actions["errors"].append({"path": str(manifest_path), "reason": "Codex adapter manifest skill_id and path must be strings."})
                    continue
                try:
                    validate_skill_id_component(skill_id)
                except SkillValidationError as exc:
                    actions["errors"].append({"skill_id": skill_id, "path": str(manifest_path), "reason": str(exc)})
                    continue
                if skill_id in seen_skill_ids:
                    actions["errors"].append({"skill_id": skill_id, "path": str(manifest_path), "reason": "Duplicate skill id in Codex adapter manifest."})
                    continue
                seen_skill_ids.add(skill_id)
                if (
                    not relative_source
                    or Path(relative_source).is_absolute()
                    or "\\" in relative_source
                    or ".." in Path(relative_source).parts
                    or relative_source != f"skills/{skill_id}"
                ):
                    actions["errors"].append({"skill_id": skill_id, "path": relative_source, "reason": "Invalid Codex adapter manifest path."})
                    continue
                source = adapter_root / relative_source
                if source.is_symlink():
                    actions["errors"].append({"skill_id": skill_id, "path": str(source), "reason": "Source skill is a symlink."})
                    continue
                if not source.exists() or not source.is_dir():
                    actions["errors"].append({"skill_id": skill_id, "path": str(source), "reason": "Manifest source skill is missing."})
                    continue
                source_resolved = source.resolve()
                if not is_relative_to(source_resolved, adapter_skills_root_resolved):
                    actions["errors"].append({"skill_id": skill_id, "path": str(source), "reason": "Source path escapes adapter root."})
                    continue
                target = skills_root / skill_id
                target_resolved = target.resolve() if target.exists() else target.absolute()
                skills_root_resolved = skills_root.resolve() if skills_root.exists() else skills_root.absolute()
                if not is_relative_to(target_resolved, skills_root_resolved):
                    actions["errors"].append({"skill_id": skill_id, "path": str(target), "reason": "Target path escapes Codex skills root."})
                    continue

                source_skill_ids.add(skill_id)
                try:
                    source_digest = tree_digest(source_resolved, exclude_root_marker=True)
                except ValueError as exc:
                    actions["errors"].append({"skill_id": skill_id, "path": str(source), "reason": str(exc)})
                    continue

                marker = {
                    "host_id": host.host_id,
                    "installed_by": AIWS_INSTALLED_BY,
                    "managed_by": AIWS_MANAGED_BY,
                    "schema_version": AIWS_MANAGED_SCHEMA_VERSION,
                    "skill_id": skill_id,
                    "source_adapter_path": str(source_resolved),
                    "source_digest": source_digest,
                }
                existing_marker = self._codex_target_marker(target)
                if target.is_symlink():
                    actions["conflicts"].append({"skill_id": skill_id, "path": str(target), "reason": "Target skill path is a symlink."})
                    continue
                if target.exists() and not self._valid_codex_marker(existing_marker, skill_id, host.host_id):
                    actions["conflicts"].append({"skill_id": skill_id, "path": str(target), "reason": "Target is not AIWS-owned by this host."})
                    continue
                if target.exists() and existing_marker == marker:
                    try:
                        target_digest = tree_digest(target, exclude_root_marker=True)
                    except ValueError as exc:
                        actions["conflicts"].append({"skill_id": skill_id, "path": str(target), "reason": str(exc)})
                        continue
                    if target_digest == source_digest:
                        actions["unchanged"].append(skill_id)
                        continue

                action = {
                    "skill_id": skill_id,
                    "source_path": str(source_resolved),
                    "target_path": str(target),
                    "marker": marker,
                }
                actions["install"].append(action)
                actions["planned_writes"].append(str(target))

        if skills_root.exists() and skills_root.is_dir() and not skills_root.is_symlink():
            for target in sorted(item for item in skills_root.iterdir() if item.is_dir() and not item.is_symlink()):
                marker = self._codex_target_marker(target)
                skill_id = marker.get("skill_id")
                if (
                    marker.get("managed_by") == AIWS_MANAGED_BY
                    and marker.get("installed_by") == AIWS_INSTALLED_BY
                    and marker.get("schema_version") == AIWS_MANAGED_SCHEMA_VERSION
                    and marker.get("host_id") == host.host_id
                    and skill_id not in source_skill_ids
                ):
                    actions["stale_aiws_managed"].append(str(target))

        return actions

    def _codex_target_marker(self, target: Path) -> dict[str, Any]:
        marker_path = target / AIWS_MANAGED_MARKER
        if marker_path.is_symlink() or not marker_path.exists() or not marker_path.is_file():
            return {}
        try:
            return load_json(marker_path, {})
        except json.JSONDecodeError:
            return {}

    def _valid_codex_marker(self, marker: dict[str, Any], skill_id: str, host_id: str) -> bool:
        return (
            marker.get("managed_by") == AIWS_MANAGED_BY
            and marker.get("installed_by") == AIWS_INSTALLED_BY
            and marker.get("schema_version") == AIWS_MANAGED_SCHEMA_VERSION
            and marker.get("skill_id") == skill_id
            and marker.get("host_id") == host_id
        )

    def _install_codex_skill(self, *, source: Path, target: Path, marker: dict[str, Any]) -> None:
        skills_root = target.parent
        temp = skills_root / f".{target.name}.aiws-tmp-{uuid.uuid4().hex}"
        backup = skills_root / f".{target.name}.aiws-backup-{uuid.uuid4().hex}"
        try:
            self._assert_safe_codex_target(target, marker)
            safe_copytree(source, temp)
            marker = dict(marker)
            marker["source_digest"] = tree_digest(temp, exclude_root_marker=True)
            write_json_atomic(temp / AIWS_MANAGED_MARKER, marker)
            self._assert_safe_codex_target(target, marker)
            if target.exists():
                target.rename(backup)
                try:
                    temp.rename(target)
                except Exception:
                    if not target.exists() and backup.exists():
                        backup.rename(target)
                    raise
                shutil.rmtree(backup)
            else:
                temp.rename(target)
        except Exception:
            if temp.exists() or temp.is_symlink():
                if temp.is_dir() and not temp.is_symlink():
                    shutil.rmtree(temp)
                else:
                    temp.unlink()
            raise

    def _assert_safe_codex_target(self, target: Path, marker: dict[str, Any]) -> None:
        skills_root = target.parent
        if skills_root.is_symlink():
            raise ValueError("Codex skills root is a symlink.")
        skills_root_resolved = skills_root.resolve()
        target_resolved = target.resolve() if target.exists() else target.absolute()
        if not is_relative_to(target_resolved, skills_root_resolved):
            raise ValueError("Target path escapes Codex skills root.")
        if target.is_symlink():
            raise ValueError("Target skill path is a symlink.")
        if target.exists() and not self._valid_codex_marker(
            self._codex_target_marker(target),
            marker["skill_id"],
            marker["host_id"],
        ):
            raise ValueError("Target is not AIWS-owned by this host.")

    def _safe_scope(self, scope: str) -> str:
        return scope.replace(":", "_").replace("/", "_")

    def _safe_cache_component(self, value: str) -> str:
        return value.replace(":", "_").replace("/", "_")

    def _display_label(self, value: str) -> str:
        overrides = {
            "meeting-followup": "Meeting Follow-up",
        }
        if value in overrides:
            return overrides[value]
        return value.replace("-", " ").title()

    def _drive_workflow_actions(
        self,
        record: SkillRecord,
        *,
        host_kind: str,
        skill_display_name: str,
        is_current_version: bool,
        backend_ref: str | None,
    ) -> list[dict[str, Any]]:
        marketplace_id = record.marketplace_id
        plugin_id = record.plugin_id
        if marketplace_id is None or plugin_id is None:
            return []
        draft_id_template = f"{plugin_id}--{record.skill_id}--<hash>"
        proposal_id_template = "skillprop_<id>"
        base_identity = {
            "marketplace_id": marketplace_id,
            "plugin_id": plugin_id,
            "skill_id": record.skill_id,
        }
        return [
            {
                "id": "materialize_skill",
                "label": f"Materialize {skill_display_name}",
                "tool": "aiws.skills.materialize",
                "args": {
                    "marketplace_id": marketplace_id,
                    "skill_id": record.skill_id,
                    "host_kind": host_kind,
                    "version": record.version,
                },
                "mutates_state": True,
                "enabled": True,
            },
            {
                "id": "open_draft",
                "label": f"Open draft for {skill_display_name}",
                "tool": "aiws.skills.create_or_open_draft",
                "args": {
                    **base_identity,
                    "target_repo": marketplace_id,
                    "origin_marketplace": marketplace_id,
                    "origin_ref": marketplace_id,
                    "base_version": record.version,
                    "base_commit": record.source,
                },
                "mutates_state": True,
                "enabled": record.materialized,
                "requires": [] if record.materialized else ["materialize_skill"],
            },
            {
                "id": "validate_draft",
                "label": "Validate draft identity",
                "tool": "aiws.skills.validate_draft",
                "args_template": {
                    "draft_id": draft_id_template,
                    "expected_plugin_id": plugin_id,
                    "expected_marketplace_id": marketplace_id,
                },
                "mutates_state": False,
                "enabled": True,
                "requires": ["open_draft"],
            },
            {
                "id": "stage_proposal",
                "label": "Stage Google Drive proposal",
                "tool": "aiws.skills.stage_proposal",
                "args_template": {
                    "draft_id": draft_id_template,
                    "target_repo": marketplace_id,
                    "summary": f"Update {skill_display_name}.",
                    "rationale": "Proposed through the AIWS Google Drive marketplace workflow.",
                    "backend_kind": "google_drive",
                    "backend_ref": backend_ref,
                    "marketplace_id": marketplace_id,
                },
                "mutates_state": True,
                "enabled": True,
                "requires": ["validate_draft"],
            },
            {
                "id": "submit_for_review",
                "label": "Submit proposal for review",
                "tool": "aiws.skills.submit_for_review",
                "args_template": {
                    "proposal_id": proposal_id_template,
                },
                "mutates_state": True,
                "enabled": True,
                "requires": ["stage_proposal"],
            },
            {
                "id": "refresh_proposal_state",
                "label": "Refresh review state",
                "tool": "aiws.skills.refresh_proposal_state",
                "args_template": {
                    "proposal_id": proposal_id_template,
                },
                "mutates_state": False,
                "enabled": True,
                "requires": ["submit_for_review"],
            },
            {
                "id": "publish_approved_proposal",
                "label": "Publish approved proposal",
                "tool": "aiws.skills.publish_approved_proposal",
                "args_template": {
                    "proposal_id": proposal_id_template,
                },
                "mutates_state": True,
                "enabled": True,
                "requires": ["refresh_proposal_state"],
            },
            {
                "id": "delete_old_artifact_dry_run",
                "label": "Preview old Drive artifact cleanup",
                "tool": "aiws.marketplaces.delete_artifact",
                "args": {
                    "marketplace_id": marketplace_id,
                    "plugin_id": plugin_id,
                    "version": record.version,
                    "dry_run": True,
                    "confirm": False,
                },
                "mutates_state": False,
                "enabled": not is_current_version,
                "disabled_reason": (
                    "Current marketplace version cannot be deleted."
                    if is_current_version
                    else None
                ),
            },
            {
                "id": "check_core_update_status",
                "label": "Check AIWS infrastructure update status",
                "tool": "aiws.runtime.update_status",
                "args": {},
                "mutates_state": False,
                "enabled": True,
            },
        ]

    def _drive_plugin_cache_root(self, host: HostIdentity, record: SkillRecord) -> Path | None:
        if record.marketplace_id is None or record.plugin_id is None:
            return None
        return (
            self.root
            / "hosts"
            / host.host_id
            / "shared-cache"
            / "plugins"
            / self._safe_cache_component(record.marketplace_id)
            / self._safe_cache_component(record.plugin_id)
            / self._safe_cache_component(record.version)
        )

    def _write_adapter(self, host_kind: str, adapter_root: Path, skill_root: Path, record: SkillRecord) -> None:
        if host_kind == "claude-code":
            target = adapter_root / ".claude" / "skills" / record.skill_id
            safe_copytree(skill_root, target)
            return
        if host_kind == "cowork":
            plugin_id = record.plugin_id if record.source.startswith("google-drive:") else None
            plugin_name = plugin_id or "aiws-generated-plugin"
            plugin_root = adapter_root / self._safe_cache_component(plugin_name)
            target = plugin_root / "skills" / record.skill_id
            safe_copytree(skill_root, target)
            write_json_atomic(
                plugin_root / ".claude-plugin" / "plugin.json",
                {
                    "name": plugin_name,
                    "description": (
                        f"Google Drive marketplace adapter for {plugin_name}."
                        if plugin_id is not None
                        else "AIWS generated skill adapter package."
                    ),
                    "version": record.version if plugin_id is not None else "0.1.0",
                },
            )
            return
        if host_kind == "codex":
            target = adapter_root / "skills" / record.skill_id
            safe_copytree(skill_root, target)
            manifest_path = adapter_root / "aiws-codex-export.json"
            existing = load_json(manifest_path, {"skills": []})
            skill_entry = {
                "skill_id": record.skill_id,
                "path": str(target.relative_to(adapter_root)),
            }
            existing["skills"] = [
                item for item in existing.get("skills", []) if item["skill_id"] != record.skill_id
            ] + [skill_entry]
            write_json_atomic(manifest_path, existing)
            return
        raise ValueError(f"Unsupported host kind: {host_kind}")

    def _build_cowork_adapter_package(self, *, plugin_root: Path, package_output_dir: Path) -> Path:
        if plugin_root.is_symlink():
            raise ValueError("Cowork adapter plugin root must not be a symlink.")
        if not plugin_root.exists() or not plugin_root.is_dir():
            raise ValueError("Cowork adapter plugin root is missing.")
        if not is_relative_to(plugin_root.resolve(), self.root.resolve()):
            raise ValueError("Cowork adapter plugin root escapes AIWS runtime root.")
        manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        if not manifest_path.is_file():
            raise ValueError("Cowork adapter plugin manifest is missing.")
        manifest = load_json(manifest_path, {})
        package_name = manifest.get("name")
        if not isinstance(package_name, str) or not package_name.strip():
            raise ValueError("Cowork adapter plugin manifest name is invalid.")

        ensure_dir(package_output_dir)
        package_path = package_output_dir / f"{package_name}.zip"
        if package_path.exists():
            package_path.unlink()
        with zipfile.ZipFile(package_path, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            for path in sorted(plugin_root.rglob("*")):
                if path.is_symlink():
                    raise ValueError(f"Cowork adapter plugin must not contain symlinks: {path}")
                if not path.is_file():
                    continue
                package.write(path, arcname=path.relative_to(plugin_root).as_posix())
        return package_path

    def discover_installed_plugins(
        self,
        *,
        plugin_id: str | None = None,
        search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    ) -> dict[str, Any]:
        return skill_manager.discover_installed_plugins(
            plugin_id=plugin_id,
            search_roots=search_roots,
            env=self.env,
        )

    def inspect_installed_skill(
        self,
        *,
        plugin_id: str,
        skill_id: str,
        search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
        source_plugin_root: str | Path | None = None,
    ) -> dict[str, Any]:
        return skill_manager.inspect_installed_skill(
            plugin_id=plugin_id,
            skill_id=skill_id,
            search_roots=search_roots,
            source_plugin_root=source_plugin_root,
            env=self.env,
        )

    def _find_materialized_plugin_root(
        self,
        *,
        marketplace_id: str,
        plugin_id: str,
        skill_id: str,
        version: str | None = None,
    ) -> Path | None:
        roots = sorted(
            (self.root / "hosts").glob(
                f"*/shared-cache/plugins/{self._safe_cache_component(marketplace_id)}/{self._safe_cache_component(plugin_id)}/*"
            )
        )
        if version is not None:
            roots = [root for root in roots if root.name == self._safe_cache_component(version)]
        for root in reversed(roots):
            if (root / "skills" / skill_id / "SKILL.md").is_file():
                return root
        return None

    def create_or_open_draft(
        self,
        *,
        plugin_id: str,
        skill_id: str,
        target_repo: str,
        source_plugin_root: str | Path | None = None,
        origin_repo: str | None = None,
        origin_marketplace: str | None = None,
        origin_ref: str | None = None,
        base_version: str | None = None,
        base_commit: str | None = None,
        search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
        allow_parallel_draft: bool = False,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        discovered: dict[str, Any] | None = None
        inspection: dict[str, Any] | None = None
        selected_marketplace_id = marketplace_id or origin_marketplace
        if source_plugin_root is None:
            if selected_marketplace_id:
                materialized_root = self._find_materialized_plugin_root(
                    marketplace_id=selected_marketplace_id,
                    plugin_id=plugin_id,
                    skill_id=skill_id,
                    version=base_version,
                )
                if materialized_root is not None:
                    source_plugin_root = materialized_root
                    origin_marketplace = origin_marketplace or selected_marketplace_id
                    origin_ref = origin_ref or selected_marketplace_id
                    base_version = base_version or skill_manager.validate_plugin(
                        materialized_root,
                        expected_name=plugin_id,
                    )["version"]
                    base_commit = base_commit or "google-drive"
            if source_plugin_root is None:
                inspection = self.inspect_installed_skill(
                    plugin_id=plugin_id,
                    skill_id=skill_id,
                    search_roots=search_roots,
                )
                discovered = inspection.get("discovery")
                selected = inspection.get("selected_instance")
                if inspection.get("status") != "ok" or not isinstance(selected, dict):
                    raise ValueError(
                        f"{inspection.get('status')}: cannot select one installed skill for {plugin_id!r}:{skill_id!r}."
                    )
                source_plugin_root = selected["source_plugin_root"]
                origin_marketplace = origin_marketplace or selected.get("origin_marketplace")
                origin_ref = origin_ref or selected.get("origin_ref")
                base_version = base_version or selected.get("base_version")
                base_commit = base_commit or selected.get("base_commit")

        source_root = Path(source_plugin_root).expanduser()
        if base_version is None:
            base_version = skill_manager.validate_plugin(source_root, expected_name=plugin_id)["version"]
        resolved_origin_repo = origin_repo or target_repo
        resolved_origin_marketplace = origin_marketplace or "cowork-upload"
        record = skill_manager.create_or_open_draft(
            self.root,
            source_plugin_root=source_root,
            plugin_id=plugin_id,
            skill_id=skill_id,
            origin_marketplace=resolved_origin_marketplace,
            origin_repo=resolved_origin_repo,
            origin_ref=origin_ref or "cowork-upload",
            base_version=base_version,
            base_commit=base_commit or "uploaded",
            allow_parallel_draft=allow_parallel_draft,
        )
        record_id = skill_manager.draft_id(plugin_id, skill_id, resolved_origin_repo)
        return {
            "status": "draft_opened",
            "record_id": record_id,
            "discovery": discovered,
            "inspection": inspection,
            **record.to_json(),
        }

    def list_draft_files(self, draft_id: str) -> dict[str, Any]:
        return skill_manager.list_draft_files(self.root, draft_id)

    def read_draft_file(self, draft_id: str, relative_path: str) -> dict[str, Any]:
        return skill_manager.read_draft_file(self.root, draft_id, relative_path)

    def write_draft_file(self, draft_id: str, relative_path: str, content: str) -> dict[str, Any]:
        return skill_manager.write_draft_file(self.root, draft_id, relative_path, content)

    def delete_draft_file(self, draft_id: str, relative_path: str) -> dict[str, Any]:
        return skill_manager.delete_draft_file(self.root, draft_id, relative_path)

    def refresh_draft(self, draft_id: str) -> dict[str, Any]:
        record = skill_manager.refresh_modified_status(self.root, draft_id)
        return {"status": "ok", "record_id": draft_id, **record.to_json()}

    def revert_draft(self, draft_id: str) -> dict[str, Any]:
        return skill_manager.revert_draft(self.root, draft_id)

    def validate_draft(
        self,
        draft_id: str,
        *,
        expected_plugin_id: str | None = None,
        expected_marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        return skill_manager.validate_draft(
            self.root,
            draft_id,
            expected_plugin_id=expected_plugin_id,
            expected_marketplace_id=expected_marketplace_id,
        )

    def activate_draft(
        self,
        draft_id: str,
        *,
        host_kind: str,
        host_id: str | None = None,
        package_output_dir: str | Path | None,
    ) -> dict[str, Any]:
        if package_output_dir is None:
            raise ValueError("package_output_dir is required.")
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        package_upload_dir = None
        if host.host_kind == "cowork":
            candidate = host.config_root / "packages"
            if candidate.exists():
                package_upload_dir = candidate
        return skill_manager.activate_draft(
            self.root,
            draft_id,
            host.host_kind,
            Path(package_output_dir).expanduser(),
            host_id=host.host_id,
            package_upload_dir=package_upload_dir,
        )

    def deactivate_draft(
        self,
        draft_id: str,
        *,
        host_kind: str,
        host_id: str | None = None,
    ) -> dict[str, Any]:
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        return skill_manager.deactivate_draft(self.root, draft_id, host.host_kind, host.host_id)

    def prepare_update_candidate(self, draft_id: str) -> dict[str, Any]:
        record = skill_manager.require_canonical_draft_record(self.root, draft_id)
        inspection = self.inspect_installed_skill(plugin_id=record.plugin_id, skill_id=record.skill_id)
        selected = inspection.get("selected_instance")
        if inspection.get("status") != "ok" or not isinstance(selected, dict):
            raise ValueError(
                f"{inspection.get('status')}: cannot select one installed update candidate for "
                f"{record.plugin_id!r}:{record.skill_id!r}."
            )
        result = skill_manager.prepare_update_candidate(self.root, draft_id, Path(selected["source_plugin_root"]))
        return {
            **result,
            "installed_selection": inspection.get("selection"),
            "installed_instance_count": inspection.get("instance_count"),
            "origin_marketplace": selected.get("origin_marketplace"),
            "origin_ref": selected.get("origin_ref"),
        }

    def review_update_conflict(self, draft_id: str, update_candidate_id: str) -> dict[str, Any]:
        return skill_manager.review_update_conflict(self.root, draft_id, update_candidate_id)

    def resolve_update_conflict(
        self,
        review_id: str,
        *,
        choice: str,
        clear_pending_upload: bool = False,
        allow_full_plugin_discard: bool = False,
    ) -> dict[str, Any]:
        return skill_manager.resolve_update_conflict(
            self.root,
            review_id,
            choice,
            clear_pending_upload=clear_pending_upload,
            allow_full_plugin_discard=allow_full_plugin_discard,
        )

    def stage_proposal(
        self,
        draft_id: str,
        *,
        summary: str,
        rationale: str,
        target_scope: str | None = None,
        target_repo: str | None = None,
        backend_kind: str = "github",
        backend_ref: str | None = None,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        resolved_target_scope = target_scope
        resolved_backend_ref = backend_ref
        if resolved_target_scope is None and backend_kind == "google_drive" and marketplace_id:
            registry = skill_manager.load_marketplace_registry(self.root)
            marketplace = registry.get("marketplaces", {}).get(marketplace_id)
            if isinstance(marketplace, dict):
                scope_id = marketplace.get("scope_id")
                if isinstance(scope_id, str) and scope_id.strip():
                    resolved_target_scope = scope_id.strip()
                if resolved_backend_ref is None:
                    registered_backend_ref = marketplace.get("backend_ref")
                    if isinstance(registered_backend_ref, str) and registered_backend_ref.strip():
                        resolved_backend_ref = registered_backend_ref.strip()
        if resolved_target_scope is None:
            raise ValueError(
                "target_scope is required unless backend_kind is google_drive and marketplace_id resolves to a registered marketplace."
            )
        return skill_manager.stage_proposal(
            self.root,
            draft_id,
            resolved_target_scope,
            target_repo,
            summary,
            rationale,
            backend_kind=backend_kind,
            backend_ref=resolved_backend_ref,
            marketplace_id=marketplace_id,
        )

    def submit_for_review(
        self,
        proposal_id: str,
        *,
        allowed_target_repos: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, Any]:
        proposal = skill_manager.load_proposal_record(self.root, proposal_id)
        backend_kind = skill_manager.require_backend_kind(proposal.get("backend_kind", "github"))
        if backend_kind == "google_drive":
            submitter_name = "GoogleDriveProposalSubmitter"
        else:
            submitter_mode = os.environ.get("AIWS_GITHUB_SUBMITTER", "").strip().lower()
            api_token_available = skill_manager.github_api_token_from_env() is not None
            if submitter_mode in {"api", "github_api"}:
                submitter_name = "GitHubApiProposalSubmitter"
            elif submitter_mode == "gh":
                submitter_name = "GhCliProposalSubmitter"
            elif submitter_mode == "handoff":
                submitter_name = "GithubHandoffProposalSubmitter"
            elif api_token_available:
                submitter_name = "GitHubApiProposalSubmitter"
            elif shutil.which("gh"):
                submitter_name = "GhCliProposalSubmitter"
            else:
                submitter_name = "GithubHandoffProposalSubmitter"
        submitter_cls = getattr(skill_manager, submitter_name, None)
        if submitter_cls is None:
            raise RuntimeError(f"{submitter_name} is not available in aiws_mcp.skill_manager.")
        submitter = submitter_cls(aiws_root=self.root)
        return skill_manager.submit_pr(
            self.root,
            proposal_id,
            submitter,
            allowed_target_repos=allowed_target_repos,
        )

    def refresh_proposal_state(self, proposal_id: str) -> dict[str, Any]:
        return skill_manager.refresh_proposal_state(self.root, proposal_id)

    def publish_approved_proposal(self, proposal_id: str) -> dict[str, Any]:
        return skill_manager.publish_approved_proposal(self.root, proposal_id)

    def start_google_drive_oauth(
        self,
        *,
        account: str = "default",
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        return skill_manager.start_google_drive_oauth(
            self.root,
            account=account,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            env=self.env,
        )

    def configure_google_drive_oauth_client(
        self,
        *,
        account: str = "default",
        client_id: str,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        token_uri: str | None = None,
        scopes: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        return skill_manager.configure_google_drive_oauth_client(
            self.root,
            account=account,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            token_uri=token_uri,
            scopes=scopes,
        )

    def finish_google_drive_oauth(
        self,
        auth_session_id: str,
        *,
        redirected_url: str | None = None,
        authorization_code: str | None = None,
    ) -> dict[str, Any]:
        return skill_manager.finish_google_drive_oauth(
            self.root,
            auth_session_id,
            redirected_url=redirected_url,
            authorization_code=authorization_code,
        )

    def list_marketplaces(
        self,
        *,
        scope_id: str | None = None,
        backend_kind: str | None = None,
    ) -> dict[str, Any]:
        registry = skill_manager.load_marketplace_registry(self.root)
        entries = []
        for marketplace_id in sorted(registry.get("marketplaces", {})):
            entry = dict(registry["marketplaces"][marketplace_id])
            if scope_id is not None and entry.get("scope_id") != scope_id:
                continue
            if backend_kind is not None and entry.get("backend_kind") != backend_kind:
                continue
            entries.append(entry)
        return {
            "status": "ok",
            "marketplaces": entries,
            "count": len(entries),
        }

    def _released_drive_package(
        self,
        *,
        marketplace_id: str,
        plugin_id: str,
        version: str,
    ) -> dict[str, Any]:
        registry = skill_manager.load_marketplace_registry(self.root)
        marketplace = registry.get("marketplaces", {}).get(marketplace_id)
        if not isinstance(marketplace, dict):
            raise ValueError(f"Marketplace is not registered: {marketplace_id}")
        if marketplace.get("backend_kind") != "google_drive":
            raise ValueError(f"Marketplace {marketplace_id} is not google_drive.")
        backend_ref = marketplace.get("backend_ref")
        if not isinstance(backend_ref, str) or not backend_ref.strip():
            raise ValueError(f"Marketplace {marketplace_id} does not define backend_ref.")

        token = skill_manager.google_drive_api_token(self.root, env=self.env)
        if token is None:
            raise ValueError("Google Drive credentials are not configured for release export.")
        client = skill_manager.GoogleDriveApiClient(token=token)
        plugins_folder = client.find_child(
            backend_ref.strip(),
            "plugins",
            mime_type="application/vnd.google-apps.folder",
        )
        if plugins_folder is None:
            raise ValueError(f"Google Drive marketplace {marketplace_id} does not have plugins folder.")
        plugin_folder = client.find_child(
            str(plugins_folder["id"]),
            plugin_id,
            mime_type="application/vnd.google-apps.folder",
        )
        if plugin_folder is None:
            raise ValueError(f"Google Drive marketplace {marketplace_id} does not have plugin {plugin_id}.")
        packages_folder = client.find_child(
            str(plugin_folder["id"]),
            "packages",
            mime_type="application/vnd.google-apps.folder",
        )
        if packages_folder is None:
            raise ValueError(f"Google Drive plugin {marketplace_id}/{plugin_id} does not have packages folder.")
        version_folder = client.find_child(
            str(packages_folder["id"]),
            version,
            mime_type="application/vnd.google-apps.folder",
        )
        if version_folder is None:
            raise ValueError(f"Google Drive plugin {marketplace_id}/{plugin_id} does not have version {version}.")
        release_metadata = client.find_child(str(version_folder["id"]), "release.json")
        release_payload = skill_manager.read_drive_json_file(client, str(version_folder["id"]), "release.json")
        if release_metadata is None or release_payload is None:
            raise ValueError(f"Google Drive release {marketplace_id}/{plugin_id}@{version} does not have release.json.")
        if release_payload.get("marketplace_id") != marketplace_id:
            raise ValueError(
                f"Drive release marketplace_id {release_payload.get('marketplace_id')!r} "
                f"does not match expected marketplace_id {marketplace_id!r}."
            )
        if release_payload.get("plugin_id") != plugin_id:
            raise ValueError(
                f"Drive release plugin_id {release_payload.get('plugin_id')!r} "
                f"does not match expected plugin_id {plugin_id!r}."
            )
        if release_payload.get("version") != version:
            raise ValueError(
                f"Drive release version {release_payload.get('version')!r} "
                f"does not match expected version {version!r}."
            )
        package_file_id = release_payload.get("package_file_id")
        if not isinstance(package_file_id, str) or not package_file_id.strip():
            raise ValueError(f"Drive release {marketplace_id}/{plugin_id}@{version} does not define package_file_id.")
        package_metadata = client.get_file(package_file_id.strip())
        parents = package_metadata.get("parents")
        version_folder_id = str(version_folder["id"])
        if not isinstance(parents, list) or version_folder_id not in [str(parent) for parent in parents]:
            raise ValueError("Drive release package file is not under the requested version folder.")
        package_bytes = client.download_file_bytes(package_file_id.strip())
        return {
            "release": release_payload,
            "release_file_id": str(release_metadata["id"]),
            "package_file_id": package_file_id.strip(),
            "package_bytes": package_bytes,
        }

    def _extract_drive_bridge_package(self, package_bytes: bytes, plugin_root: Path) -> None:
        ensure_dir(plugin_root)
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as package:
            for info in package.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue
                if not name or name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"Unsafe Google Drive package entry: {name}")
                destination = plugin_root / name
                ensure_dir(destination.parent)
                with package.open(info) as source, destination.open("wb") as handle:
                    shutil.copyfileobj(source, handle)

    def _bridge_export_component(self, value: str, *, label: str) -> str:
        component = self._safe_cache_component(value)
        if component in {"", ".", ".."}:
            raise ValueError(f"Cowork bridge export {label} is not safe: {value!r}")
        return component

    def _assert_bridge_export_path_safe(self, export_root: Path) -> None:
        if self.root.is_symlink():
            raise ValueError("AIWS root must not be a symlink for Cowork bridge export.")
        root_resolved = self.root.resolve()
        try:
            relative = export_root.relative_to(self.root)
        except ValueError as exc:
            raise ValueError(f"Cowork bridge export path escapes AIWS root: {export_root}") from exc
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ValueError(f"Cowork bridge export path must not contain symlinks: {current}")
            if current.exists() and not is_relative_to(current.resolve(), root_resolved):
                raise ValueError(f"Cowork bridge export path escapes AIWS root: {current}")

    def export_drive_cowork_bridge(
        self,
        *,
        marketplace_id: str,
        plugin_id: str,
        version: str,
    ) -> dict[str, Any]:
        release = self._released_drive_package(
            marketplace_id=marketplace_id,
            plugin_id=plugin_id,
            version=version,
        )
        package_bytes = release["package_bytes"]
        export_root = (
            self.root
            / "bridge-exports"
            / "cowork-git"
            / self._bridge_export_component(marketplace_id, label="marketplace_id")
            / self._bridge_export_component(plugin_id, label="plugin_id")
            / self._bridge_export_component(version, label="version")
        )
        self._assert_bridge_export_path_safe(export_root)
        if export_root.exists():
            shutil.rmtree(export_root)
        bridge_repo_root = export_root / "repo"
        plugin_root = bridge_repo_root / self._bridge_export_component(plugin_id, label="plugin_id")
        self._extract_drive_bridge_package(package_bytes, plugin_root)
        plugin_validation = skill_manager.validate_plugin(
            plugin_root,
            expected_name=plugin_id,
            expected_version=version,
        )
        manifest = load_json(plugin_root / ".claude-plugin" / "plugin.json", {})
        description = manifest.get("description")
        if not isinstance(description, str) or not description.strip():
            description = f"Generated Cowork distribution projection for {plugin_id}."
        author = manifest.get("author")
        plugin_entry = {
            "name": plugin_id,
            "source": f"./{plugin_id}",
            "description": description,
            "version": version,
        }
        if isinstance(author, dict):
            plugin_entry["author"] = author
        write_json_atomic(
            bridge_repo_root / ".claude-plugin" / "marketplace.json",
            {
                "name": "aiws-cowork-drive-bridge",
                "owner": {"name": "Sasha Kang"},
                "metadata": {
                    "description": "Generated Cowork distribution projections from released AIWS Drive plugins.",
                    "projection_kind": "cowork-git-marketplace",
                },
                "plugins": [plugin_entry],
            },
        )
        provenance_path = bridge_repo_root / ".aiws-bridge" / "provenance.json"
        write_json_atomic(
            provenance_path,
            {
                "schema_version": 1,
                "projection_kind": "cowork-git-marketplace",
                "generated_at": utc_now_iso(),
                "source": {
                    "backend_kind": "google_drive",
                    "marketplace_id": marketplace_id,
                    "plugin_id": plugin_id,
                    "version": version,
                    "package_file_id": release["package_file_id"],
                    "package_sha256": hashlib.sha256(package_bytes).hexdigest(),
                    "release_file_id": release["release_file_id"],
                    "release": release["release"],
                },
                "target": {
                    "marketplace_name": "aiws-cowork-drive-bridge",
                    "plugin_source": f"./{plugin_id}",
                },
            },
        )
        validation = skill_manager.validate_marketplace(bridge_repo_root)
        return {
            "status": "exported",
            "source_marketplace_id": marketplace_id,
            "source_plugin_id": plugin_id,
            "source_version": version,
            "bridge_repo_root": str(bridge_repo_root),
            "plugin_root": str(plugin_root),
            "provenance_path": str(provenance_path),
            "publication_instructions": {
                "target_repo": "sashakang/aiws-cowork-drive-bridge",
                "source_tree": str(bridge_repo_root),
                "boundary": (
                    "Publishing this generated Git marketplace projection does not install, update, "
                    "or activate the plugin in Cowork; Cowork native marketplace sync and install/update "
                    "must confirm visibility."
                ),
                "steps": [
                    "Sync the contents of bridge_repo_root to the root of the generated bridge repository.",
                    "Commit the generated marketplace projection with maintainer or bot credentials.",
                    "Push the bridge repository so Cowork can sync the native marketplace artifact.",
                    "Verify Cowork Directory visibility, install, skill use, and update separately.",
                ],
            },
            "plugin_validation": plugin_validation,
            "validation": validation,
        }

    def drive_marketplace_workflow(
        self,
        *,
        marketplace_id: str | None = None,
        plugin_id: str | None = None,
        skill_id: str | None = None,
        host_kind: str = "cowork",
        latest_only: bool = False,
        include_history: bool = True,
        include_debug: bool = False,
    ) -> dict[str, Any]:
        listed = self.list_marketplaces(backend_kind="google_drive")
        marketplaces = listed["marketplaces"]
        if marketplace_id is not None:
            marketplaces = [entry for entry in marketplaces if entry.get("marketplace_id") == marketplace_id]
        selection_filtered = any((marketplace_id, plugin_id, skill_id))
        records = self.catalog_records()
        marketplace_payloads: list[dict[str, Any]] = []
        for marketplace in marketplaces:
            current_marketplace_id = marketplace.get("marketplace_id")
            marketplace_records = [
                record
                for record in records
                if record.marketplace_id == current_marketplace_id
                and (host_kind is None or host_kind in record.supported_hosts)
            ]
            if plugin_id is not None:
                marketplace_records = [record for record in marketplace_records if record.plugin_id == plugin_id]
            if skill_id is not None:
                marketplace_records = [record for record in marketplace_records if record.skill_id == skill_id]
            marketplace_records = self._dedupe_display_records(marketplace_records)
            current_keys = {
                (
                    record.marketplace_id or "",
                    record.plugin_id or "",
                    record.skill_id,
                    record.scope,
                    record.version,
                )
                for record in self._latest_display_records(marketplace_records)
            }
            if latest_only or not include_history:
                marketplace_records = self._latest_display_records(marketplace_records)
            plugins: dict[str, dict[str, Any]] = {}
            for record in marketplace_records:
                record_plugin_id = record.plugin_id or "unknown"
                plugin = plugins.setdefault(
                    record_plugin_id,
                    {
                        "plugin_id": record_plugin_id,
                        "display_name": self._display_label(record_plugin_id),
                        "skills": [],
                    },
                )
                skill_display_name = (
                    self._display_label(record.skill_id)
                    if record.name == record.skill_id
                    else record.name
                )
                next_action = "open_draft" if record.materialized else "materialize_skill"
                actions = self._drive_workflow_actions(
                    record,
                    host_kind=host_kind,
                    skill_display_name=skill_display_name,
                    is_current_version=(
                        (
                            record.marketplace_id or "",
                            record.plugin_id or "",
                            record.skill_id,
                            record.scope,
                            record.version,
                        )
                        in current_keys
                    ),
                    backend_ref=marketplace.get("backend_ref")
                    if isinstance(marketplace.get("backend_ref"), str)
                    else None,
                )
                skill_payload = {
                    "skill_id": record.skill_id,
                    "display_name": skill_display_name,
                    "description": record.description,
                    "version": record.version,
                    "source": record.source,
                    "marketplace_id": record.marketplace_id,
                    "materialized": record.materialized,
                    "status_label": "Materialized" if record.materialized else "Available",
                    "next_action": next_action,
                    "next_action_detail": next(
                        (action for action in actions if action.get("id") == next_action),
                        None,
                    ),
                    "actions": actions,
                }
                if include_debug:
                    skill_payload["debug"] = {"legacy_scope_id": record.scope}
                plugin["skills"].append(skill_payload)
            plugin_payloads = list(plugins.values())
            marketplace_payload = {
                "marketplace_id": current_marketplace_id,
                "backend_kind": marketplace.get("backend_kind"),
                "display_name": self._display_label(str(current_marketplace_id)),
                "cowork_native_visible": False,
                "plugins": plugin_payloads,
                "plugin_count": len(plugins),
                "skill_count": len(marketplace_records),
            }
            if len(plugin_payloads) == 1 and len(plugin_payloads[0]["skills"]) == 1:
                only_skill = plugin_payloads[0]["skills"][0]
                marketplace_payload["current_skill"] = {
                    "plugin_id": plugin_payloads[0]["plugin_id"],
                    "plugin_display_name": plugin_payloads[0]["display_name"],
                    **only_skill,
                }
            if include_debug:
                marketplace_payload["debug"] = {
                    "scope_id": marketplace.get("scope_id"),
                    "backend_ref": marketplace.get("backend_ref"),
                }
            marketplace_payloads.append(marketplace_payload)
        selected_skill_count = sum(payload["skill_count"] for payload in marketplace_payloads)
        selection_status = (
            "browse"
            if not selection_filtered
            else "matched"
            if selected_skill_count
            else "not_found"
        )
        workflow_payload = {
            "status": "ok",
            "host_kind": host_kind,
            "filters": {
                "marketplace_id": marketplace_id,
                "plugin_id": plugin_id,
                "skill_id": skill_id,
            },
            "selection_status": selection_status,
            "selected_skill_count": selected_skill_count,
            "workflow_schema_version": 1,
            "latest_only": latest_only,
            "include_history": include_history,
            "include_debug": include_debug,
            "note": "AIWS Google Drive marketplace skills are managed through AIWS tools and do not appear in Cowork's native plugin sidebar yet.",
            "marketplaces": marketplace_payloads,
            "workflow": [
                "aiws.marketplaces.drive_workflow: list Drive marketplaces and browse plugins/skills.",
                "aiws.skills.search: find a skill with marketplace_id.",
                "aiws.skills.materialize: materialize the skill with marketplace_id and host_kind.",
                "aiws.skills.create_or_open_draft: open a draft using marketplace_id, plugin_id, and skill_id.",
                "aiws.skills.read_draft_file / aiws.skills.write_draft_file: inspect and edit the draft.",
                "aiws.skills.validate_draft: validate with expected_plugin_id and expected_marketplace_id.",
                "aiws.skills.stage_proposal: stage to backend_kind=google_drive with the same marketplace_id.",
                "aiws.skills.submit_for_review / aiws.skills.refresh_proposal_state / aiws.skills.publish_approved_proposal: review, approve, publish, then materialize again from a fresh task.",
            ],
        }
        if selection_filtered and selected_skill_count == 1:
            selected_skill = next(
                payload["current_skill"]
                for payload in marketplace_payloads
                if "current_skill" in payload
            )
            workflow_payload["selected_skill"] = selected_skill
            workflow_payload["selected_action"] = selected_skill["next_action_detail"]
        return workflow_payload

    def register_marketplace(
        self,
        *,
        marketplace_id: str,
        scope_id: str,
        backend_kind: str,
        backend_ref: str,
        replace: bool = False,
    ) -> dict[str, Any]:
        entry = skill_manager.register_marketplace(
            self.root,
            marketplace_id=marketplace_id,
            scope_id=scope_id,
            backend_kind=backend_kind,
            backend_ref=backend_ref,
            replace=replace,
        )
        return {
            "status": "registered",
            "replaced": replace,
            "marketplace": entry,
        }

    def remove_marketplace(self, *, marketplace_id: str) -> dict[str, Any]:
        removed = skill_manager.remove_marketplace_registration(self.root, marketplace_id)
        if removed is None:
            return {
                "status": "not_found",
                "marketplace_id": marketplace_id,
            }
        return {
            "status": "removed",
            "marketplace": removed,
        }

    def delete_marketplace_artifact(
        self,
        *,
        marketplace_id: str,
        plugin_id: str,
        version: str,
        package_file_id: str | None = None,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return skill_manager.delete_drive_marketplace_artifact(
            self.root,
            marketplace_id=marketplace_id,
            plugin_id=plugin_id,
            version=version,
            package_file_id=package_file_id,
            dry_run=dry_run,
            confirm=confirm,
        )

    def stage_change(
        self,
        *,
        skill_id: str,
        target_scope: str,
        summary: str,
        rationale: str,
        host_kind: str | None = None,
        host_id: str | None = None,
        base_version: str | None = None,
        diff: str | None = None,
        bundle_path: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, Any]:
        """Legacy host-local staged write surface; Cowork skill proposals use stage_proposal."""
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        proposal_id = "skillchg_" + uuid.uuid4().hex[:12]
        proposal_path = (
            self.root
            / "hosts"
            / host.host_id
            / "staged-writes"
            / "skills"
            / f"{proposal_id}.json"
        )
        payload = {
            "proposal_id": proposal_id,
            "skill_id": skill_id,
            "target_scope": target_scope,
            "base_version": base_version,
            "summary": summary,
            "rationale": rationale,
            "diff": diff,
            "bundle_path": bundle_path,
            "evidence": evidence,
            "host_id": host.host_id,
            "created_ts": utc_now_iso(),
            "status": "staged",
        }
        if proposal_path.exists():
            raise FileExistsError(f"Proposal already exists: {proposal_path}")
        write_json_atomic(proposal_path, payload)
        return {
            "proposal_id": proposal_id,
            "proposal_path": str(proposal_path),
            "status": "staged",
        }

    def list_staged_changes(self, target_scope: str | None = None, skill_id: str | None = None) -> dict[str, Any]:
        proposals = []
        for path in sorted((self.root / "hosts").glob("*/staged-writes/skills/*.json")):
            payload = load_json(path, {})
            if target_scope and payload.get("target_scope") != target_scope:
                continue
            if skill_id and payload.get("skill_id") != skill_id:
                continue
            payload["proposal_path"] = str(path)
            proposals.append(payload)
        return {"proposals": proposals}
