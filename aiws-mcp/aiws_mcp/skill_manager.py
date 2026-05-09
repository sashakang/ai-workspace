from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit


NAME_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?")
ALLOWED_SKILL_FRONTMATTER = {"name", "description"}
CLUTTER_FILES = {
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
    "README.md",
}
SECRET_NAME_RE = re.compile(
    r"(?:^|[_-])(?:auth|authorization|token|secret|password|credential|api[_-]?key|bearer|oauth)(?:$|[_-])",
    re.IGNORECASE,
)
SECRET_VALUE_RE = re.compile(
    r"(?:xox[baprs]-[A-Za-z0-9-]+|gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]+)",
    re.IGNORECASE,
)


class SkillManagerError(ValueError):
    pass


@dataclass(frozen=True)
class DraftRecord:
    plugin_id: str
    skill_id: str
    origin_marketplace: str
    origin_repo: str
    origin_ref: str
    base_version: str
    base_commit: str
    draft_path: str
    active: bool
    modified: bool
    publish_target: str | None
    branch_name: str | None
    pr_url: str | None
    last_validation_status: str
    updated_at: str

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9-]+", "-", value.lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized or "unknown"


def draft_id(plugin_id: str, skill_id: str, origin_repo: str) -> str:
    digest = hashlib.sha256(origin_repo.encode("utf-8")).hexdigest()[:10]
    return f"{slug(plugin_id)}--{slug(skill_id)}--{digest}"


def draft_record_path(aiws_root: Path, record_id: str) -> Path:
    return aiws_root / "state" / "skill-drafts" / f"{record_id}.json"


def draft_worktree_path(aiws_root: Path, marketplace: str, plugin_id: str, origin_repo: str) -> Path:
    digest = hashlib.sha256(origin_repo.encode("utf-8")).hexdigest()[:10]
    return aiws_root / "plugins" / slug(marketplace) / f"{slug(plugin_id)}-{digest}"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SkillManagerError(f"Invalid JSON: {path}") from exc


def reject_symlinked_root(root: Path, *, label: str) -> None:
    if root.is_symlink():
        raise SkillManagerError(f"{label} must not be a symlink: {root}")


def reject_symlinked_child_path(path: Path, root: Path, *, label: str) -> None:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError as exc:
        raise SkillManagerError(f"{label} is outside AIWS draft plugin root: {path}") from exc

    current = root.absolute()
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise SkillManagerError(f"{label} must not contain symlinks: {path}")


def require_path_under(path: Path, root: Path, *, label: str) -> Path:
    reject_symlinked_root(root, label="AIWS draft plugin root")
    reject_symlinked_child_path(path, root, label=label)
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root:
        raise SkillManagerError(f"{label} is outside AIWS draft plugin root: {path}")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SkillManagerError(f"{label} is outside AIWS draft plugin root: {path}") from exc
    return resolved_path


def require_record_path_under(path: Path, root: Path) -> Path:
    reject_symlinked_root(root.parent, label="AIWS draft state parent")
    reject_symlinked_root(root, label="AIWS draft state root")
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root:
        raise SkillManagerError(f"Draft record path is outside AIWS draft state root: {path}")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SkillManagerError(f"Draft record path is outside AIWS draft state root: {path}") from exc
    return resolved_path


def parse_skill_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        raise SkillManagerError("SKILL.md must start with YAML frontmatter.")
    try:
        _, frontmatter, body = content.split("---", 2)
    except ValueError as exc:
        raise SkillManagerError("SKILL.md frontmatter is not closed.") from exc

    metadata: dict[str, str] = {}
    for raw_line in frontmatter.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise SkillManagerError(f"Invalid frontmatter line: {raw_line}")
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, body


