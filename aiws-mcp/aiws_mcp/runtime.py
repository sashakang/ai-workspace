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

from .builtins import BUILTIN_SKILLS, RESOURCES


NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")
HOST_KINDS = {"claude-code", "cowork", "codex"}


class SkillValidationError(ValueError):
    """Raised when an Agent Skills bundle is invalid."""


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
    if host_kind == "claude-code":
        return Path(env.get("CLAUDE_HOME", "~/.claude")).expanduser().resolve()
    if host_kind == "cowork":
        return Path(env.get("COWORK_HOME", "~/.cowork")).expanduser().resolve()
    if host_kind == "codex":
        return Path(env.get("CODEX_HOME", "~/.codex")).expanduser().resolve()
    raise ValueError(f"Unsupported host kind: {host_kind}")


def derived_host_id(host_kind: str, config_root: Path) -> str:
    digest = hashlib.sha256(str(config_root).encode("utf-8")).hexdigest()[:12]
    return f"{host_kind}-{digest}"


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def safe_copytree(source: Path, destination: Path) -> None:
    for item in source.rglob("*"):
        if item.is_symlink():
            raise ValueError(f"Symlinks are not allowed in skill bundles: {item}")
        if not is_relative_to(item.resolve(), source.resolve()):
            raise ValueError(f"Skill bundle path escapes its root: {item}")
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

        if host_id is None:
            if host_kind is None:
                raise ValueError("host_kind is required when host_id is omitted.")
            resolved_config_root = (config_root or default_config_root(host_kind, self.env)).resolve()
            host_id = derived_host_id(host_kind, resolved_config_root)
        host_root = self.root / "hosts" / host_id
        host_json = host_root / "host.json"

        if host_json.exists():
            payload = load_json(host_json, {})
            existing = HostIdentity(
                host_id=payload["host_id"],
                host_kind=payload["host_kind"],
                config_root=Path(payload["config_root"]),
            )
            if host_kind is not None and host_kind != existing.host_kind:
                raise ValueError("Supplied host_kind conflicts with existing host.json.")
            return existing

        if host_kind is None:
            raise ValueError("host_kind is required for first registration of a host_id.")

        resolved_config_root = (config_root or default_config_root(host_kind, self.env)).resolve()
        host = HostIdentity(host_id=host_id, host_kind=host_kind, config_root=resolved_config_root)
        ensure_dir(host_root)
        write_json_atomic(
            host_json,
            {
                "host_id": host.host_id,
                "host_kind": host.host_kind,
                "config_root": str(host.config_root),
            },
        )
        return host

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
            metadata = validate_skill_content(entrypoint.read_text(), skill_root.name)
            records.append(
                SkillRecord(
                    skill_id=skill_root.name,
                    name=metadata["name"],
                    description=metadata["description"],
                    scope=skill_root.parent.parent.name,
                    version=skill_root.parent.name,
                    source=str(skill_root),
                    root=skill_root,
                    entrypoint_content=None,
                    supported_hosts=tuple(sorted(HOST_KINDS)),
                    materialized=True,
                )
            )
        return records

    def catalog_records(self) -> list[SkillRecord]:
        return [
            *self.built_in_records(),
            *self.personal_records(),
            *self.materialized_records(),
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
        target_root = cache_root / self._safe_scope(record.scope) / record.version / record.skill_id
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
