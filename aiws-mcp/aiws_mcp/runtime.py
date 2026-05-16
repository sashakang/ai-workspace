from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
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

    def manifest(self) -> dict[str, Any]:
        return {
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

    def summary(self) -> dict[str, Any]:
        return {
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
            records.append(
                SkillRecord(
                    skill_id=skill_id,
                    name=metadata["name"],
                    description=metadata["description"],
                    scope=skill_root.parent.parent.name,
                    version=skill_root.name,
                    source=str(skill_root),
                    root=skill_root,
                    entrypoint_content=None,
                    supported_hosts=tuple(sorted(HOST_KINDS)),
                    materialized=True,
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
        ]

    def search_skills(
        self,
        *,
        query: str | None = None,
        scopes: list[str] | None = None,
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
        if host_kind:
            records = [record for record in records if host_kind in record.supported_hosts]
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
        version: str | None = None,
        host_kind: str | None = None,
    ) -> dict[str, Any]:
        records = [record for record in self.catalog_records() if record.skill_id == skill_id]
        if scope:
            records = [record for record in records if record.scope == scope]
        if version:
            records = [record for record in records if record.version == version]
        if host_kind:
            records = [record for record in records if host_kind in record.supported_hosts]
        if not records:
            return {"status": "not_found", "reason": f"No skill found for {skill_id}."}
        unique: dict[tuple[str, str], SkillRecord] = {}
        for record in records:
            key = (record.scope, record.version)
            existing = unique.get(key)
            if existing is None or existing.materialized:
                unique[key] = record
        records = list(unique.values())
        if len(records) > 1 and not (scope or version):
            return {"status": "ambiguous", "candidates": [record.summary() for record in records]}
        return {"status": "ok", "manifest": records[0].manifest()}

    def get_skill(
        self,
        skill_id: str,
        *,
        scope: str | None = None,
        version: str | None = None,
        include_content: bool = False,
    ) -> dict[str, Any]:
        resolved = self.resolve_skill(skill_id, scope=scope, version=version)
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
            if (
                record.skill_id == manifest["skill_id"]
                and record.scope == manifest["scope"]
                and record.version == manifest["version"]
            ):
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

    def materialize_skill(
        self,
        *,
        skill_id: str,
        host_kind: str | None = None,
        host_id: str | None = None,
        scope: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        host = self.ensure_host(host_kind=host_kind, host_id=host_id)
        resolved = self.resolve_skill(skill_id, scope=scope, version=version, host_kind=host.host_kind)
        if resolved["status"] != "ok":
            return resolved
        record = self._record_from_manifest(resolved["manifest"])
        if not record.downloadable:
            return {"status": "unavailable", "reason": "Remote fixture records are metadata-only in MVP."}

        cache_root = self.root / "hosts" / host.host_id / "shared-cache" / "skills"
        target_root = cache_root / self._safe_scope(record.scope) / record.skill_id / record.version
        ensure_dir(target_root.parent)

        if record.root is not None:
            safe_copytree(record.root, target_root)
        else:
            if target_root.exists():
                shutil.rmtree(target_root)
            ensure_dir(target_root)
            write_text_atomic(target_root / "SKILL.md", record.entrypoint_content or "")

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
        if host_kind != "codex":
            raise ValueError("install-host currently supports only host_kind='codex'.")
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

    def _write_adapter(self, host_kind: str, adapter_root: Path, skill_root: Path, record: SkillRecord) -> None:
        if host_kind == "claude-code":
            target = adapter_root / ".claude" / "skills" / record.skill_id
            safe_copytree(skill_root, target)
            return
        if host_kind == "cowork":
            plugin_root = adapter_root / "aiws-generated-plugin"
            target = plugin_root / "skills" / record.skill_id
            safe_copytree(skill_root, target)
            write_json_atomic(
                plugin_root / ".claude-plugin" / "plugin.json",
                {
                    "name": "aiws-generated-plugin",
                    "description": "AIWS generated skill adapter package.",
                    "version": "0.1.0",
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
    ) -> dict[str, Any]:
        discovered: dict[str, Any] | None = None
        inspection: dict[str, Any] | None = None
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

    def validate_draft(self, draft_id: str) -> dict[str, Any]:
        return skill_manager.validate_draft(self.root, draft_id)

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
        target_scope: str,
        target_repo: str,
        summary: str,
        rationale: str,
    ) -> dict[str, Any]:
        return skill_manager.stage_proposal(
            self.root,
            draft_id,
            target_scope,
            target_repo,
            summary,
            rationale,
        )

    def submit_for_review(
        self,
        proposal_id: str,
        *,
        allowed_target_repos: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, Any]:
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