def validate_skill_creator_compat(skill_root: Path) -> dict[str, str]:
    if not skill_root.is_dir():
        raise SkillManagerError(f"Skill root is not a directory: {skill_root}")
    skill_file = skill_root / "SKILL.md"
    if not skill_file.is_file():
        raise SkillManagerError(f"Missing SKILL.md: {skill_root}")

    metadata, body = parse_skill_frontmatter(skill_file.read_text())
    extra = set(metadata) - ALLOWED_SKILL_FRONTMATTER
    if extra:
        raise SkillManagerError(f"Unsupported SKILL.md frontmatter fields in {skill_root}: {sorted(extra)}")

    name = metadata.get("name", "")
    description = metadata.get("description", "")
    if name != skill_root.name:
        raise SkillManagerError(f"Skill name {name!r} must match directory {skill_root.name!r}.")
    if not NAME_RE.fullmatch(name) or "--" in name:
        raise SkillManagerError("Skill name must use lowercase letters, digits, and single hyphens.")
    if not description:
        raise SkillManagerError(f"Skill description is required: {skill_root}")
    if not body.strip():
        raise SkillManagerError(f"Skill body is required: {skill_root}")

    clutter = sorted(path.name for path in skill_root.iterdir() if path.is_file() and path.name in CLUTTER_FILES)
    if clutter:
        raise SkillManagerError(f"Unsupported clutter files in skill folder {skill_root}: {clutter}")

    return {"name": name, "description": description}


def validate_mcp_config(path: Path) -> dict[str, Any]:
    payload = load_json(path)
    return validate_mcp_payload(payload, source=str(path))


def validate_mcp_payload(payload: Any, *, source: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SkillManagerError(f"MCP config must be a JSON object: {source}")
    if "servers" in payload:
        raise SkillManagerError(f"MCP config must use top-level mcpServers, not servers: {source}")
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise SkillManagerError(f"MCP config must contain non-empty mcpServers object: {source}")

    for name, config in servers.items():
        if not isinstance(name, str) or not name:
            raise SkillManagerError(f"MCP server names must be non-empty strings: {source}")
        if not isinstance(config, dict):
            raise SkillManagerError(f"MCP server config must be an object: {name}")
        scan_for_inline_secrets(config, path=f"mcpServers.{name}")
        server_type = config.get("type", "stdio")
        if server_type == "http":
            if not isinstance(config.get("url"), str) or not config["url"]:
                raise SkillManagerError(f"HTTP MCP server must define url: {name}")
        elif server_type == "stdio":
            if not isinstance(config.get("command"), str) or not config["command"]:
                raise SkillManagerError(f"stdio MCP server must define command: {name}")
            if "args" in config and not isinstance(config["args"], list):
                raise SkillManagerError(f"stdio MCP server args must be a list: {name}")
            if "env" in config and not isinstance(config["env"], dict):
                raise SkillManagerError(f"stdio MCP server env must be an object: {name}")
            if "env" in config:
                validate_mcp_env(config["env"], server_name=name)
        else:
            raise SkillManagerError(f"Unsupported MCP server type {server_type!r}: {name}")
    return payload


def scan_for_inline_secrets(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(key, str) and SECRET_NAME_RE.search(key):
                raise SkillManagerError(f"MCP config must not inline secret-like key {path}.{key}")
            scan_for_inline_secrets(item, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            scan_for_inline_secrets(item, path=f"{path}[{index}]")
    elif isinstance(value, str):
        if SECRET_VALUE_RE.search(value):
            raise SkillManagerError(f"MCP config must not inline secret-like value at {path}")
        scan_url_query_for_secrets(value, path=path)


def scan_url_query_for_secrets(value: str, *, path: str) -> None:
    parsed = urlsplit(value)
    if not parsed.query:
        return
    for key, item in parse_qsl(parsed.query, keep_blank_values=True):
        if SECRET_NAME_RE.search(key):
            raise SkillManagerError(f"MCP config must not inline secret-like URL query key {path}.{key}")
        if SECRET_VALUE_RE.search(item):
            raise SkillManagerError(f"MCP config must not inline secret-like URL query value {path}.{key}")


def validate_mcp_env(env: dict[str, Any], *, server_name: str) -> None:
    for key, value in env.items():
        if not isinstance(key, str) or not key:
            raise SkillManagerError(f"MCP env keys must be non-empty strings: {server_name}")
        if not isinstance(value, str):
            raise SkillManagerError(f"MCP env values must be strings: {server_name}")
        if SECRET_NAME_RE.search(key):
            raise SkillManagerError(f"MCP env must not inline secret-like key {key!r}: {server_name}")
        if SECRET_VALUE_RE.search(value):
            raise SkillManagerError(f"MCP env must not inline secret-like value for {key!r}: {server_name}")


def plugin_manifest_path(plugin_root: Path) -> Path:
    return plugin_root / ".claude-plugin" / "plugin.json"


def contract_path(plugin_root: Path, plugin_id: str) -> Path:
    return plugin_root / "contracts" / f"{plugin_id}.contract.json"


def validate_plugin(plugin_root: Path, *, expected_name: str | None = None, expected_version: str | None = None) -> dict[str, Any]:
    manifest_file = plugin_manifest_path(plugin_root)
    if not manifest_file.is_file():
        raise SkillManagerError(f"Missing plugin manifest: {manifest_file}")
    manifest = load_json(manifest_file)
    if not isinstance(manifest, dict):
        raise SkillManagerError(f"Plugin manifest must be an object: {manifest_file}")

    name = manifest.get("name")
    version = manifest.get("version")
    if not isinstance(name, str) or not name:
        raise SkillManagerError(f"Plugin manifest must define name: {manifest_file}")
    if not isinstance(version, str) or not version:
        raise SkillManagerError(f"Plugin manifest must define version: {manifest_file}")
    if expected_name and name != expected_name:
        raise SkillManagerError(f"Marketplace entry {expected_name!r} points to plugin {name!r}.")
    if expected_version and version != expected_version:
        raise SkillManagerError(
            f"Marketplace entry for {name} declares version {expected_version!r}, but plugin.json says {version!r}."
        )

    contract_file = contract_path(plugin_root, name)
    if contract_file.exists():
        contract = load_json(contract_file)
        if contract.get("plugin_id") != name:
            raise SkillManagerError(f"Contract plugin_id must match plugin name: {contract_file}")
        if contract.get("version") != version:
            raise SkillManagerError(f"Contract version must match plugin version: {contract_file}")
    else:
        contract = None

    skill_results = []
    skills_root = plugin_root / "skills"
    if skills_root.is_dir():
        for skill_root in sorted(path for path in skills_root.iterdir() if path.is_dir()):
            skill_results.append(validate_skill_creator_compat(skill_root))
    actual_skill_names = {item["name"] for item in skill_results}
    if contract is not None:
        public_skills = contract.get("public_skills", [])
        if not isinstance(public_skills, list) or not all(isinstance(item, str) for item in public_skills):
            raise SkillManagerError(f"Contract public_skills must be a string list: {contract_file}")
        missing = sorted(set(public_skills) - actual_skill_names)
        if missing:
            raise SkillManagerError(f"Contract public_skills missing skill folders in {name}: {missing}")

    mcp_files = sorted(plugin_root.glob(".mcp.json"))
    for mcp_file in mcp_files:
        validate_mcp_config(mcp_file)
    if "mcpServers" in manifest or "servers" in manifest:
        validate_mcp_payload(manifest, source=str(manifest_file))

    return {"name": name, "version": version, "skills": skill_results, "mcp_files": [str(path) for path in mcp_files]}


def validate_marketplace(repo_root: Path) -> dict[str, Any]:
    marketplace_file = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = load_json(marketplace_file)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise SkillManagerError("marketplace.json must contain plugins list.")

    results = []
    for entry in plugins:
        if not isinstance(entry, dict):
            raise SkillManagerError("Marketplace plugin entries must be objects.")
        name = entry.get("name")
        source = entry.get("source")
        version = entry.get("version")
        if not all(isinstance(value, str) and value for value in (name, source, version)):
            raise SkillManagerError(f"Marketplace entry must define name, source, and version: {entry}")
        plugin_root = (repo_root / source).resolve()
        try:
            plugin_root.relative_to(repo_root.resolve())
        except ValueError as exc:
            raise SkillManagerError(f"Marketplace source escapes repository: {source}") from exc
        results.append(validate_plugin(plugin_root, expected_name=name, expected_version=version))
    return {"marketplace": marketplace.get("name"), "plugins": results}


def create_draft_record(
    aiws_root: Path,
    *,
    plugin_id: str,
    skill_id: str,
    origin_marketplace: str,
    origin_repo: str,
    origin_ref: str,
    base_version: str,
    base_commit: str,
) -> DraftRecord:
    record_id = draft_id(plugin_id, skill_id, origin_repo)
    draft_path = draft_worktree_path(aiws_root, origin_marketplace, plugin_id, origin_repo)
    record = DraftRecord(
        plugin_id=plugin_id,
        skill_id=skill_id,
        origin_marketplace=origin_marketplace,
        origin_repo=origin_repo,
        origin_ref=origin_ref,
        base_version=base_version,
        base_commit=base_commit,
        draft_path=str(draft_path),
        active=True,
        modified=False,
        publish_target=None,
        branch_name=None,
        pr_url=None,
        last_validation_status="not_run",
        updated_at=utc_now(),
    )
    write_json_atomic(draft_record_path(aiws_root, record_id), record.to_json())
    return record


def load_draft_record(aiws_root: Path, record_id: str) -> DraftRecord:
    payload = load_json(draft_record_path(aiws_root, record_id))
    return DraftRecord(**payload)


def create_or_open_draft(
    aiws_root: Path,
    *,
    source_plugin_root: Path,
    plugin_id: str,
    skill_id: str,
    origin_marketplace: str,
    origin_repo: str,
    origin_ref: str,
    base_version: str,
    base_commit: str,
) -> DraftRecord:
    validation = validate_plugin(source_plugin_root, expected_name=plugin_id, expected_version=base_version)
    skill_names = {skill["name"] for skill in validation["skills"]}
    if skill_id not in skill_names:
        raise SkillManagerError(f"Requested skill {skill_id!r} does not exist in plugin {plugin_id!r}.")

    record_id = draft_id(plugin_id, skill_id, origin_repo)
    record_path = draft_record_path(aiws_root, record_id)
    state_root = aiws_root / "state" / "skill-drafts"
    plugins_root = aiws_root / "plugins"
    expected_draft_path = draft_worktree_path(aiws_root, origin_marketplace, plugin_id, origin_repo)
    require_record_path_under(record_path, state_root)
    require_path_under(expected_draft_path, plugins_root, label="Draft path")

    if record_path.exists():
        existing = load_draft_record(aiws_root, record_id)
        existing_draft_path = require_path_under(Path(existing.draft_path), plugins_root, label="Draft path")
        if existing_draft_path != expected_draft_path.resolve():
            raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")
        if existing_draft_path.exists():
            return existing

    if expected_draft_path.exists():
        raise SkillManagerError(f"Draft path already exists without a usable record: {expected_draft_path}")

    expected_draft_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_plugin_root, expected_draft_path)

    record = DraftRecord(
        plugin_id=plugin_id,
        skill_id=skill_id,
        origin_marketplace=origin_marketplace,
        origin_repo=origin_repo,
        origin_ref=origin_ref,
        base_version=base_version,
        base_commit=base_commit,
        draft_path=str(expected_draft_path),
        active=True,
        modified=False,
        publish_target=None,
        branch_name=None,
        pr_url=None,
        last_validation_status="passed",
        updated_at=utc_now(),
    )
    write_json_atomic(record_path, record.to_json())
    return record


def revert_draft(aiws_root: Path, record_id: str) -> dict[str, str]:
    record_path = draft_record_path(aiws_root, record_id)
    state_root = aiws_root / "state" / "skill-drafts"
    plugins_root = aiws_root / "plugins"
    require_record_path_under(record_path, state_root)

    record = load_draft_record(aiws_root, record_id)
    draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
    expected_draft_path = require_path_under(
        draft_worktree_path(aiws_root, record.origin_marketplace, record.plugin_id, record.origin_repo),
        plugins_root,
        label="Expected draft path",
    )
    if draft_path != expected_draft_path:
        raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")

    if draft_path.exists():
        if not draft_path.is_dir():
            raise SkillManagerError(f"Draft path is not a directory: {draft_path}")
        shutil.rmtree(draft_path)
    record_path.unlink()
    return {"status": "reverted", "record_id": record_id}


def update_from_github_decision(record: DraftRecord | None) -> dict[str, Any]:
    if record is not None and record.active and record.modified:
        return {
            "allowed": False,
            "reason": "active_modified_draft",
            "choices": ["keep_local_modified_skill_active", "discard_local_changes_and_update", "submit_or_upload_first"],
        }
    return {"allowed": True, "reason": "no_active_modified_draft", "choices": []}
