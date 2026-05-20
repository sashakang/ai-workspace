from __future__ import annotations

import base64
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urlsplit
from urllib.request import Request, urlopen


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
UPDATE_CONFLICT_CHOICES = [
    "keep_local_draft_and_pending_package",
    "discard_local_changes_and_update",
    "submit_or_upload_first",
]
UPDATE_DIFF_PREVIEW_LIMIT = 20_000


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
    base_tree_digest: str | None
    current_tree_digest: str | None
    active: bool
    modified: bool
    publish_target: str | None
    branch_name: str | None
    pr_url: str | None
    last_validation_status: str
    last_validation_tree_digest: str | None
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


def draft_base_tree_path(aiws_root: Path, record_id: str) -> Path:
    return aiws_root / "state" / "skill-drafts" / f"{record_id}.base-tree.json"


def draft_base_snapshot_path(aiws_root: Path, record_id: str) -> Path:
    return aiws_root / "state" / "skill-drafts" / f"{record_id}.base-snapshot"


def update_candidate_root(aiws_root: Path) -> Path:
    return aiws_root / "state" / "update-candidates"


def update_candidate_record_path(aiws_root: Path, candidate_id: str) -> Path:
    return update_candidate_root(aiws_root) / f"{candidate_id}.json"


def update_review_root(aiws_root: Path) -> Path:
    return aiws_root / "state" / "update-reviews"


def update_review_record_path(aiws_root: Path, review_id: str) -> Path:
    return update_review_root(aiws_root) / f"{review_id}.json"


def draft_worktree_path(aiws_root: Path, marketplace: str, plugin_id: str, origin_repo: str) -> Path:
    digest = hashlib.sha256(origin_repo.encode("utf-8")).hexdigest()[:10]
    return aiws_root / "plugins" / slug(marketplace) / f"{slug(plugin_id)}-{digest}"


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    reject_existing_symlink_components(path.parent, label="JSON write parent")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    reject_existing_symlink_components(temp.parent, label="JSON temporary parent")
    if temp.is_symlink():
        raise SkillManagerError(f"JSON temporary path must not be a symlink: {temp}")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temp.replace(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise SkillManagerError(f"Invalid JSON: {path}") from exc


def draft_record_from_payload(payload: dict[str, Any]) -> DraftRecord:
    compatible = dict(payload)
    compatible.setdefault("base_tree_digest", None)
    compatible.setdefault("current_tree_digest", None)
    compatible.setdefault("last_validation_tree_digest", None)
    return DraftRecord(**compatible)


def reject_symlinked_root(root: Path, *, label: str) -> None:
    if root.is_symlink():
        raise SkillManagerError(f"{label} must not be a symlink: {root}")


def reject_existing_symlink_components(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor) if absolute.anchor else Path()
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        if current.parent == Path(current.anchor):
            continue
        if current.is_symlink():
            raise SkillManagerError(f"{label} must not contain symlinks: {path}")
        if not current.exists():
            break


def reject_symlinked_child_path(path: Path, root: Path, *, label: str) -> None:
    path_absolute = path.absolute()
    root_absolute = root.absolute()
    try:
        relative = path_absolute.relative_to(root_absolute)
        current = root_absolute
    except ValueError:
        try:
            relative = path.resolve(strict=False).relative_to(root.resolve(strict=False))
            current = root.resolve(strict=False)
        except ValueError as exc:
            raise SkillManagerError(f"{label} is outside AIWS draft plugin root: {path}") from exc

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


def require_activation_path_under(path: Path, root: Path) -> Path:
    reject_symlinked_root(root.parent, label="AIWS activation state parent")
    reject_symlinked_root(root, label="AIWS activation state root")
    reject_existing_symlink_components(path.parent, label="AIWS activation state path")
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root:
        raise SkillManagerError(f"Activation record path is outside AIWS activation state root: {path}")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SkillManagerError(f"Activation record path is outside AIWS activation state root: {path}") from exc
    return resolved_path


def require_update_state_path_under(path: Path, root: Path) -> Path:
    reject_symlinked_root(root.parent, label="AIWS update state parent")
    reject_symlinked_root(root, label="AIWS update state root")
    reject_existing_symlink_components(path.parent, label="AIWS update state path")
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    if resolved_path == resolved_root:
        raise SkillManagerError(f"Update state path is outside AIWS update state root: {path}")
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise SkillManagerError(f"Update state path is outside AIWS update state root: {path}") from exc
    return resolved_path


def tree_digest(root: Path) -> str:
    if not root.is_dir():
        raise SkillManagerError(f"Draft path is not a directory: {root}")

    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise SkillManagerError(f"Draft path must not contain symlinks: {path}")
        if path.is_dir():
            digest.update(b"D\0")
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            continue
        if path.is_file():
            digest.update(b"F\0")
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            content = path.read_bytes()
            digest.update(str(len(content)).encode("ascii"))
            digest.update(b"\0")
            digest.update(content)
            digest.update(b"\0")
            continue
        raise SkillManagerError(f"Unsupported draft tree entry: {path}")
    return digest.hexdigest()


def tree_file_hashes(root: Path) -> dict[str, str]:
    if not root.is_dir():
        raise SkillManagerError(f"Draft path is not a directory: {root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise SkillManagerError(f"Draft path must not contain symlinks: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise SkillManagerError(f"Unsupported draft tree entry: {path}")
        result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def reject_tree_symlinks(root: Path, *, label: str) -> None:
    if root.is_symlink():
        raise SkillManagerError(f"{label} must not be a symlink: {root}")
    if not root.is_dir():
        raise SkillManagerError(f"{label} is not a directory: {root}")
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise SkillManagerError(f"{label} must not contain symlinks: {path}")
        if not (path.is_dir() or path.is_file()):
            raise SkillManagerError(f"{label} contains unsupported entry: {path}")


def write_base_tree_manifest(aiws_root: Path, record_id: str, draft_path: Path) -> None:
    path = draft_base_tree_path(aiws_root, record_id)
    require_record_path_under(path, aiws_root / "state" / "skill-drafts")
    write_json_atomic(path, {"files": tree_file_hashes(draft_path)})


def write_base_tree_snapshot(aiws_root: Path, record_id: str, source_path: Path) -> Path:
    root = aiws_root / "state" / "skill-drafts"
    snapshot_path = draft_base_snapshot_path(aiws_root, record_id)
    require_record_path_under(snapshot_path, root)
    temp_path = snapshot_path.with_name(f"{snapshot_path.name}.tmp-{uuid.uuid4().hex}")
    require_record_path_under(temp_path, root)
    reject_tree_symlinks(source_path, label="Draft base snapshot source")
    if temp_path.exists():
        shutil.rmtree(temp_path)
    shutil.copytree(source_path, temp_path, symlinks=False)
    if snapshot_path.exists():
        if snapshot_path.is_symlink() or not snapshot_path.is_dir():
            raise SkillManagerError(f"Draft base snapshot path is unsafe: {snapshot_path}")
        shutil.rmtree(snapshot_path)
    temp_path.replace(snapshot_path)
    return snapshot_path


def ensure_base_tree_snapshot(aiws_root: Path, record_id: str, draft_path: Path, record: DraftRecord) -> Path:
    snapshot_path = draft_base_snapshot_path(aiws_root, record_id)
    require_record_path_under(snapshot_path, aiws_root / "state" / "skill-drafts")
    if snapshot_path.exists():
        reject_tree_symlinks(snapshot_path, label="Draft base snapshot")
        if record.base_tree_digest is not None and tree_digest(snapshot_path) != record.base_tree_digest:
            raise SkillManagerError(f"Draft base snapshot digest does not match draft record: {record_id}")
        return snapshot_path
    current_digest = tree_digest(draft_path)
    if record.modified or record.base_tree_digest != current_digest:
        raise SkillManagerError(
            "Draft base snapshot is missing and cannot be reconstructed after local modifications. "
            "Recreate the draft before reviewing marketplace updates."
        )
    return write_base_tree_snapshot(aiws_root, record_id, draft_path)


def load_base_tree_manifest(aiws_root: Path, record_id: str) -> dict[str, str]:
    path = draft_base_tree_path(aiws_root, record_id)
    require_record_path_under(path, aiws_root / "state" / "skill-drafts")
    if not path.exists():
        raise SkillManagerError(f"Draft base tree manifest is missing; recreate the draft before staging: {record_id}")
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise SkillManagerError(f"Draft base tree manifest is invalid: {path}")
    files = payload["files"]
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in files.items()):
        raise SkillManagerError(f"Draft base tree manifest is invalid: {path}")
    return dict(files)


def changed_paths_since_base(aiws_root: Path, record_id: str, draft_path: Path) -> list[str]:
    base = load_base_tree_manifest(aiws_root, record_id)
    current = tree_file_hashes(draft_path)
    paths = sorted(set(base) | set(current))
    return [path for path in paths if base.get(path) != current.get(path)]


def require_changes_only_under_skill(aiws_root: Path, record_id: str, draft_path: Path, skill_id: str) -> list[str]:
    changed = changed_paths_since_base(aiws_root, record_id, draft_path)
    allowed_prefix = f"skills/{skill_id}/"
    outside = [path for path in changed if not path.startswith(allowed_prefix)]
    if outside:
        raise SkillManagerError(f"Draft contains changes outside the managed skill folder: {outside}")
    return changed


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


def default_plugin_search_roots(env: dict[str, str] | None = None) -> list[Path]:
    env = dict(os.environ if env is None else env)
    roots: list[Path] = []
    configured = env.get("AIWS_PLUGIN_SEARCH_ROOTS", "")
    roots.extend(Path(item).expanduser() for item in configured.split(os.pathsep) if item)
    plugin_root = env.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        root = Path(plugin_root).expanduser()
        roots.extend([root, root.parent, root.parent.parent])
    cowork_home = env.get("COWORK_HOME")
    if cowork_home:
        root = Path(cowork_home).expanduser()
        roots.extend([root, root / "rpm", root / "plugins"])
    default_cowork_home = Path("~/.cowork").expanduser()
    roots.extend([default_cowork_home, default_cowork_home / "rpm", default_cowork_home / "plugins"])
    sessions_root = Path(
        env.get("AIWS_CLAUDE_LOCAL_AGENT_SESSIONS_ROOT", "~/Library/Application Support/Claude/local-agent-mode-sessions")
    ).expanduser()
    if sessions_root.exists() and sessions_root.is_dir() and not sessions_root.is_symlink():
        for pattern in ("*/rpm", "*/*/rpm", "*/*/*/rpm"):
            roots.extend(path for path in sessions_root.glob(pattern) if path.is_dir())

    result: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen and root.exists():
            result.append(root)
            seen.add(key)
    return result


def discover_installed_plugins(
    *,
    plugin_id: str | None = None,
    search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    roots = [Path(root).expanduser() for root in search_roots] if search_roots is not None else default_plugin_search_roots(env)
    searched = [str(root) for root in roots]
    plugins: list[dict[str, Any]] = []
    seen_roots: set[Path] = set()

    for root in roots:
        if not root.exists() or root.is_symlink():
            continue
        if not root.is_dir():
            continue
        reject_existing_symlink_components(root, label="Plugin search root")
        manifest_paths = [root / ".claude-plugin" / "plugin.json"]
        if root.is_dir():
            manifest_paths.extend(root.rglob(".claude-plugin/plugin.json"))
        for manifest_path in manifest_paths:
            if not manifest_path.is_file() or manifest_path.is_symlink():
                continue
            plugin_root = manifest_path.parent.parent
            try:
                manifest_path.resolve().relative_to(root.resolve())
            except (OSError, ValueError):
                continue
            try:
                reject_symlinked_child_path(plugin_root, root, label="Installed plugin root")
            except SkillManagerError:
                continue
            try:
                resolved_root = plugin_root.resolve()
            except OSError:
                continue
            if resolved_root in seen_roots:
                continue
            seen_roots.add(resolved_root)
            try:
                manifest = load_json(manifest_path)
            except SkillManagerError:
                continue
            name = manifest.get("name") if isinstance(manifest, dict) else None
            version = manifest.get("version") if isinstance(manifest, dict) else None
            if not isinstance(name, str) or not isinstance(version, str):
                continue
            if plugin_id is not None and name != plugin_id:
                continue
            plugins.append(
                {
                    "plugin_id": name,
                    "base_version": version,
                    "source_plugin_root": str(resolved_root),
                    "origin_marketplace": plugin_root.parent.name or "cowork-upload",
                    "origin_ref": "cowork-upload",
                    "base_commit": "uploaded",
                }
            )

    plugins.sort(key=lambda item: item["source_plugin_root"])
    if plugin_id is not None and not plugins:
        status = "installed_plugin_not_found"
    elif plugin_id is not None and len(plugins) > 1:
        status = "ambiguous_installed_plugin"
    else:
        status = "ok"
    return {"status": status, "searched_roots": searched, "plugins": plugins}


def _installed_skill_instance(plugin: dict[str, Any], skill_id: str) -> dict[str, Any] | None:
    plugin_root = Path(plugin["source_plugin_root"])
    skill_root = plugin_root / "skills" / skill_id
    skill_file = skill_root / "SKILL.md"
    if not skill_file.is_file() or skill_file.is_symlink():
        return None
    try:
        reject_symlinked_child_path(skill_file, plugin_root, label="Installed skill file")
    except SkillManagerError:
        return None
    return {
        "plugin_id": plugin["plugin_id"],
        "skill_id": skill_id,
        "base_version": plugin["base_version"],
        "source_plugin_root": plugin["source_plugin_root"],
        "origin_marketplace": plugin.get("origin_marketplace"),
        "origin_ref": plugin.get("origin_ref"),
        "base_commit": plugin.get("base_commit"),
        "skill_root": str(skill_root.resolve()),
        "skill_file": str(skill_file.resolve()),
        "runtime_evidence": "installed_plugin_root",
    }


def inspect_installed_skill(
    *,
    plugin_id: str,
    skill_id: str,
    search_roots: list[str | Path] | tuple[str | Path, ...] | None = None,
    source_plugin_root: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if source_plugin_root is not None:
        source_root = Path(source_plugin_root).expanduser()
        try:
            validation = validate_plugin(source_root, expected_name=plugin_id)
        except SkillManagerError as exc:
            return {
                "status": "installed_plugin_not_found",
                "selection": "explicit_source",
                "plugin_id": plugin_id,
                "skill_id": skill_id,
                "instance_count": 0,
                "selected_instance": None,
                "instances": [],
                "reason": str(exc),
            }
        plugin = {
            "plugin_id": validation["name"],
            "base_version": validation["version"],
            "source_plugin_root": str(source_root.resolve()),
            "origin_marketplace": source_root.parent.name or "cowork-upload",
            "origin_ref": "explicit_source",
            "base_commit": "explicit_source",
        }
        instance = _installed_skill_instance(plugin, skill_id)
        if instance is None:
            return {
                "status": "installed_skill_not_found",
                "selection": "explicit_source",
                "plugin_id": plugin_id,
                "skill_id": skill_id,
                "instance_count": 0,
                "selected_instance": None,
                "instances": [],
                "reason": f"Plugin {plugin_id!r} does not contain skill {skill_id!r}.",
            }
        return {
            "status": "ok",
            "selection": "explicit_source",
            "plugin_id": plugin_id,
            "skill_id": skill_id,
            "instance_count": 1,
            "selected_instance": instance,
            "instances": [instance],
            "discovery": None,
        }

    discovery = discover_installed_plugins(plugin_id=plugin_id, search_roots=search_roots, env=env)
    instances = [
        instance
        for plugin in discovery.get("plugins", [])
        if (instance := _installed_skill_instance(plugin, skill_id)) is not None
    ]
    if not instances:
        return {
            "status": "installed_skill_not_found",
            "selection": "auto",
            "plugin_id": plugin_id,
            "skill_id": skill_id,
            "instance_count": 0,
            "selected_instance": None,
            "instances": [],
            "discovery": discovery,
            "reason": f"No installed copy of {plugin_id}:{skill_id} was found in the searched plugin roots.",
        }
    if len(instances) > 1:
        return {
            "status": "duplicate_visible_identity",
            "selection": "auto",
            "plugin_id": plugin_id,
            "skill_id": skill_id,
            "instance_count": len(instances),
            "selected_instance": None,
            "instances": instances,
            "discovery": discovery,
            "reason": (
                "Cowork has more than one installed copy of this skill. "
                "AIWS cannot safely choose which copy to manage."
            ),
        }
    return {
        "status": "ok",
        "selection": "auto",
        "plugin_id": plugin_id,
        "skill_id": skill_id,
        "instance_count": 1,
        "selected_instance": instances[0],
        "instances": instances,
        "discovery": discovery,
    }


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
    base_tree_digest = tree_digest(draft_path) if draft_path.exists() else None
    record = DraftRecord(
        plugin_id=plugin_id,
        skill_id=skill_id,
        origin_marketplace=origin_marketplace,
        origin_repo=origin_repo,
        origin_ref=origin_ref,
        base_version=base_version,
        base_commit=base_commit,
        draft_path=str(draft_path),
        base_tree_digest=base_tree_digest,
        current_tree_digest=base_tree_digest,
        active=True,
        modified=False,
        publish_target=None,
        branch_name=None,
        pr_url=None,
        last_validation_status="not_run",
        last_validation_tree_digest=None,
        updated_at=utc_now(),
    )
    write_json_atomic(draft_record_path(aiws_root, record_id), record.to_json())
    if draft_path.exists():
        write_base_tree_manifest(aiws_root, record_id, draft_path)
        write_base_tree_snapshot(aiws_root, record_id, draft_path)
    return record


def load_draft_record(aiws_root: Path, record_id: str) -> DraftRecord:
    payload = load_json(draft_record_path(aiws_root, record_id))
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Draft record must be a JSON object: {draft_record_path(aiws_root, record_id)}")
    return draft_record_from_payload(payload)


def safely_identify_draft_record(aiws_root: Path, record_id: str) -> DraftRecord:
    record_path = draft_record_path(aiws_root, record_id)
    require_record_path_under(record_path, aiws_root / "state" / "skill-drafts")
    return load_draft_record(aiws_root, record_id)


def draft_summary(record_id: str, record: DraftRecord) -> dict[str, Any]:
    return {
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "origin_marketplace": record.origin_marketplace,
        "origin_repo": record.origin_repo,
        "draft_path": record.draft_path,
        "active": record.active,
        "modified": record.modified,
        "last_validation_status": record.last_validation_status,
        "last_validation_tree_digest": record.last_validation_tree_digest,
    }


def related_drafts(aiws_root: Path, *, plugin_id: str, skill_id: str, exclude_record_id: str | None = None) -> list[dict[str, Any]]:
    state_root = aiws_root / "state" / "skill-drafts"
    if not state_root.exists():
        return []
    require_path_under(state_root, aiws_root / "state", label="Draft state root")
    drafts: list[dict[str, Any]] = []
    for record_path in sorted(state_root.glob("*.json"), key=lambda item: item.name):
        if record_path.name.endswith(".base-tree.json"):
            continue
        if record_path.is_symlink():
            raise SkillManagerError(f"Draft record path must not be a symlink: {record_path}")
        record_id = record_path.stem
        if exclude_record_id is not None and record_id == exclude_record_id:
            continue
        record = load_draft_record(aiws_root, record_id)
        canonical_record_id = draft_id(record.plugin_id, record.skill_id, record.origin_repo)
        if canonical_record_id != record_id:
            raise SkillManagerError(f"Draft record id does not match canonical draft id {canonical_record_id}.")
        if record.plugin_id == plugin_id and record.skill_id == skill_id:
            drafts.append(draft_summary(record_id, record))
    return drafts


def persist_validation_status(aiws_root: Path, record_id: str, status: str) -> DraftRecord:
    record = safely_identify_draft_record(aiws_root, record_id)
    validation_tree_digest = record.current_tree_digest if status == "passed" else None
    updated = DraftRecord(
        **{
            **record.to_json(),
            "last_validation_status": status,
            "last_validation_tree_digest": validation_tree_digest,
            "updated_at": utc_now(),
        }
    )
    write_json_atomic(draft_record_path(aiws_root, record_id), updated.to_json())
    return updated


def persist_validation_failure(aiws_root: Path, record_id: str, *, digest_failed: bool) -> DraftRecord:
    record = safely_identify_draft_record(aiws_root, record_id)
    updates: dict[str, Any] = {
        "last_validation_status": "failed",
        "last_validation_tree_digest": None,
        "updated_at": utc_now(),
    }
    if digest_failed:
        updates.update({"modified": True, "current_tree_digest": None})
    updated = DraftRecord(**{**record.to_json(), **updates})
    write_json_atomic(draft_record_path(aiws_root, record_id), updated.to_json())
    return updated


def persist_stage_validation_result(
    aiws_root: Path,
    record_id: str,
    *,
    status: str,
    current_tree_digest: str | None,
    modified: bool,
) -> DraftRecord:
    record = safely_identify_draft_record(aiws_root, record_id)
    validation_tree_digest = current_tree_digest if status == "passed" else None
    updated = DraftRecord(
        **{
            **record.to_json(),
            "current_tree_digest": current_tree_digest,
            "modified": modified,
            "last_validation_status": status,
            "last_validation_tree_digest": validation_tree_digest,
            "updated_at": utc_now(),
        }
    )
    write_json_atomic(draft_record_path(aiws_root, record_id), updated.to_json())
    return updated


def require_non_blank_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SkillManagerError(f"{field_name} must be a non-blank string.")
    return value.strip()


def require_marketplace_id(value: Any) -> str:
    marketplace_id = require_non_blank_string(value, "marketplace_id")
    if not NAME_RE.fullmatch(marketplace_id):
        raise SkillManagerError(f"marketplace_id contains unsupported characters: {marketplace_id!r}")
    return marketplace_id


def require_backend_kind(value: Any) -> str:
    backend_kind = require_non_blank_string(value, "backend_kind").lower()
    if backend_kind not in {"github", "google_drive"}:
        raise SkillManagerError(f"backend_kind is not supported: {backend_kind!r}")
    return backend_kind


def ensure_marketplace_registration(
    aiws_root: Path,
    *,
    marketplace_id: str,
    scope_id: str,
    backend_kind: str,
    backend_ref: str,
) -> dict[str, Any]:
    registry = load_marketplace_registry(aiws_root)
    marketplaces = registry.setdefault("marketplaces", {})
    existing = marketplaces.get(marketplace_id)
    normalized = {
        "marketplace_id": marketplace_id,
        "scope_id": scope_id,
        "backend_kind": backend_kind,
        "backend_ref": backend_ref,
    }
    if existing is None:
        marketplaces[marketplace_id] = normalized
        write_marketplace_registry(aiws_root, registry)
        return normalized
    if existing != normalized:
        raise SkillManagerError(
            f"marketplace_id {marketplace_id!r} is already registered with different identity metadata."
        )
    return existing


def require_host_id(value: Any) -> str:
    host_id = require_non_blank_string(value, "host_id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", host_id):
        raise SkillManagerError(f"host_id contains unsupported characters: {host_id!r}")
    return host_id


def require_canonical_draft_record(aiws_root: Path, record_id: str) -> DraftRecord:
    record = safely_identify_draft_record(aiws_root, record_id)
    canonical_record_id = draft_id(record.plugin_id, record.skill_id, record.origin_repo)
    if canonical_record_id != record_id:
        raise SkillManagerError(f"Draft record id does not match canonical draft id {canonical_record_id}.")
    return record


def proposal_record_path(aiws_root: Path, proposal_id: str) -> Path:
    return aiws_root / "state" / "skill-proposals" / f"{proposal_id}.json"


def proposal_state_root(aiws_root: Path) -> Path:
    return aiws_root / "state" / "skill-proposals"


def marketplace_registry_path(aiws_root: Path) -> Path:
    return aiws_root / "state" / "marketplace-registry.json"


def require_proposal_path_under(path: Path, root: Path) -> Path:
    reject_symlinked_root(root.parent, label="AIWS proposal state parent")
    reject_symlinked_root(root, label="AIWS proposal state root")
    absolute_path = path.absolute()
    absolute_root = root.absolute()
    if absolute_path == absolute_root:
        raise SkillManagerError(f"Proposal path is outside AIWS proposal state root: {path}")
    try:
        absolute_path.relative_to(absolute_root)
    except ValueError as exc:
        raise SkillManagerError(f"Proposal path is outside AIWS proposal state root: {path}") from exc
    return absolute_path


def validate_proposal_write_path(path: Path, root: Path) -> Path:
    require_proposal_path_under(path, root)
    reject_existing_symlink_components(path.parent, label="Proposal path parent")
    if path.is_symlink():
        raise SkillManagerError(f"Proposal path must not be a symlink: {path}")
    temp_path = path.with_suffix(path.suffix + ".tmp")
    reject_existing_symlink_components(temp_path.parent, label="Proposal temporary path parent")
    if temp_path.is_symlink():
        raise SkillManagerError(f"Proposal temporary path must not be a symlink: {temp_path}")
    return temp_path


def write_json_exclusive_via_temp(path: Path, payload: dict[str, Any]) -> bool:
    proposal_root = path.parent
    temp_path = validate_proposal_write_path(path, proposal_root)
    proposal_root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return False
    if temp_path.exists():
        return False

    try:
        with temp_path.open("x") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        os.link(temp_path, path)
    except FileExistsError:
        return False
    finally:
        remove_package_file(temp_path)
    return True


def load_proposal_record(aiws_root: Path, proposal_id: str) -> dict[str, Any]:
    proposal_id = require_non_blank_string(proposal_id, "proposal_id")
    if "/" in proposal_id or "\\" in proposal_id or ".." in proposal_id:
        raise SkillManagerError(f"Invalid proposal_id: {proposal_id}")
    proposal_root = proposal_state_root(aiws_root)
    proposal_path = proposal_record_path(aiws_root, proposal_id)
    require_proposal_path_under(proposal_path, proposal_root)
    if not proposal_path.exists():
        raise SkillManagerError(f"Proposal record not found: {proposal_id}")
    if proposal_path.is_symlink():
        raise SkillManagerError(f"Proposal path must not be a symlink: {proposal_path}")
    payload = load_json(proposal_path)
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Proposal record must be a JSON object: {proposal_path}")
    if payload.get("proposal_id") != proposal_id:
        raise SkillManagerError(f"Proposal record id does not match requested proposal_id {proposal_id}.")
    return payload


def write_proposal_record(aiws_root: Path, proposal_id: str, payload: dict[str, Any]) -> None:
    proposal_root = proposal_state_root(aiws_root)
    proposal_path = proposal_record_path(aiws_root, proposal_id)
    require_proposal_path_under(proposal_path, proposal_root)
    write_json_atomic(proposal_path, payload)


def load_marketplace_registry(aiws_root: Path) -> dict[str, Any]:
    path = marketplace_registry_path(aiws_root)
    if not path.exists():
        return {"marketplaces": {}}
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Marketplace registry must be a JSON object: {path}")
    marketplaces = payload.get("marketplaces")
    if not isinstance(marketplaces, dict):
        raise SkillManagerError(f"Marketplace registry is invalid: {path}")
    return payload


def write_marketplace_registry(aiws_root: Path, payload: dict[str, Any]) -> None:
    path = marketplace_registry_path(aiws_root)
    write_json_atomic(path, payload)


def remove_package_file(path: Path | None) -> None:
    if path is not None and path.exists() and not path.is_symlink() and path.is_file():
        path.unlink()


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
    allow_parallel_draft: bool = False,
) -> DraftRecord:
    reject_tree_symlinks(source_plugin_root, label="Source plugin tree")
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
        existing_identity = draft_id(existing.plugin_id, existing.skill_id, existing.origin_repo)
        if (
            existing_identity != record_id
            or existing.plugin_id != plugin_id
            or existing.skill_id != skill_id
            or existing.origin_repo != origin_repo
        ):
            raise SkillManagerError(f"Draft record {record_id} does not match requested draft identity.")
        existing_draft_path = require_path_under(Path(existing.draft_path), plugins_root, label="Draft path")
        recorded_draft_path = require_path_under(
            draft_worktree_path(aiws_root, existing.origin_marketplace, existing.plugin_id, existing.origin_repo),
            plugins_root,
            label="Recorded draft path",
        )
        if existing_draft_path != recorded_draft_path:
            raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")
        if existing_draft_path.exists():
            refreshed = refresh_modified_status(aiws_root, record_id)
            if not draft_base_tree_path(aiws_root, record_id).exists() and not refreshed.modified:
                write_base_tree_manifest(aiws_root, record_id, existing_draft_path)
            if not draft_base_snapshot_path(aiws_root, record_id).exists() and not refreshed.modified:
                ensure_base_tree_snapshot(aiws_root, record_id, existing_draft_path, refreshed)
            return refreshed

    if not allow_parallel_draft:
        blocking_drafts = [
            draft
            for draft in related_drafts(
                aiws_root,
                plugin_id=plugin_id,
                skill_id=skill_id,
                exclude_record_id=record_id,
            )
            if draft["active"]
        ]
        if blocking_drafts:
            draft_ids = ", ".join(draft["draft_id"] for draft in blocking_drafts)
            raise SkillManagerError(
                "Existing active draft for this plugin and skill must be reused, staged, reverted, "
                f"or explicitly bypassed with allow_parallel_draft=true before opening another draft: {draft_ids}"
            )

    if expected_draft_path.exists():
        raise SkillManagerError(f"Draft path already exists without a usable record: {expected_draft_path}")

    expected_draft_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_plugin_root, expected_draft_path)
    base_tree_digest = tree_digest(expected_draft_path)
    write_base_tree_manifest(aiws_root, record_id, expected_draft_path)
    write_base_tree_snapshot(aiws_root, record_id, expected_draft_path)

    record = DraftRecord(
        plugin_id=plugin_id,
        skill_id=skill_id,
        origin_marketplace=origin_marketplace,
        origin_repo=origin_repo,
        origin_ref=origin_ref,
        base_version=base_version,
        base_commit=base_commit,
        draft_path=str(expected_draft_path),
        base_tree_digest=base_tree_digest,
        current_tree_digest=base_tree_digest,
        active=True,
        modified=False,
        publish_target=None,
        branch_name=None,
        pr_url=None,
        last_validation_status="passed",
        last_validation_tree_digest=base_tree_digest,
        updated_at=utc_now(),
    )
    write_json_atomic(record_path, record.to_json())
    return record


def refresh_modified_status(aiws_root: Path, record_id: str) -> DraftRecord:
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

    current_tree_digest = tree_digest(draft_path)
    if record.base_tree_digest is None and record.modified:
        base_tree_digest = None
        modified = True
    else:
        base_tree_digest = record.base_tree_digest or current_tree_digest
        modified = current_tree_digest != base_tree_digest
    if (
        record.base_tree_digest == base_tree_digest
        and record.current_tree_digest == current_tree_digest
        and record.modified == modified
    ):
        return record

    refreshed = DraftRecord(
        **{
            **record.to_json(),
            "base_tree_digest": base_tree_digest,
            "current_tree_digest": current_tree_digest,
            "modified": modified,
            "updated_at": utc_now(),
        }
    )
    write_json_atomic(record_path, refreshed.to_json())
    return refreshed


def draft_skill_root(aiws_root: Path, record_id: str) -> tuple[DraftRecord, Path, Path]:
    record = safely_identify_draft_record(aiws_root, record_id)
    plugins_root = aiws_root / "plugins"
    draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
    expected_draft_path = require_path_under(
        draft_worktree_path(aiws_root, record.origin_marketplace, record.plugin_id, record.origin_repo),
        plugins_root,
        label="Expected draft path",
    )
    if draft_path != expected_draft_path:
        raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")
    skill_root = require_path_under(draft_path / "skills" / record.skill_id, plugins_root, label="Draft skill path")
    if not skill_root.is_dir():
        raise SkillManagerError(f"Draft skill path is not a directory: {skill_root}")
    return record, draft_path, skill_root


def resolve_draft_skill_file(aiws_root: Path, record_id: str, relative_path: str) -> tuple[DraftRecord, Path, Path]:
    relative_path = require_non_blank_string(relative_path, "relative_path")
    path = Path(relative_path)
    if path.is_absolute() or ".." in path.parts:
        raise SkillManagerError(f"Draft file path is outside the managed skill folder: {relative_path}")
    record, _draft_path, skill_root = draft_skill_root(aiws_root, record_id)
    allowed_prefix = Path("skills") / record.skill_id
    try:
        suffix = path.relative_to(allowed_prefix)
    except ValueError as exc:
        raise SkillManagerError(f"Draft file path is outside the managed skill folder: {relative_path}") from exc
    if not suffix.parts:
        raise SkillManagerError(f"Draft file path must identify a file under the managed skill folder: {relative_path}")
    target = skill_root / suffix
    reject_symlinked_child_path(target, skill_root, label="Draft file path")
    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(skill_root.resolve())
    except ValueError as exc:
        raise SkillManagerError(f"Draft file path is outside the managed skill folder: {relative_path}") from exc
    return record, skill_root, resolved


def list_draft_files(aiws_root: Path, record_id: str) -> dict[str, Any]:
    record, _draft_path, skill_root = draft_skill_root(aiws_root, record_id)
    files: list[str] = []
    for path in sorted(skill_root.rglob("*"), key=lambda item: item.relative_to(skill_root).as_posix()):
        if path.is_symlink():
            raise SkillManagerError(f"Draft path must not contain symlinks: {path}")
        if path.is_file():
            files.append((Path("skills") / record.skill_id / path.relative_to(skill_root)).as_posix())
        elif not path.is_dir():
            raise SkillManagerError(f"Unsupported draft tree entry: {path}")
    return {"status": "ok", "record_id": record_id, "plugin_id": record.plugin_id, "skill_id": record.skill_id, "files": files}


def read_draft_file(aiws_root: Path, record_id: str, relative_path: str) -> dict[str, Any]:
    record, _skill_root, target = resolve_draft_skill_file(aiws_root, record_id, relative_path)
    if not target.is_file():
        raise SkillManagerError(f"Draft file not found: {relative_path}")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillManagerError(f"Draft file is not valid UTF-8 text: {relative_path}") from exc
    return {
        "status": "ok",
        "record_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "relative_path": relative_path,
        "content": content,
    }


def write_draft_file(aiws_root: Path, record_id: str, relative_path: str, content: str) -> dict[str, Any]:
    if not isinstance(content, str):
        raise SkillManagerError("content must be a string.")
    record, skill_root, target = resolve_draft_skill_file(aiws_root, record_id, relative_path)
    reject_existing_symlink_components(target.parent, label="Draft file parent")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not target.is_file():
        raise SkillManagerError(f"Draft file path is not a file: {relative_path}")
    if target.is_symlink():
        raise SkillManagerError(f"Draft file path must not be a symlink: {relative_path}")
    temp_path = target.with_suffix(target.suffix + ".tmp")
    if temp_path.exists() and temp_path.is_symlink():
        raise SkillManagerError(f"Draft file temporary path must not be a symlink: {relative_path}")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(target)
    refreshed = refresh_modified_status(aiws_root, record_id)
    return {
        "status": "written",
        "record_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "relative_path": relative_path,
        "modified": refreshed.modified,
        "skill_root": str(skill_root),
    }


def delete_draft_file(aiws_root: Path, record_id: str, relative_path: str) -> dict[str, Any]:
    record, skill_root, target = resolve_draft_skill_file(aiws_root, record_id, relative_path)
    if not target.exists():
        raise SkillManagerError(f"Draft file not found: {relative_path}")
    if target.is_symlink():
        raise SkillManagerError(f"Draft file path must not be a symlink: {relative_path}")
    if not target.is_file():
        raise SkillManagerError(f"Draft file path is not a file: {relative_path}")
    target.unlink()
    parent = target.parent
    while parent != skill_root and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    refreshed = refresh_modified_status(aiws_root, record_id)
    return {
        "status": "deleted",
        "record_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "relative_path": relative_path,
        "modified": refreshed.modified,
    }


def package_path_for_record(package_output_dir: Path, record_id: str) -> Path:
    return package_output_dir / f"{record_id}.zip"


def reject_output_dir_inside_draft(package_output_dir: Path, draft_path: Path) -> None:
    draft_resolved = draft_path.resolve()
    output_resolved = package_output_dir.resolve(strict=False)
    if output_resolved == draft_resolved:
        raise SkillManagerError(f"Package output directory must not be inside the draft tree: {package_output_dir}")
    try:
        output_resolved.relative_to(draft_resolved)
    except ValueError:
        return
    raise SkillManagerError(f"Package output directory must not be inside the draft tree: {package_output_dir}")


def path_is_at_or_under(path: Path, root: Path) -> bool:
    absolute_path = path.absolute()
    absolute_root = root.absolute()
    if absolute_path == absolute_root:
        return True
    try:
        absolute_path.relative_to(absolute_root)
    except ValueError:
        return False
    return True


def path_is_under_claude_memory_data(path: Path) -> bool:
    parts = path.absolute().parts
    lowered_parts = [part.lower() for part in parts]
    marker = (".claude", "plugins", "data")
    for index in range(0, len(lowered_parts) - len(marker) + 1):
        if tuple(lowered_parts[index : index + len(marker)]) != marker:
            continue
        return any("memory" in part for part in lowered_parts[index + len(marker) :])
    return False


def path_is_at_or_under_dot_claude(path: Path) -> bool:
    return ".claude" in [part.lower() for part in path.absolute().parts]


def reject_disallowed_package_output_dir(aiws_root: Path, package_output_dir: Path) -> None:
    disallowed_roots = (aiws_root / "memory", aiws_root / "imports", aiws_root / "exports")
    for root in disallowed_roots:
        if path_is_at_or_under(package_output_dir, root):
            raise SkillManagerError(f"Package output directory is under a disallowed package output directory: {root}")
    if path_is_at_or_under_dot_claude(package_output_dir):
        raise SkillManagerError("Package output directory is under a disallowed package output directory: .claude")
    if path_is_under_claude_memory_data(package_output_dir):
        raise SkillManagerError(
            "Package output directory is under a disallowed package output directory: .claude/plugins/data/*memory*"
        )


def validate_package_output_dir(
    aiws_root: Path, package_output_dir: Path, draft_path: Path, record_id: str
) -> tuple[Path, Path]:
    if package_output_dir is None:
        raise SkillManagerError("Package output directory is required.")
    reject_existing_symlink_components(package_output_dir.parent, label="Package output directory parent")
    if package_output_dir.is_symlink():
        raise SkillManagerError(f"Package output directory must not be a symlink: {package_output_dir}")
    reject_disallowed_package_output_dir(aiws_root, package_output_dir)
    reject_output_dir_inside_draft(package_output_dir, draft_path)
    if package_output_dir.exists() and not package_output_dir.is_dir():
        raise SkillManagerError(f"Package output path is not a directory: {package_output_dir}")

    package_path = package_path_for_record(package_output_dir, record_id)
    reject_existing_symlink_components(package_path.parent, label="Package path parent")
    if package_path.is_symlink():
        raise SkillManagerError(f"Package path must not be a symlink: {package_path}")
    temp_path = package_output_dir / f".{record_id}.zip.tmp"
    reject_existing_symlink_components(temp_path.parent, label="Temporary package path parent")
    if temp_path.is_symlink():
        raise SkillManagerError(f"Temporary package path must not be a symlink: {temp_path}")
    return package_path, temp_path


def zip_entry_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise SkillManagerError(f"Unsafe package entry path: {path}")
    entry_name = relative.as_posix()
    if not entry_name or entry_name.startswith("/"):
        raise SkillManagerError(f"Unsafe package entry path: {path}")
    return entry_name


def build_draft_package(aiws_root: Path, record_id: str, package_output_dir: Path) -> dict[str, Any]:
    safely_identify_draft_record(aiws_root, record_id)
    package_path: Path | None = None
    temp_path: Path | None = None
    refresh_completed = False
    try:
        record = refresh_modified_status(aiws_root, record_id)
        refresh_completed = True
        draft_path = require_path_under(Path(record.draft_path), aiws_root / "plugins", label="Draft path")
        package_path, temp_path = validate_package_output_dir(aiws_root, package_output_dir, draft_path, record_id)

        validation = validate_plugin(draft_path, expected_name=record.plugin_id, expected_version=record.base_version)
        skill_names = {skill["name"] for skill in validation["skills"]}
        if record.skill_id not in skill_names:
            raise SkillManagerError(f"Requested skill {record.skill_id!r} does not exist in plugin {record.plugin_id!r}.")

        package_output_dir.mkdir(parents=True, exist_ok=True)
        if temp_path.exists():
            temp_path.unlink()

        with zipfile.ZipFile(temp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            for path in sorted(draft_path.rglob("*"), key=lambda item: item.relative_to(draft_path).as_posix()):
                if path.is_symlink():
                    raise SkillManagerError(f"Draft path must not contain symlinks: {path}")
                if path.is_dir():
                    continue
                if not path.is_file():
                    raise SkillManagerError(f"Unsupported draft tree entry: {path}")
                package.write(path, zip_entry_name(path, draft_path))
        temp_path.replace(package_path)
        record = persist_validation_status(aiws_root, record_id, "passed")
    except Exception:
        remove_package_file(temp_path)
        remove_package_file(package_path)
        persist_validation_failure(aiws_root, record_id, digest_failed=not refresh_completed)
        raise

    return {
        "status": "packaged",
        "record_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "package_path": str(package_path),
        "modified": record.modified,
        "status_label": "Modified locally" if record.modified else "Current",
        "validation_status": "passed",
        "validation_tree_digest": record.last_validation_tree_digest,
        "current_tree_digest": record.current_tree_digest,
        "package_layout": "cowork_flat_root",
    }


def copy_package_to_upload_surface(package_path: Path, package_upload_dir: Path) -> dict[str, Any]:
    package_path = package_path.expanduser()
    reject_existing_symlink_components(package_path.parent, label="Package handoff source parent")
    if package_path.is_symlink():
        raise SkillManagerError(f"Package handoff source must not be a symlink: {package_path}")
    if not package_path.is_file():
        raise SkillManagerError(f"Package handoff source must be a regular file: {package_path}")
    package_path = package_path.resolve()

    package_upload_dir = package_upload_dir.expanduser()
    reject_existing_symlink_components(package_upload_dir, label="Cowork package upload surface")
    if package_upload_dir.is_symlink():
        raise SkillManagerError(f"Cowork package upload surface must not be a symlink: {package_upload_dir}")
    if not package_upload_dir.exists():
        raise SkillManagerError(f"Cowork package upload surface must already exist: {package_upload_dir}")
    if not package_upload_dir.is_dir():
        raise SkillManagerError(f"Cowork package upload surface must be a directory: {package_upload_dir}")

    upload_root = package_upload_dir.resolve()
    destination = upload_root / package_path.name
    reject_existing_symlink_components(destination.parent, label="Cowork package handoff destination parent")
    if destination.is_symlink():
        raise SkillManagerError(f"Cowork package handoff destination must not be a symlink: {destination}")
    if destination.exists():
        if not destination.is_file():
            raise SkillManagerError(f"Cowork package handoff destination is not a regular file: {destination}")
        if destination.read_bytes() != package_path.read_bytes():
            raise SkillManagerError(
                f"Cowork package handoff destination already exists with different content: {destination}"
            )
    else:
        with destination.open("xb") as handle:
            handle.write(package_path.read_bytes())
    return {
        "handoff_status": "handoff_prepared",
        "package_upload_surface": str(upload_root),
        "copied_package_path": str(destination),
    }


def validate_draft(aiws_root: Path, record_id: str) -> dict[str, Any]:
    record_id = require_non_blank_string(record_id, "record_id")
    record = safely_identify_draft_record(aiws_root, record_id)
    canonical_record_id = draft_id(record.plugin_id, record.skill_id, record.origin_repo)
    if canonical_record_id != record_id:
        persist_validation_failure(aiws_root, record_id, digest_failed=True)
        raise SkillManagerError(f"Draft record id does not match canonical draft id {canonical_record_id}.")

    plugins_root = aiws_root / "plugins"
    try:
        draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
        expected_draft_path = require_path_under(
            draft_worktree_path(aiws_root, record.origin_marketplace, record.plugin_id, record.origin_repo),
            plugins_root,
            label="Expected draft path",
        )
        if draft_path != expected_draft_path:
            persist_validation_failure(aiws_root, record_id, digest_failed=True)
            raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")

        current_tree_digest = tree_digest(draft_path)
    except Exception:
        persist_validation_failure(aiws_root, record_id, digest_failed=True)
        raise

    modified = record.base_tree_digest is not None and current_tree_digest != record.base_tree_digest
    if record.base_tree_digest is None:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=True,
        )
        raise SkillManagerError(f"Draft record {record_id} has no base_tree_digest; cannot validate draft.")

    try:
        require_changes_only_under_skill(aiws_root, record_id, draft_path, record.skill_id)
        validation = validate_plugin(draft_path, expected_name=record.plugin_id, expected_version=record.base_version)
        skill_names = {skill["name"] for skill in validation["skills"]}
        if record.skill_id not in skill_names:
            raise SkillManagerError(f"Requested skill {record.skill_id!r} does not exist in plugin {record.plugin_id!r}.")
    except Exception:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=modified,
        )
        raise

    record = persist_stage_validation_result(
        aiws_root,
        record_id,
        status="passed",
        current_tree_digest=current_tree_digest,
        modified=modified,
    )
    return {
        "status": "validated",
        "record_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "modified": record.modified,
        "status_label": "Modified locally" if record.modified else "Current",
        "validation_status": "passed",
        "validation_tree_digest": current_tree_digest,
        "current_tree_digest": current_tree_digest,
    }


def draft_activation_root(aiws_root: Path) -> Path:
    return aiws_root / "state" / "draft-activations"


def draft_activation_record_path(aiws_root: Path, host_id: str, record_id: str) -> Path:
    return draft_activation_root(aiws_root) / require_host_id(host_id) / f"{record_id}.json"


def write_draft_activation_record(
    aiws_root: Path,
    *,
    record_id: str,
    host_kind: str,
    host_id: str,
    record: DraftRecord,
    package: dict[str, Any],
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = draft_activation_root(aiws_root)
    path = draft_activation_record_path(aiws_root, host_id, record_id)
    require_activation_path_under(path, root)
    require_activation_path_under(path.with_suffix(path.suffix + ".tmp"), root)
    now = utc_now()
    payload = {
        "status": "pending_upload",
        "activation_status": "pending_upload",
        "draft_id": record_id,
        "record_id": record_id,
        "host_kind": host_kind,
        "host_id": host_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "origin_marketplace": record.origin_marketplace,
        "origin_repo": record.origin_repo,
        "base_version": record.base_version,
        "package_path": package["package_path"],
        "validation_status": package.get("validation_status"),
        "validation_tree_digest": package.get("validation_tree_digest"),
        "current_tree_digest": package.get("current_tree_digest"),
        "created_at": now,
        "updated_at": now,
    }
    if handoff:
        payload.update(handoff)
    write_json_atomic(path, payload)
    return {"activation_record_path": str(path), **payload}


def deactivate_draft(aiws_root: Path, record_id: str, host_kind: str, host_id: str) -> dict[str, Any]:
    if host_kind != "cowork":
        raise SkillManagerError("Only host_kind='cowork' is supported for draft deactivation in this slice.")
    host_id = require_host_id(host_id)
    record = require_canonical_draft_record(aiws_root, record_id)
    path = draft_activation_record_path(aiws_root, host_id, record_id)
    require_activation_path_under(path, draft_activation_root(aiws_root))
    if not path.exists():
        return {
            "status": "inactive",
            "activation_status": "inactive",
            "record_id": record_id,
            "draft_id": record_id,
            "host_kind": host_kind,
            "host_id": host_id,
            "plugin_id": record.plugin_id,
            "skill_id": record.skill_id,
            "cleared": False,
        }
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Activation record must be a JSON object: {path}")
    if payload.get("draft_id") != record_id:
        raise SkillManagerError(f"Activation record draft_id does not match requested draft: {record_id}")
    path.unlink()
    return {
        "status": "deactivated",
        "activation_status": "inactive",
        "record_id": record_id,
        "draft_id": record_id,
        "host_kind": host_kind,
        "host_id": host_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "cleared": True,
    }


def require_text_plugin_tree(root: Path, *, label: str) -> None:
    reject_tree_symlinks(root, label=label)
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_dir():
            continue
        try:
            path.read_text()
        except UnicodeDecodeError as exc:
            raise SkillManagerError(f"{label} contains binary or non-UTF-8 content: {path.relative_to(root).as_posix()}") from exc
        if b"\0" in path.read_bytes():
            raise SkillManagerError(f"{label} contains binary content: {path.relative_to(root).as_posix()}")


def require_plugin_contains_skill(plugin_root: Path, plugin_id: str, skill_id: str) -> dict[str, Any]:
    validation = validate_plugin(plugin_root, expected_name=plugin_id)
    skill_names = {skill["name"] for skill in validation["skills"]}
    if skill_id not in skill_names:
        raise SkillManagerError(f"Requested skill {skill_id!r} does not exist in plugin {plugin_id!r}.")
    return validation


def copy_update_tree(source: Path, destination: Path, *, label: str) -> None:
    source = Path(source).expanduser()
    require_text_plugin_tree(source, label=label)
    if destination.exists():
        raise SkillManagerError(f"Update candidate destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, symlinks=False)


def create_update_candidate(
    aiws_root: Path,
    record_id: str,
    base_plugin_root: Path,
    remote_plugin_root: Path,
) -> dict[str, Any]:
    record = require_canonical_draft_record(aiws_root, require_non_blank_string(record_id, "record_id"))
    base_plugin_root = Path(base_plugin_root).expanduser()
    remote_plugin_root = Path(remote_plugin_root).expanduser()
    require_text_plugin_tree(base_plugin_root, label="Base update candidate tree")
    require_text_plugin_tree(remote_plugin_root, label="Remote update candidate tree")
    require_plugin_contains_skill(base_plugin_root, record.plugin_id, record.skill_id)
    remote_validation = require_plugin_contains_skill(remote_plugin_root, record.plugin_id, record.skill_id)
    base_digest = tree_digest(base_plugin_root)
    if record.base_tree_digest is not None and base_digest != record.base_tree_digest:
        raise SkillManagerError("Update candidate base tree does not match the draft base digest.")
    remote_digest = tree_digest(remote_plugin_root)
    candidate_id = "updcand_" + uuid.uuid4().hex
    root = update_candidate_root(aiws_root)
    candidate_dir = root / candidate_id
    require_update_state_path_under(candidate_dir, root)
    copied_base = candidate_dir / "base"
    copied_remote = candidate_dir / "remote"
    copy_update_tree(base_plugin_root, copied_base, label="Base update candidate tree")
    copy_update_tree(remote_plugin_root, copied_remote, label="Remote update candidate tree")
    payload = {
        "candidate_id": candidate_id,
        "update_candidate_id": candidate_id,
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "base_plugin_root": str(copied_base),
        "remote_plugin_root": str(copied_remote),
        "base_tree_digest": base_digest,
        "remote_tree_digest": remote_digest,
        "remote_version": remote_validation["version"],
        "created_at": utc_now(),
    }
    path = update_candidate_record_path(aiws_root, candidate_id)
    require_update_state_path_under(path, root)
    write_json_atomic(path, payload)
    return {
        "status": "created",
        "update_candidate_id": candidate_id,
        "candidate_id": candidate_id,
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "base_tree_digest": base_digest,
        "remote_tree_digest": remote_digest,
        "remote_version": remote_validation["version"],
    }


def prepare_update_candidate(aiws_root: Path, record_id: str, remote_plugin_root: Path) -> dict[str, Any]:
    record_id = require_non_blank_string(record_id, "record_id")
    record = refresh_modified_status(aiws_root, record_id)
    draft_path = require_path_under(Path(record.draft_path), aiws_root / "plugins", label="Draft path")
    base_snapshot = ensure_base_tree_snapshot(aiws_root, record_id, draft_path, record)
    remote_plugin_root = Path(remote_plugin_root).expanduser()
    require_text_plugin_tree(remote_plugin_root, label="Remote update candidate tree")
    remote_validation = require_plugin_contains_skill(remote_plugin_root, record.plugin_id, record.skill_id)
    remote_digest = tree_digest(remote_plugin_root)
    if remote_digest == record.base_tree_digest:
        return {
            "status": "no_update_available",
            "draft_id": record_id,
            "plugin_id": record.plugin_id,
            "skill_id": record.skill_id,
            "base_version": record.base_version,
            "remote_version": remote_validation["version"],
            "base_tree_digest": record.base_tree_digest,
            "remote_tree_digest": remote_digest,
            "update_candidate_id": None,
        }
    candidate = create_update_candidate(aiws_root, record_id, base_snapshot, remote_plugin_root)
    return {
        **candidate,
        "status": "update_candidate_created",
        "update_available": True,
    }


def load_update_candidate(aiws_root: Path, candidate_id: str) -> dict[str, Any]:
    candidate_id = require_non_blank_string(candidate_id, "update_candidate_id")
    path = update_candidate_record_path(aiws_root, candidate_id)
    require_update_state_path_under(path, update_candidate_root(aiws_root))
    if not path.is_file():
        raise SkillManagerError(f"Update candidate not found: {candidate_id}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Update candidate must be a JSON object: {path}")
    return payload


def load_update_review(aiws_root: Path, review_id: str) -> dict[str, Any]:
    review_id = require_non_blank_string(review_id, "review_id")
    path = update_review_record_path(aiws_root, review_id)
    require_update_state_path_under(path, update_review_root(aiws_root))
    if not path.is_file():
        raise SkillManagerError(f"Update review not found: {review_id}")
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise SkillManagerError(f"Update review must be a JSON object: {path}")
    return payload


def changed_paths_between(base_root: Path, other_root: Path) -> list[str]:
    base = tree_file_hashes(base_root)
    other = tree_file_hashes(other_root)
    paths = sorted(set(base) | set(other))
    return [path for path in paths if base.get(path) != other.get(path)]


def split_non_skill_changes(paths: list[str], skill_id: str) -> list[str]:
    allowed_prefix = f"skills/{skill_id}/"
    return [path for path in paths if not path.startswith(allowed_prefix)]


def read_tree_text(root: Path, relative_path: str) -> list[str]:
    path = root / relative_path
    if not path.exists():
        return []
    if path.is_dir():
        return []
    try:
        return path.read_text().splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise SkillManagerError(f"Cannot diff binary or non-UTF-8 file: {relative_path}") from exc


def unified_tree_diff(base_root: Path, other_root: Path, changed_paths: list[str], *, label: str) -> dict[str, Any]:
    chunks: list[str] = []
    truncated = False
    for relative_path in changed_paths:
        base_lines = read_tree_text(base_root, relative_path)
        other_lines = read_tree_text(other_root, relative_path)
        diff = difflib.unified_diff(
            base_lines,
            other_lines,
            fromfile=f"base/{relative_path}",
            tofile=f"{label}/{relative_path}",
        )
        chunks.extend(diff)
        content = "".join(chunks)
        if len(content) > UPDATE_DIFF_PREVIEW_LIMIT:
            truncated = True
            content = content[:UPDATE_DIFF_PREVIEW_LIMIT]
            return {
                "content": content,
                "truncated": True,
                "limit": UPDATE_DIFF_PREVIEW_LIMIT,
                "changed_files": changed_paths,
            }
    return {
        "content": "".join(chunks),
        "truncated": truncated,
        "limit": UPDATE_DIFF_PREVIEW_LIMIT,
        "changed_files": changed_paths,
    }


def pending_upload_records(aiws_root: Path, record_id: str) -> list[dict[str, Any]]:
    root = draft_activation_root(aiws_root)
    if not root.exists():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(root.glob(f"*/{record_id}.json")):
        require_activation_path_under(path, root)
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise SkillManagerError(f"Activation record must be a JSON object: {path}")
        if payload.get("draft_id") != record_id:
            raise SkillManagerError(f"Activation record draft_id does not match requested draft: {record_id}")
        if payload.get("activation_status") == "pending_upload" or payload.get("status") == "pending_upload":
            records.append({"path": path, "payload": payload})
    return records


def pending_upload_summary(aiws_root: Path, record_id: str) -> dict[str, Any]:
    records = pending_upload_records(aiws_root, record_id)
    return {
        "present": bool(records),
        "count": len(records),
        "hosts": [item["payload"].get("host_id") for item in records],
    }


def pending_upload_digest(aiws_root: Path, record_id: str) -> str:
    records = pending_upload_records(aiws_root, record_id)
    stable = [
        {
            "host_id": item["payload"].get("host_id"),
            "host_kind": item["payload"].get("host_kind"),
            "package_path": item["payload"].get("package_path"),
            "activation_status": item["payload"].get("activation_status"),
            "status": item["payload"].get("status"),
            "validation_tree_digest": item["payload"].get("validation_tree_digest"),
            "current_tree_digest": item["payload"].get("current_tree_digest"),
        }
        for item in records
    ]
    content = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def clear_pending_upload_records(aiws_root: Path, record_id: str) -> int:
    records = pending_upload_records(aiws_root, record_id)
    for item in records:
        item["path"].unlink()
    return len(records)


def review_update_conflict(aiws_root: Path, record_id: str, update_candidate_id: str) -> dict[str, Any]:
    record = refresh_modified_status(aiws_root, require_non_blank_string(record_id, "record_id"))
    candidate = load_update_candidate(aiws_root, update_candidate_id)
    if candidate.get("draft_id") != record_id:
        raise SkillManagerError("Update candidate draft_id does not match requested draft.")
    if candidate.get("plugin_id") != record.plugin_id or candidate.get("skill_id") != record.skill_id:
        raise SkillManagerError("Update candidate identity does not match requested draft.")
    plugins_root = aiws_root / "plugins"
    draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
    candidate_root = update_candidate_root(aiws_root)
    base_root = require_update_state_path_under(Path(str(candidate["base_plugin_root"])), candidate_root)
    remote_root = require_update_state_path_under(Path(str(candidate["remote_plugin_root"])), candidate_root)
    require_plugin_contains_skill(remote_root, record.plugin_id, record.skill_id)
    base_digest = tree_digest(base_root)
    current_digest = tree_digest(draft_path)
    remote_digest = tree_digest(remote_root)
    if base_digest != candidate.get("base_tree_digest") or base_digest != record.base_tree_digest:
        raise SkillManagerError("Update candidate base digest does not match the draft base.")
    if remote_digest != candidate.get("remote_tree_digest"):
        raise SkillManagerError("Update candidate remote digest changed after creation.")
    local_changed = changed_paths_between(base_root, draft_path)
    remote_changed = changed_paths_between(base_root, remote_root)
    local_non_skill = split_non_skill_changes(local_changed, record.skill_id)
    remote_non_skill = split_non_skill_changes(remote_changed, record.skill_id)
    pending = pending_upload_summary(aiws_root, record_id)
    status = "update_conflict" if local_changed or pending["present"] else "update_allowed"
    review_id = "updrev_" + uuid.uuid4().hex
    review_payload = {
        "review_id": review_id,
        "candidate_id": update_candidate_id,
        "update_candidate_id": update_candidate_id,
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "base_tree_digest": base_digest,
        "current_tree_digest": current_digest,
        "remote_tree_digest": remote_digest,
        "local_changed_files": local_changed,
        "remote_changed_files": remote_changed,
        "local_non_skill_changed_files": local_non_skill,
        "remote_non_skill_changed_files": remote_non_skill,
        "pending_upload": pending,
        "pending_upload_digest": pending_upload_digest(aiws_root, record_id),
        "choices": UPDATE_CONFLICT_CHOICES if status == "update_conflict" else [],
        "created_at": utc_now(),
    }
    review_path = update_review_record_path(aiws_root, review_id)
    require_update_state_path_under(review_path, update_review_root(aiws_root))
    write_json_atomic(review_path, review_payload)
    return {
        "status": status,
        "reason": "modified_draft_or_pending_upload" if status == "update_conflict" else "no_modified_draft_or_pending_upload",
        "review_id": review_id,
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "base_tree_digest": base_digest,
        "current_tree_digest": current_digest,
        "remote_tree_digest": remote_digest,
        "local_changed_files": local_changed,
        "remote_changed_files": remote_changed,
        "local_non_skill_changed_files": local_non_skill,
        "remote_non_skill_changed_files": remote_non_skill,
        "local_vs_base_diff": unified_tree_diff(base_root, draft_path, local_changed, label="local"),
        "remote_vs_base_diff": unified_tree_diff(base_root, remote_root, remote_changed, label="remote"),
        "pending_upload": pending,
        "choices": UPDATE_CONFLICT_CHOICES if status == "update_conflict" else [],
    }


def resolve_update_conflict(
    aiws_root: Path,
    review_id: str,
    choice: str,
    *,
    clear_pending_upload: bool = False,
    allow_full_plugin_discard: bool = False,
) -> dict[str, Any]:
    choice = require_non_blank_string(choice, "choice")
    if choice not in UPDATE_CONFLICT_CHOICES:
        raise SkillManagerError(f"Unsupported update conflict choice: {choice}")
    review = load_update_review(aiws_root, review_id)
    record_id = require_non_blank_string(review.get("draft_id"), "draft_id")
    record = require_canonical_draft_record(aiws_root, record_id)
    candidate = load_update_candidate(aiws_root, require_non_blank_string(review.get("candidate_id"), "candidate_id"))
    if candidate.get("draft_id") != record_id:
        raise SkillManagerError("Update review candidate does not match draft.")
    if candidate.get("plugin_id") != record.plugin_id or candidate.get("skill_id") != record.skill_id:
        raise SkillManagerError("Update review identity does not match draft.")
    draft_path = require_path_under(Path(record.draft_path), aiws_root / "plugins", label="Draft path")
    candidate_root = update_candidate_root(aiws_root)
    base_root = require_update_state_path_under(Path(str(candidate["base_plugin_root"])), candidate_root)
    remote_root = require_update_state_path_under(Path(str(candidate["remote_plugin_root"])), candidate_root)
    require_plugin_contains_skill(remote_root, record.plugin_id, record.skill_id)
    base_digest = tree_digest(base_root)
    current_digest = tree_digest(draft_path)
    remote_digest = tree_digest(remote_root)
    if record.base_tree_digest != review.get("base_tree_digest") or base_digest != review.get("base_tree_digest"):
        return {"status": "stale_review", "reason": "base_digest_changed", "review_id": review_id, "mutated": False}
    if current_digest != review.get("current_tree_digest"):
        return {"status": "stale_review", "reason": "current_draft_digest_changed", "review_id": review_id, "mutated": False}
    if remote_digest != review.get("remote_tree_digest"):
        return {"status": "stale_review", "reason": "remote_candidate_digest_changed", "review_id": review_id, "mutated": False}
    if pending_upload_digest(aiws_root, record_id) != review.get("pending_upload_digest"):
        return {"status": "stale_review", "reason": "pending_upload_state_changed", "review_id": review_id, "mutated": False}
    if choice == "keep_local_draft_and_pending_package":
        return {"status": "update_skipped", "review_id": review_id, "draft_id": record_id, "mutated": False}
    if choice == "submit_or_upload_first":
        return {
            "status": "submit_or_upload_first",
            "review_id": review_id,
            "draft_id": record_id,
            "mutated": False,
            "next_action": "Submit the current draft for review or upload the pending package before updating.",
        }
    pending = pending_upload_records(aiws_root, record_id)
    if pending and not clear_pending_upload:
        return {
            "status": "pending_upload_must_be_cleared",
            "review_id": review_id,
            "draft_id": record_id,
            "pending_upload": pending_upload_summary(aiws_root, record_id),
            "mutated": False,
        }
    local_non_skill = list(review.get("local_non_skill_changed_files") or [])
    if local_non_skill and not allow_full_plugin_discard:
        return {
            "status": "full_plugin_discard_confirmation_required",
            "review_id": review_id,
            "draft_id": record_id,
            "local_non_skill_changed_files": local_non_skill,
            "mutated": False,
        }
    temp_draft_path = draft_path.with_name(f"{draft_path.name}.update-{uuid.uuid4().hex}.tmp")
    require_path_under(temp_draft_path, aiws_root / "plugins", label="Temporary draft update path")
    shutil.copytree(remote_root, temp_draft_path, symlinks=False)
    try:
        validation = require_plugin_contains_skill(temp_draft_path, record.plugin_id, record.skill_id)
        shutil.rmtree(draft_path)
        temp_draft_path.replace(draft_path)
    except Exception:
        if temp_draft_path.exists():
            shutil.rmtree(temp_draft_path)
        raise
    write_base_tree_manifest(aiws_root, record_id, draft_path)
    new_digest = tree_digest(draft_path)
    write_base_tree_snapshot(aiws_root, record_id, draft_path)
    cleared = clear_pending_upload_records(aiws_root, record_id) if clear_pending_upload else 0
    updated = DraftRecord(
        **{
            **record.to_json(),
            "base_version": validation["version"],
            "base_commit": "remote-update-candidate",
            "base_tree_digest": new_digest,
            "current_tree_digest": new_digest,
            "modified": False,
            "last_validation_status": "passed",
            "last_validation_tree_digest": new_digest,
            "updated_at": utc_now(),
        }
    )
    write_json_atomic(draft_record_path(aiws_root, record_id), updated.to_json())
    return {
        "status": "discarded_local_changes_and_updated",
        "review_id": review_id,
        "draft_id": record_id,
        "plugin_id": record.plugin_id,
        "skill_id": record.skill_id,
        "current_tree_digest": new_digest,
        "base_tree_digest": new_digest,
        "modified": False,
        "cleared_pending_uploads": cleared,
        "remote_non_skill_changed_files": review.get("remote_non_skill_changed_files") or [],
        "mutated": True,
    }


def activate_draft(
    aiws_root: Path,
    record_id: str,
    host_kind: str,
    package_output_dir: Path,
    *,
    host_id: str,
    package_upload_dir: Path | None = None,
) -> dict[str, Any]:
    if host_kind != "cowork":
        raise SkillManagerError("Only host_kind='cowork' is supported for draft activation in this slice.")
    host_id = require_host_id(host_id)

    require_canonical_draft_record(aiws_root, record_id)
    try:
        record = refresh_modified_status(aiws_root, record_id)
    except Exception:
        persist_validation_failure(aiws_root, record_id, digest_failed=True)
        raise
    if not record.modified:
        draft_path = require_path_under(Path(record.draft_path), aiws_root / "plugins", label="Draft path")
        try:
            validation = validate_plugin(draft_path, expected_name=record.plugin_id, expected_version=record.base_version)
            skill_names = {skill["name"] for skill in validation["skills"]}
            if record.skill_id not in skill_names:
                raise SkillManagerError(
                    f"Requested skill {record.skill_id!r} does not exist in plugin {record.plugin_id!r}."
                )
            persist_validation_status(aiws_root, record_id, "passed")
        except Exception:
            persist_validation_failure(aiws_root, record_id, digest_failed=False)
            raise
        return {
            "status": "not_modified",
            "record_id": record_id,
            "plugin_id": record.plugin_id,
            "skill_id": record.skill_id,
            "modified": False,
            "status_label": "Current",
            "actions": [],
        }

    record = require_canonical_draft_record(aiws_root, record_id)
    package = build_draft_package(aiws_root, record_id, package_output_dir)
    handoff = None
    if package_upload_dir is not None:
        handoff = copy_package_to_upload_surface(Path(package["package_path"]), package_upload_dir)
    activation_record = write_draft_activation_record(
        aiws_root,
        record_id=record_id,
        host_kind=host_kind,
        host_id=host_id,
        record=record,
        package=package,
        handoff=handoff,
    )
    if handoff:
        return {
            **package,
            **handoff,
            "status": "handoff_prepared",
            "activation_status": "pending_upload",
            "host_id": host_id,
            "activation_effective": False,
            "requires_manual_upload": False,
            "requires_cowork_confirmation": True,
            "activation_record_path": activation_record["activation_record_path"],
            "actions": [
                {
                    "type": "cowork_package_handoff",
                    "terminal": False,
                    "host_kind": "cowork",
                    "package_path": package["package_path"],
                    "copied_package_path": handoff["copied_package_path"],
                    "label": "Confirm draft package in Cowork",
                },
            ],
        }
    return {
        **package,
        "status": "host_capability_missing",
        "activation_status": "pending_upload",
        "host_id": host_id,
        "activation_effective": False,
        "requires_manual_upload": True,
        "activation_record_path": activation_record["activation_record_path"],
        "actions": [
            {
                "type": "package_upload",
                "terminal": False,
                "host_kind": "cowork",
                "package_path": package["package_path"],
                "label": "Upload draft package to Cowork",
            }
        ],
    }


def stage_proposal(
    aiws_root: Path,
    record_id: str,
    target_scope: str,
    target_repo: str | None,
    summary: str,
    rationale: str,
    *,
    backend_kind: str = "github",
    backend_ref: str | None = None,
    marketplace_id: str | None = None,
) -> dict[str, Any]:
    record_id = require_non_blank_string(record_id, "record_id")
    summary = require_non_blank_string(summary, "summary")
    rationale = require_non_blank_string(rationale, "rationale")
    target = normalize_proposal_target(
        aiws_root,
        target_scope=target_scope,
        target_repo=target_repo,
        backend_kind=backend_kind,
        backend_ref=backend_ref,
        marketplace_id=marketplace_id,
    )
    target_scope = target["scope_id"]

    record = safely_identify_draft_record(aiws_root, record_id)
    canonical_record_id = draft_id(record.plugin_id, record.skill_id, record.origin_repo)
    if canonical_record_id != record_id:
        raise SkillManagerError(f"Draft record id does not match canonical draft id {canonical_record_id}.")

    plugins_root = aiws_root / "plugins"
    draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
    expected_draft_path = require_path_under(
        draft_worktree_path(aiws_root, record.origin_marketplace, record.plugin_id, record.origin_repo),
        plugins_root,
        label="Expected draft path",
    )
    if draft_path != expected_draft_path:
        persist_validation_failure(aiws_root, record_id, digest_failed=True)
        raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")

    try:
        current_tree_digest = tree_digest(draft_path)
    except Exception:
        persist_validation_failure(aiws_root, record_id, digest_failed=True)
        raise

    modified = record.base_tree_digest is not None and current_tree_digest != record.base_tree_digest
    if record.base_tree_digest is None:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=True,
        )
        raise SkillManagerError(f"Draft record {record_id} has no base_tree_digest; cannot stage proposal.")
    if not modified:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=False,
        )
        raise SkillManagerError(f"Draft record {record_id} does not differ from its base tree.")

    try:
        require_changes_only_under_skill(aiws_root, record_id, draft_path, record.skill_id)
    except Exception:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=modified,
        )
        raise

    try:
        validation = validate_plugin(draft_path, expected_name=record.plugin_id, expected_version=record.base_version)
        skill_names = {skill["name"] for skill in validation["skills"]}
        if record.skill_id not in skill_names:
            raise SkillManagerError(f"Requested skill {record.skill_id!r} does not exist in plugin {record.plugin_id!r}.")
    except Exception:
        persist_stage_validation_result(
            aiws_root,
            record_id,
            status="failed",
            current_tree_digest=current_tree_digest,
            modified=modified,
        )
        raise

    record = persist_stage_validation_result(
        aiws_root,
        record_id,
        status="passed",
        current_tree_digest=current_tree_digest,
        modified=True,
    )

    proposal_root = aiws_root / "state" / "skill-proposals"
    created_at = utc_now()
    for _attempt in range(10):
        proposal_id = f"skillprop_{uuid.uuid4().hex}"
        proposal_path = proposal_record_path(aiws_root, proposal_id)
        proposal = {
            "proposal_id": proposal_id,
            "draft_id": record_id,
            "plugin_id": record.plugin_id,
            "skill_id": record.skill_id,
            "origin_marketplace": record.origin_marketplace,
            "origin_repo": record.origin_repo,
            "origin_ref": record.origin_ref,
            "base_version": record.base_version,
            "base_commit": record.base_commit,
            "draft_path": record.draft_path,
            "base_tree_digest": record.base_tree_digest,
            "current_tree_digest": current_tree_digest,
            "validation_status": "passed",
            "validation_tree_digest": current_tree_digest,
            "target_scope": target_scope,
            "scope_id": target["scope_id"],
            "backend_kind": target["backend_kind"],
            "backend_ref": target["backend_ref"],
            "target_repo": target["target_repo"],
            "marketplace_id": target["marketplace_id"],
            "summary": summary,
            "rationale": rationale,
            "active": record.active,
            "modified": record.modified,
            "status": "staged",
            "branch_name": None,
            "pr_url": None,
            "created_at": created_at,
            "updated_at": created_at,
        }
        if write_json_exclusive_via_temp(proposal_path, proposal):
            return {
                "status": "staged",
                "proposal_id": proposal_id,
                "proposal_path": str(proposal_path),
                "draft_id": record_id,
                "plugin_id": record.plugin_id,
                "skill_id": record.skill_id,
                "target_scope": target_scope,
                "target_repo": target["target_repo"],
                "backend_kind": target["backend_kind"],
                "backend_ref": target["backend_ref"],
                "marketplace_id": target["marketplace_id"],
                "next_action": "submit_for_review",
            }

    raise SkillManagerError(f"Could not allocate a unique proposal record under {proposal_root}.")


def proposal_branch_name(proposal_id: str) -> str:
    return f"aiws/skill-proposals/{proposal_id}"


def normalize_review_roles(required_review_roles: list[str] | tuple[str, ...] | None) -> list[str]:
    if required_review_roles is None:
        return []
    return [require_non_blank_string(role, "required_review_roles") for role in required_review_roles]


def call_proposal_submitter(submitter: Any, payload: dict[str, Any]) -> dict[str, Any]:
    if hasattr(submitter, "submit"):
        result = submitter.submit(payload)
    elif callable(submitter):
        result = submitter(payload)
    else:
        raise SkillManagerError("submitter must be callable or expose submit(payload).")
    if not isinstance(result, dict):
        raise SkillManagerError("submitter returned invalid review metadata.")
    return result


def post_merge_delivery_guidance(target_repo: str) -> dict[str, Any]:
    target_repo = require_non_blank_string(target_repo, "target_repo")
    return {
        "status": "marketplace_update_required_after_merge",
        "regular_user_next_step": "Wait for maintainer review, merge, and Cowork marketplace update/sync.",
        "normal_user_manual_zip_upload_required": False,
        "local_activation": "technical_pilot_fallback_only",
        "delivery_paths": [
            {
                "marketplace_type": "github_synced",
                "maintainer_action": (
                    f"Merge the proposal in {target_repo}, then trigger Cowork marketplace update/sync "
                    "or rely on automatic sync if enabled."
                ),
            },
            {
                "marketplace_type": "manual",
                "maintainer_action": (
                    "Upload a new plugin ZIP with the same plugin name so Cowork overwrites the existing plugin."
                ),
            },
        ],
    }


def repository_review_policy_from_codeowners(codeowners_status: Any) -> dict[str, Any]:
    value = str(codeowners_status or "unknown")
    if value == "detected":
        status = "present"
        caveat = "CODEOWNERS detected; GitHub repository policy owns reviewer assignment and approval."
    elif value == "not_detected":
        status = "absent"
        caveat = "CODEOWNERS not detected; repository maintainers still own review and merge."
    else:
        value = "unknown"
        status = "unknown"
        caveat = "Repository review policy could not be determined from the submitter."
    return {
        "status": status,
        "codeowners": value,
        "review_assignment_owner": "repository_policy",
        "normal_user_selects_reviewers": False,
        "caveat": caveat,
    }


def submitted_review_response(proposal: dict[str, Any]) -> dict[str, Any]:
    backend_kind = require_backend_kind(proposal.get("backend_kind", "github"))
    if backend_kind == "google_drive":
        proposal_folder_id = require_non_blank_string(proposal.get("proposal_folder_id"), "proposal_folder_id")
        proposal_folder_url = require_non_blank_string(proposal.get("proposal_folder_url"), "proposal_folder_url")
        marketplace_id = require_marketplace_id(proposal.get("marketplace_id"))
        return {
            "status": "submitted_for_review",
            "status_label": "Submitted for review",
            "proposal_id": proposal["proposal_id"],
            "draft_id": proposal["draft_id"],
            "plugin_id": proposal["plugin_id"],
            "skill_id": proposal["skill_id"],
            "target_scope": proposal["target_scope"],
            "backend_kind": "google_drive",
            "backend_ref": require_non_blank_string(proposal.get("backend_ref"), "backend_ref"),
            "marketplace_id": marketplace_id,
            "proposal_folder_id": proposal_folder_id,
            "proposal_folder_url": proposal_folder_url,
            "backend_review_state": require_non_blank_string(
                proposal.get("backend_review_state") or "in_review",
                "backend_review_state",
            ),
        }

    branch_name = require_non_blank_string(proposal.get("branch_name"), "branch_name")
    pr_url = require_non_blank_string(proposal.get("pr_url"), "pr_url")
    target_repo = require_non_blank_string(proposal.get("target_repo"), "target_repo")
    repository_review_policy = proposal.get("repository_review_policy")
    if not isinstance(repository_review_policy, dict):
        repository_review_policy = repository_review_policy_from_codeowners("unknown")
    return {
        "status": "submitted_for_review",
        "status_label": "Submitted for review",
        "proposal_id": proposal["proposal_id"],
        "draft_id": proposal["draft_id"],
        "plugin_id": proposal["plugin_id"],
        "skill_id": proposal["skill_id"],
        "target_scope": proposal["target_scope"],
        "target_repo": target_repo,
        "branch_name": branch_name,
        "pr_url": pr_url,
        "repository_review_policy": repository_review_policy,
        "post_merge_delivery": post_merge_delivery_guidance(target_repo),
    }


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
DEFAULT_COMMAND_TIMEOUT_SECONDS = 120


def default_command_runner(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["GH_PROMPT_DISABLED"] = "1"
    stdin = subprocess.DEVNULL if input_text is None else None
    return subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        stdin=stdin,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=DEFAULT_COMMAND_TIMEOUT_SECONDS,
    )


def require_command_success(result: subprocess.CompletedProcess[str], *, action: str) -> subprocess.CompletedProcess[str]:
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if detail:
            raise SkillManagerError(f"{action} failed: {detail}")
        raise SkillManagerError(f"{action} failed with exit code {result.returncode}.")
    return result


def require_target_repo(value: Any) -> str:
    target_repo = require_non_blank_string(value, "target_repo")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", target_repo):
        raise SkillManagerError("target_repo must use owner/repo format.")
    return target_repo


def normalize_proposal_target(
    aiws_root: Path,
    *,
    target_scope: str,
    target_repo: Any,
    backend_kind: Any,
    backend_ref: Any,
    marketplace_id: Any,
) -> dict[str, Any]:
    scope_id = require_non_blank_string(target_scope, "target_scope")
    normalized_backend_kind = require_backend_kind(backend_kind)
    if normalized_backend_kind == "github":
        resolved_target_repo = require_non_blank_string(target_repo, "target_repo")
        return {
            "scope_id": scope_id,
            "backend_kind": "github",
            "backend_ref": resolved_target_repo,
            "target_repo": resolved_target_repo,
            "marketplace_id": None,
        }

    resolved_backend_ref = require_non_blank_string(backend_ref, "backend_ref")
    resolved_marketplace_id = require_marketplace_id(marketplace_id)
    ensure_marketplace_registration(
        aiws_root,
        marketplace_id=resolved_marketplace_id,
        scope_id=scope_id,
        backend_kind=normalized_backend_kind,
        backend_ref=resolved_backend_ref,
    )
    return {
        "scope_id": scope_id,
        "backend_kind": normalized_backend_kind,
        "backend_ref": resolved_backend_ref,
        "target_repo": None,
        "marketplace_id": resolved_marketplace_id,
    }


def git_worktree_root(aiws_root: Path, target_repo: str, proposal_id: str) -> Path:
    owner, repo = target_repo.split("/", 1)
    return aiws_root / "state" / "git-worktrees" / f"{owner}__{repo}" / proposal_id


def require_aiws_owned_scratch_path(path: Path, aiws_root: Path, *, label: str) -> Path:
    scratch_root = aiws_root / "state" / "git-worktrees"
    reject_existing_symlink_components(path.parent, label=f"{label} parent")
    if path.exists() and path.is_symlink():
        raise SkillManagerError(f"{label} must not be a symlink: {path}")
    try:
        path.absolute().relative_to(scratch_root.absolute())
    except ValueError as exc:
        raise SkillManagerError(f"{label} is outside AIWS git scratch root: {path}") from exc
    return path


def find_target_plugin_root(repo_dir: Path, plugin_id: str) -> Path:
    candidates = [repo_dir, repo_dir / plugin_id]
    for candidate in candidates:
        manifest_path = plugin_manifest_path(candidate)
        if not manifest_path.is_file() or manifest_path.is_symlink():
            continue
        try:
            manifest = load_json(manifest_path)
        except SkillManagerError:
            continue
        if isinstance(manifest, dict) and manifest.get("name") == plugin_id:
            return candidate
    raise SkillManagerError(f"Target repository does not contain plugin {plugin_id!r} at root or {plugin_id}/.")


def copy_skill_folder(source_skill_root: Path, target_skill_root: Path) -> None:
    if not source_skill_root.is_dir():
        raise SkillManagerError(f"Source skill folder is missing: {source_skill_root}")
    if not target_skill_root.is_dir():
        raise SkillManagerError(f"Target skill folder is missing: {target_skill_root}")
    reject_existing_symlink_components(target_skill_root.parent, label="Target skill folder parent")
    if target_skill_root.is_symlink():
        raise SkillManagerError(f"Target skill folder must not be a symlink: {target_skill_root}")
    for path in source_skill_root.rglob("*"):
        if path.is_symlink():
            raise SkillManagerError(f"Source skill folder must not contain symlinks: {path}")
    for path in target_skill_root.rglob("*"):
        if path.is_symlink():
            raise SkillManagerError(f"Target skill folder must not contain symlinks: {path}")
    shutil.rmtree(target_skill_root)
    shutil.copytree(source_skill_root, target_skill_root)


def detect_codeowners(repo_dir: Path) -> str:
    candidates = [
        repo_dir / "CODEOWNERS",
        repo_dir / ".github" / "CODEOWNERS",
        repo_dir / "docs" / "CODEOWNERS",
    ]
    return "detected" if any(path.is_file() for path in candidates) else "not_detected"


def detect_codeowners_in_tree(tree_items: list[Any]) -> str:
    candidates = {"CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"}
    return (
        "detected"
        if any(isinstance(item, dict) and item.get("type") == "blob" and item.get("path") in candidates for item in tree_items)
        else "not_detected"
    )


def pr_body_text(payload: dict[str, Any], *, codeowners_status: str) -> str:
    lines = [
        f"AIWS proposal: {payload['proposal_id']}",
        "",
        f"Plugin: {payload['plugin_id']}",
        f"Skill: {payload['skill_id']}",
        f"Target scope: {payload['target_scope']}",
        f"Target repo: {payload['target_repo']}",
        f"Validation digest: {payload['validation_tree_digest']}",
        f"CODEOWNERS: {codeowners_status}",
        "",
        "Summary:",
        str(payload.get("summary", "")).strip(),
        "",
        "Rationale:",
        str(payload.get("rationale", "")).strip(),
        "",
        "Review and merge are managed by the target repository's maintainers and policies.",
        "",
        "Post-merge Cowork delivery:",
        "- GitHub-synced marketplace: trigger Cowork marketplace update/sync, or rely on automatic sync if enabled.",
        "- Manual marketplace: upload a new plugin ZIP with the same plugin name so Cowork overwrites the existing plugin.",
        "- Regular users should not manually upload ZIP files for the normal path.",
    ]
    return "\n".join(lines) + "\n"


def write_pr_body(path: Path, payload: dict[str, Any], *, codeowners_status: str) -> None:
    path.write_text(pr_body_text(payload, codeowners_status=codeowners_status), encoding="utf-8")


def update_existing_pr_metadata(
    runner: "GhCliProposalSubmitter",
    *,
    target_repo: str,
    pr_url: str,
    is_draft: bool,
    body_path: Path,
) -> None:
    runner.run(
        [
            "gh",
            "pr",
            "edit",
            pr_url,
            "--repo",
            target_repo,
            "--body-file",
            str(body_path),
        ],
        action="Update existing proposal pull request body",
    )
    if is_draft:
        runner.run(
            [
                "gh",
                "pr",
                "ready",
                pr_url,
                "--repo",
                target_repo,
            ],
            action="Mark existing proposal pull request ready for review",
        )


class GhCliProposalSubmitter:
    def __init__(self, *, aiws_root: Path, runner: CommandRunner | None = None) -> None:
        self.aiws_root = aiws_root
        self.runner = runner or default_command_runner

    def run(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
        action: str,
    ) -> subprocess.CompletedProcess[str]:
        return require_command_success(self.runner(args, cwd=cwd, input_text=input_text), action=action)

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_id = require_non_blank_string(payload.get("proposal_id"), "proposal_id")
        plugin_id = require_non_blank_string(payload.get("plugin_id"), "plugin_id")
        skill_id = require_non_blank_string(payload.get("skill_id"), "skill_id")
        branch_name = require_non_blank_string(payload.get("branch_name"), "branch_name")
        target_repo = require_target_repo(payload.get("target_repo"))
        draft_path = Path(require_non_blank_string(payload.get("draft_path"), "draft_path"))
        validation_tree_digest = require_non_blank_string(
            payload.get("validation_tree_digest"), "validation_tree_digest"
        )

        repo_api = self.run(["gh", "api", f"repos/{target_repo}"], action="Check GitHub repository access")
        try:
            repo_meta = json.loads(repo_api.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise SkillManagerError("GitHub repository metadata was not valid JSON.") from exc
        default_branch = require_non_blank_string(repo_meta.get("default_branch"), "default_branch")
        permissions = repo_meta.get("permissions")
        if isinstance(permissions, dict) and permissions.get("push") is False:
            raise SkillManagerError(f"Authenticated GitHub user does not have push permission for {target_repo}.")

        worktree_root = require_aiws_owned_scratch_path(
            git_worktree_root(self.aiws_root, target_repo, proposal_id),
            self.aiws_root,
            label="Git scratch path",
        )
        if worktree_root.exists():
            shutil.rmtree(worktree_root)
        worktree_root.mkdir(parents=True, exist_ok=True)
        repo_dir = worktree_root / "repo"

        self.run(["gh", "repo", "clone", target_repo, str(repo_dir)], action="Clone target repository")
        plugin_root = find_target_plugin_root(repo_dir, plugin_id)
        target_skill_root = plugin_root / "skills" / skill_id
        source_skill_root = draft_path / "skills" / skill_id
        copy_skill_folder(source_skill_root, target_skill_root)

        self.run(["git", "checkout", "-B", branch_name], cwd=repo_dir, action="Create proposal branch")
        status = self.run(["git", "status", "--porcelain"], cwd=repo_dir, action="Check proposal diff")
        if not status.stdout.strip():
            return {
                "status": "no_changes_to_submit",
                "branch_name": branch_name,
                "validation_tree_digest": validation_tree_digest,
            }

        relative_skill_path = target_skill_root.relative_to(repo_dir).as_posix()
        self.run(["git", "add", relative_skill_path], cwd=repo_dir, action="Stage proposal skill changes")
        self.run(
            ["git", "commit", "-m", f"AIWS proposal {proposal_id}: update {plugin_id}/{skill_id}"],
            cwd=repo_dir,
            action="Commit proposal changes",
        )
        self.run(
            ["git", "push", "--force-with-lease", "origin", f"{branch_name}:{branch_name}"],
            cwd=repo_dir,
            action="Push proposal branch",
        )

        existing = self.run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                target_repo,
                "--head",
                branch_name,
                "--state",
                "open",
                "--json",
                "url,isDraft",
            ],
            action="Check existing proposal pull request",
        )
        try:
            existing_prs = json.loads(existing.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise SkillManagerError("GitHub PR list output was not valid JSON.") from exc
        body_path = worktree_root / "pull-request-body.md"
        codeowners_status = detect_codeowners(repo_dir)
        repository_review_policy = repository_review_policy_from_codeowners(codeowners_status)
        write_pr_body(body_path, payload, codeowners_status=codeowners_status)
        if isinstance(existing_prs, list) and existing_prs and isinstance(existing_prs[0], dict):
            pr_url = require_non_blank_string(existing_prs[0].get("url"), "pr_url")
            update_existing_pr_metadata(
                self,
                target_repo=target_repo,
                pr_url=pr_url,
                is_draft=bool(existing_prs[0].get("isDraft")),
                body_path=body_path,
            )
            return {
                "status": "submitted_for_review",
                "branch_name": branch_name,
                "pr_url": pr_url,
                "repository_review_policy": repository_review_policy,
            }

        pr_create = self.run(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                target_repo,
                "--base",
                default_branch,
                "--head",
                branch_name,
                "--title",
                str(payload.get("summary", "")).strip() or f"AIWS proposal {proposal_id}",
                "--body-file",
                str(body_path),
            ],
            action="Create proposal pull request",
        )
        pr_url = require_non_blank_string(pr_create.stdout.strip(), "pr_url")
        return {
            "status": "submitted_for_review",
            "branch_name": branch_name,
            "pr_url": pr_url,
            "repository_review_policy": repository_review_policy,
        }


def github_api_token_from_env(env: dict[str, str] | None = None) -> str | None:
    values = env or os.environ
    for name in ("AIWS_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        token = values.get(name)
        if token and token.strip():
            return token.strip()
    return None


class GitHubApiClient:
    def __init__(self, *, token: str, api_url: str | None = None) -> None:
        self.token = require_non_blank_string(token, "token")
        self.api_url = (api_url or os.environ.get("GITHUB_API_URL") or "https://api.github.com").rstrip("/")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        suffix = path if path.startswith("/") else f"/{path}"
        if query:
            suffix = f"{suffix}?{urlencode(query)}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.api_url}{suffix}",
            data=body,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "aiws-mcp",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urlopen(request, timeout=DEFAULT_COMMAND_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise SkillManagerError(f"GitHub API request failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise SkillManagerError(f"GitHub API request failed: {exc.reason}") from exc
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SkillManagerError("GitHub API response was not valid JSON.") from exc


def require_github_object(value: Any, *, action: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SkillManagerError(f"{action} returned invalid GitHub metadata.")
    return value


def require_github_list(value: Any, *, action: str) -> list[Any]:
    if not isinstance(value, list):
        raise SkillManagerError(f"{action} returned invalid GitHub metadata.")
    return value


def github_ref_path(branch_name: str) -> str:
    return f"/git/refs/heads/{quote(branch_name, safe='/')}"


def list_source_skill_files(source_skill_root: Path) -> list[tuple[str, bytes]]:
    if not source_skill_root.is_dir():
        raise SkillManagerError(f"Source skill folder is missing: {source_skill_root}")
    files: list[tuple[str, bytes]] = []
    for path in sorted(source_skill_root.rglob("*")):
        if path.is_symlink():
            raise SkillManagerError(f"Source skill folder must not contain symlinks: {path}")
        if path.is_file():
            relative = path.relative_to(source_skill_root).as_posix()
            files.append((relative, path.read_bytes()))
    if not files:
        raise SkillManagerError(f"Source skill folder has no files: {source_skill_root}")
    return files


class GitHubApiProposalSubmitter:
    def __init__(
        self,
        *,
        aiws_root: Path,
        token: str | None = None,
        api_client: Any | None = None,
    ) -> None:
        self.aiws_root = aiws_root
        resolved_token = token or github_api_token_from_env()
        if api_client is None and not resolved_token:
            raise SkillManagerError(
                "GitHub API submitter requires AIWS_GITHUB_TOKEN, GITHUB_TOKEN, or GH_TOKEN in the host environment."
            )
        self.client = api_client or GitHubApiClient(token=resolved_token or "")

    def request_json(
        self,
        method: str,
        target_repo: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | list[Any] | None:
        return self.client.request_json(
            method,
            f"/repos/{target_repo}{path}",
            payload=payload,
            query=query,
            allow_404=allow_404,
        )

    def read_blob_json(self, target_repo: str, blob_sha: str) -> dict[str, Any]:
        blob = require_github_object(
            self.request_json("GET", target_repo, f"/git/blobs/{quote(blob_sha, safe='')}"),
            action="Read GitHub blob",
        )
        if blob.get("encoding") != "base64":
            raise SkillManagerError("GitHub blob encoding was not base64.")
        try:
            raw = base64.b64decode(require_non_blank_string(blob.get("content"), "content"))
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SkillManagerError("GitHub blob did not contain valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise SkillManagerError("GitHub blob did not contain a JSON object.")
        return parsed

    def find_plugin_prefix(self, target_repo: str, tree_items: list[Any], plugin_id: str) -> str:
        manifest_paths = [".claude-plugin/plugin.json", f"{plugin_id}/.claude-plugin/plugin.json"]
        blobs = {
            str(item.get("path")): item
            for item in tree_items
            if isinstance(item, dict) and item.get("type") == "blob" and item.get("path") in manifest_paths
        }
        for manifest_path in manifest_paths:
            item = blobs.get(manifest_path)
            if not item:
                continue
            manifest = self.read_blob_json(target_repo, require_non_blank_string(item.get("sha"), "sha"))
            if manifest.get("name") == plugin_id:
                return "" if manifest_path.startswith(".claude-plugin/") else plugin_id
        raise SkillManagerError(f"Target repository does not contain plugin {plugin_id!r} at root or {plugin_id}/.")

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_id = require_non_blank_string(payload.get("proposal_id"), "proposal_id")
        plugin_id = require_non_blank_string(payload.get("plugin_id"), "plugin_id")
        skill_id = require_non_blank_string(payload.get("skill_id"), "skill_id")
        branch_name = require_non_blank_string(payload.get("branch_name"), "branch_name")
        target_repo = require_target_repo(payload.get("target_repo"))
        owner, _repo = target_repo.split("/", 1)
        draft_path = Path(require_non_blank_string(payload.get("draft_path"), "draft_path"))
        validation_tree_digest = require_non_blank_string(
            payload.get("validation_tree_digest"), "validation_tree_digest"
        )

        repo_meta = require_github_object(
            self.request_json("GET", target_repo, ""),
            action="Check GitHub repository access",
        )
        default_branch = require_non_blank_string(repo_meta.get("default_branch"), "default_branch")
        permissions = repo_meta.get("permissions")
        if isinstance(permissions, dict) and permissions.get("push") is False:
            raise SkillManagerError(f"Authenticated GitHub user does not have push permission for {target_repo}.")

        base_ref = require_github_object(
            self.request_json("GET", target_repo, github_ref_path(default_branch)),
            action="Read default branch ref",
        )
        base_commit_sha = require_non_blank_string(
            require_github_object(base_ref.get("object"), action="Read default branch ref").get("sha"),
            "sha",
        )
        base_commit = require_github_object(
            self.request_json("GET", target_repo, f"/git/commits/{quote(base_commit_sha, safe='')}"),
            action="Read default branch commit",
        )
        base_tree_sha = require_non_blank_string(
            require_github_object(base_commit.get("tree"), action="Read default branch commit").get("sha"),
            "tree.sha",
        )
        recursive_tree = require_github_object(
            self.request_json("GET", target_repo, f"/git/trees/{quote(base_tree_sha, safe='')}", query={"recursive": "1"}),
            action="Read repository tree",
        )
        tree_items = require_github_list(recursive_tree.get("tree"), action="Read repository tree")
        plugin_prefix = self.find_plugin_prefix(target_repo, tree_items, plugin_id)
        skill_prefix = f"{plugin_prefix + '/' if plugin_prefix else ''}skills/{skill_id}"
        existing_skill_paths = [
            str(item.get("path"))
            for item in tree_items
            if isinstance(item, dict)
            and item.get("type") == "blob"
            and item.get("path")
            and str(item.get("path")).startswith(f"{skill_prefix}/")
        ]
        if any(
            isinstance(item, dict)
            and item.get("mode") == "120000"
            and item.get("path")
            and str(item.get("path")).startswith(f"{skill_prefix}/")
            for item in tree_items
        ):
            raise SkillManagerError(f"Target skill folder must not contain symlinks: {skill_prefix}")
        if not existing_skill_paths:
            raise SkillManagerError(f"Target skill folder is missing: {skill_prefix}")

        tree_entries: list[dict[str, Any]] = [
            {"path": path, "mode": "100644", "type": "blob", "sha": None}
            for path in existing_skill_paths
        ]
        source_skill_root = draft_path / "skills" / skill_id
        for relative, content in list_source_skill_files(source_skill_root):
            blob = require_github_object(
                self.request_json(
                    "POST",
                    target_repo,
                    "/git/blobs",
                    payload={
                        "content": base64.b64encode(content).decode("ascii"),
                        "encoding": "base64",
                    },
                ),
                action="Create GitHub blob",
            )
            tree_entries.append(
                {
                    "path": f"{skill_prefix}/{relative}",
                    "mode": "100644",
                    "type": "blob",
                    "sha": require_non_blank_string(blob.get("sha"), "sha"),
                }
            )

        created_tree = require_github_object(
            self.request_json(
                "POST",
                target_repo,
                "/git/trees",
                payload={"base_tree": base_tree_sha, "tree": tree_entries},
            ),
            action="Create GitHub tree",
        )
        new_tree_sha = require_non_blank_string(created_tree.get("sha"), "sha")
        if new_tree_sha == base_tree_sha:
            return {
                "status": "no_changes_to_submit",
                "branch_name": branch_name,
                "validation_tree_digest": validation_tree_digest,
            }

        commit = require_github_object(
            self.request_json(
                "POST",
                target_repo,
                "/git/commits",
                payload={
                    "message": f"AIWS proposal {proposal_id}: update {plugin_id}/{skill_id}",
                    "tree": new_tree_sha,
                    "parents": [base_commit_sha],
                },
            ),
            action="Create GitHub commit",
        )
        commit_sha = require_non_blank_string(commit.get("sha"), "sha")

        branch_ref_path = github_ref_path(branch_name)
        existing_branch = self.request_json("GET", target_repo, branch_ref_path, allow_404=True)
        if existing_branch is None:
            self.request_json(
                "POST",
                target_repo,
                "/git/refs",
                payload={"ref": f"refs/heads/{branch_name}", "sha": commit_sha},
            )
        else:
            self.request_json(
                "PATCH",
                target_repo,
                branch_ref_path,
                payload={"sha": commit_sha, "force": True},
            )

        codeowners_status = detect_codeowners_in_tree(tree_items)
        repository_review_policy = repository_review_policy_from_codeowners(codeowners_status)
        body = pr_body_text(payload, codeowners_status=codeowners_status)
        existing_prs = require_github_list(
            self.request_json(
                "GET",
                target_repo,
                "/pulls",
                query={"head": f"{owner}:{branch_name}", "state": "open"},
            ),
            action="Check existing proposal pull request",
        )
        if existing_prs and isinstance(existing_prs[0], dict):
            pr_url = require_non_blank_string(existing_prs[0].get("html_url") or existing_prs[0].get("url"), "pr_url")
            number = existing_prs[0].get("number")
            if isinstance(number, int):
                self.request_json("PATCH", target_repo, f"/pulls/{number}", payload={"body": body})
            return {
                "status": "submitted_for_review",
                "branch_name": branch_name,
                "pr_url": pr_url,
                "repository_review_policy": repository_review_policy,
            }

        created_pr = require_github_object(
            self.request_json(
                "POST",
                target_repo,
                "/pulls",
                payload={
                    "title": str(payload.get("summary", "")).strip() or f"AIWS proposal {proposal_id}",
                    "head": branch_name,
                    "base": default_branch,
                    "body": body,
                    "draft": False,
                },
            ),
            action="Create GitHub pull request",
        )
        pr_url = require_non_blank_string(created_pr.get("html_url") or created_pr.get("url"), "pr_url")
        return {
            "status": "submitted_for_review",
            "branch_name": branch_name,
            "pr_url": pr_url,
            "repository_review_policy": repository_review_policy,
        }


class GithubHandoffProposalSubmitter:
    def __init__(self, *, aiws_root: Path) -> None:
        self.aiws_root = aiws_root

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_id = require_non_blank_string(payload.get("proposal_id"), "proposal_id")
        draft_id_value = require_non_blank_string(payload.get("draft_id"), "draft_id")
        target_repo = require_non_blank_string(payload.get("target_repo"), "target_repo")
        branch_name = require_non_blank_string(payload.get("branch_name"), "branch_name")
        raw_review_roles = payload.get("required_review_roles")
        required_review_roles = normalize_review_roles(
            raw_review_roles if isinstance(raw_review_roles, (list, tuple)) else None
        )
        action = {
            "type": "github_submit_handoff",
            "label": "Submit through a Cowork-compatible GitHub adapter, bot, or maintainer handoff",
            "reason_code": "github_cli_unavailable",
            "target_repo": target_repo,
            "branch_name": branch_name,
            "terminal": False,
        }
        response = {
            "status": "submit_handoff_required",
            "status_label": "GitHub submit handoff required",
            "reason_code": "github_cli_unavailable",
            "proposal_id": proposal_id,
            "draft_id": draft_id_value,
            "target_repo": target_repo,
            "branch_name": branch_name,
            "terminal": False,
            "no_pr_created": True,
            "actions": [action],
        }
        if required_review_roles:
            response["required_review_roles"] = required_review_roles
            action["required_review_roles"] = required_review_roles

        return response


def google_drive_api_token_from_env(env: dict[str, str] | None = None) -> str | None:
    values = env or os.environ
    for name in ("AIWS_GOOGLE_DRIVE_TOKEN", "GOOGLE_DRIVE_TOKEN", "GOOGLE_OAUTH_ACCESS_TOKEN"):
        token = values.get(name)
        if token and token.strip():
            return token.strip()
    return None


def drive_query_literal(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


class GoogleDriveApiClient:
    def __init__(
        self,
        *,
        token: str,
        api_url: str | None = None,
        upload_url: str | None = None,
    ) -> None:
        self.token = require_non_blank_string(token, "token")
        self.api_url = (
            api_url or os.environ.get("GOOGLE_DRIVE_API_URL") or "https://www.googleapis.com/drive/v3"
        ).rstrip("/")
        self.upload_url = (
            upload_url or os.environ.get("GOOGLE_DRIVE_UPLOAD_URL") or "https://www.googleapis.com/upload/drive/v3"
        ).rstrip("/")

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        allow_404: bool = False,
        upload: bool = False,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any] | list[Any] | None:
        suffix = path if path.startswith("/") else f"/{path}"
        if query:
            suffix = f"{suffix}?{urlencode(query)}"
        base_url = self.upload_url if upload else self.api_url
        request_body = body
        request_headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "aiws-mcp",
        }
        if payload is not None:
            request_body = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if headers:
            request_headers.update(headers)
        request = Request(
            f"{base_url}{suffix}",
            data=request_body,
            method=method,
            headers=request_headers,
        )
        try:
            with urlopen(request, timeout=DEFAULT_COMMAND_TIMEOUT_SECONDS) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if allow_404 and exc.code == 404:
                return None
            detail = exc.read().decode("utf-8", errors="replace").strip()
            raise SkillManagerError(f"Google Drive API request failed ({exc.code}): {detail}") from exc
        except URLError as exc:
            raise SkillManagerError(f"Google Drive API request failed: {exc.reason}") from exc
        if not raw.strip():
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SkillManagerError("Google Drive API response was not valid JSON.") from exc

    def find_child(self, parent_id: str, name: str, *, mime_type: str | None = None) -> dict[str, Any] | None:
        query_parts = [
            f"{drive_query_literal(parent_id)} in parents",
            f"name = {drive_query_literal(name)}",
            "trashed = false",
        ]
        if mime_type is not None:
            query_parts.append(f"mimeType = {drive_query_literal(mime_type)}")
        response = self.request_json(
            "GET",
            "/files",
            query={
                "q": " and ".join(query_parts),
                "fields": "files(id,name,mimeType,webViewLink,parents)",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        if not isinstance(response, dict):
            raise SkillManagerError("Google Drive file query returned invalid metadata.")
        files = response.get("files")
        if not isinstance(files, list):
            raise SkillManagerError("Google Drive file query returned invalid metadata.")
        if not files:
            return None
        if len(files) > 1:
            raise SkillManagerError(f"Google Drive contains duplicate children named {name!r} under {parent_id}.")
        if not isinstance(files[0], dict):
            raise SkillManagerError("Google Drive file query returned invalid metadata.")
        return files[0]

    def get_file(self, file_id: str) -> dict[str, Any]:
        metadata = self.request_json(
            "GET",
            f"/files/{quote(require_non_blank_string(file_id, 'file_id'), safe='')}",
            query={
                "fields": "id,name,mimeType,webViewLink,parents,md5Checksum,modifiedTime",
                "supportsAllDrives": "true",
            },
        )
        if not isinstance(metadata, dict):
            raise SkillManagerError("Google Drive file lookup returned invalid metadata.")
        return metadata

    def move_file(self, file_id: str, new_parent_id: str) -> dict[str, Any]:
        metadata = self.get_file(file_id)
        parents = metadata.get("parents")
        remove_parents = ""
        if isinstance(parents, list):
            remove_parents = ",".join(str(parent) for parent in parents if str(parent).strip())
        moved = self.request_json(
            "PATCH",
            f"/files/{quote(require_non_blank_string(file_id, 'file_id'), safe='')}",
            query={
                "addParents": require_non_blank_string(new_parent_id, "new_parent_id"),
                "removeParents": remove_parents,
                "supportsAllDrives": "true",
                "fields": "id,name,mimeType,webViewLink,parents,md5Checksum,modifiedTime",
            },
        )
        if not isinstance(moved, dict):
            raise SkillManagerError("Google Drive file move returned invalid metadata.")
        return moved

    def ensure_folder(self, parent_id: str, name: str) -> dict[str, Any]:
        existing = self.find_child(parent_id, name, mime_type="application/vnd.google-apps.folder")
        if existing is not None:
            return existing
        created = self.request_json(
            "POST",
            "/files",
            payload={
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            },
            query={
                "supportsAllDrives": "true",
                "fields": "id,name,mimeType,webViewLink,parents",
            },
        )
        if not isinstance(created, dict):
            raise SkillManagerError("Google Drive folder creation returned invalid metadata.")
        return created

    def upsert_text_file(self, parent_id: str, name: str, content: str, mime_type: str) -> dict[str, Any]:
        metadata: dict[str, Any] = {"name": name, "mimeType": mime_type}
        existing = self.find_child(parent_id, name)
        if existing is None:
            metadata["parents"] = [parent_id]

        boundary = f"aiws-{uuid.uuid4().hex}"
        metadata_bytes = json.dumps(metadata).encode("utf-8")
        content_bytes = content.encode("utf-8")
        multipart_body = b"".join(
            [
                f"--{boundary}\r\n".encode("ascii"),
                b"Content-Type: application/json; charset=UTF-8\r\n\r\n",
                metadata_bytes,
                b"\r\n",
                f"--{boundary}\r\n".encode("ascii"),
                f"Content-Type: {mime_type}; charset=UTF-8\r\n\r\n".encode("ascii"),
                content_bytes,
                b"\r\n",
                f"--{boundary}--\r\n".encode("ascii"),
            ]
        )
        path = "/files" if existing is None else f"/files/{quote(require_non_blank_string(existing.get('id'), 'id'), safe='')}"
        method = "POST" if existing is None else "PATCH"
        uploaded = self.request_json(
            method,
            path,
            query={
                "uploadType": "multipart",
                "supportsAllDrives": "true",
                "fields": "id,name,mimeType,webViewLink,parents",
            },
            upload=True,
            body=multipart_body,
            headers={"Content-Type": f"multipart/related; boundary={boundary}"},
        )
        if not isinstance(uploaded, dict):
            raise SkillManagerError("Google Drive file upload returned invalid metadata.")
        return uploaded


def require_drive_file(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SkillManagerError(f"{label} returned invalid Google Drive metadata.")
    return value


def drive_folder_url(metadata: dict[str, Any]) -> str:
    folder_id = require_non_blank_string(metadata.get("id"), "id")
    web_view_link = metadata.get("webViewLink")
    if isinstance(web_view_link, str) and web_view_link.strip():
        return web_view_link.strip()
    return f"https://drive.google.com/drive/folders/{folder_id}"


def read_snapshot_skill_markdown(snapshot_root: Path, skill_id: str) -> str:
    skill_path = snapshot_root / "skills" / skill_id / "SKILL.md"
    if not skill_path.is_file() or skill_path.is_symlink():
        raise SkillManagerError(f"Draft base snapshot is missing skills/{skill_id}/SKILL.md.")
    return skill_path.read_text(encoding="utf-8")


def read_draft_skill_markdown(draft_path: Path, skill_id: str) -> str:
    skill_path = draft_path / "skills" / skill_id / "SKILL.md"
    if not skill_path.is_file() or skill_path.is_symlink():
        raise SkillManagerError(f"Draft is missing skills/{skill_id}/SKILL.md.")
    return skill_path.read_text(encoding="utf-8")


def drive_review_packet_payload(
    payload: dict[str, Any],
    *,
    proposal_folder_id: str,
    proposal_folder_url: str,
    submitted_at: str,
) -> dict[str, Any]:
    return {
        "proposal_id": require_non_blank_string(payload.get("proposal_id"), "proposal_id"),
        "draft_id": require_non_blank_string(payload.get("draft_id"), "draft_id"),
        "plugin_id": require_non_blank_string(payload.get("plugin_id"), "plugin_id"),
        "skill_id": require_non_blank_string(payload.get("skill_id"), "skill_id"),
        "target_scope": require_non_blank_string(payload.get("target_scope"), "target_scope"),
        "scope_id": require_non_blank_string(payload.get("scope_id"), "scope_id"),
        "backend_kind": require_backend_kind(payload.get("backend_kind")),
        "backend_ref": require_non_blank_string(payload.get("backend_ref"), "backend_ref"),
        "marketplace_id": require_marketplace_id(payload.get("marketplace_id")),
        "summary": require_non_blank_string(payload.get("summary"), "summary"),
        "rationale": require_non_blank_string(payload.get("rationale"), "rationale"),
        "base_version": require_non_blank_string(payload.get("base_version"), "base_version"),
        "base_commit": require_non_blank_string(payload.get("base_commit"), "base_commit"),
        "base_tree_digest": require_non_blank_string(payload.get("base_tree_digest"), "base_tree_digest"),
        "current_tree_digest": require_non_blank_string(payload.get("current_tree_digest"), "current_tree_digest"),
        "validation_status": require_non_blank_string(payload.get("validation_status"), "validation_status"),
        "validation_tree_digest": require_non_blank_string(
            payload.get("validation_tree_digest"), "validation_tree_digest"
        ),
        "status": "submitted_for_review",
        "backend_review_state": "in_review",
        "proposal_folder_id": proposal_folder_id,
        "proposal_folder_url": proposal_folder_url,
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
    }


class GoogleDriveProposalSubmitter:
    def __init__(
        self,
        *,
        aiws_root: Path,
        token: str | None = None,
        drive_client: Any | None = None,
    ) -> None:
        self.aiws_root = aiws_root
        resolved_token = token or google_drive_api_token_from_env()
        if drive_client is None and resolved_token is None:
            raise SkillManagerError(
                "Google Drive submit requires AIWS_GOOGLE_DRIVE_TOKEN, GOOGLE_DRIVE_TOKEN, or GOOGLE_OAUTH_ACCESS_TOKEN."
            )
        self.drive_client = drive_client or GoogleDriveApiClient(token=resolved_token)

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal_id = require_non_blank_string(payload.get("proposal_id"), "proposal_id")
        record_id = require_non_blank_string(payload.get("draft_id"), "draft_id")
        plugin_id = require_non_blank_string(payload.get("plugin_id"), "plugin_id")
        skill_id = require_non_blank_string(payload.get("skill_id"), "skill_id")
        marketplace_root_id = require_non_blank_string(payload.get("backend_ref"), "backend_ref")
        draft_path = Path(require_non_blank_string(payload.get("draft_path"), "draft_path"))
        record = require_canonical_draft_record(self.aiws_root, record_id)
        base_snapshot_root = ensure_base_tree_snapshot(self.aiws_root, record_id, draft_path, record)
        base_skill_markdown = read_snapshot_skill_markdown(base_snapshot_root, skill_id)
        proposed_skill_markdown = read_draft_skill_markdown(draft_path, skill_id)

        plugins_folder = require_drive_file(
            self.drive_client.ensure_folder(marketplace_root_id, "plugins"),
            label="Google Drive plugins folder",
        )
        plugin_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(plugins_folder.get("id"), "id"),
                plugin_id,
            ),
            label="Google Drive plugin folder",
        )
        proposals_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(plugin_folder.get("id"), "id"),
                "proposals",
            ),
            label="Google Drive proposals folder",
        )
        in_review_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(proposals_folder.get("id"), "id"),
                "in_review",
            ),
            label="Google Drive in_review folder",
        )
        proposal_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(in_review_folder.get("id"), "id"),
                proposal_id,
            ),
            label="Google Drive proposal folder",
        )
        proposal_folder_id = require_non_blank_string(proposal_folder.get("id"), "proposal_folder_id")
        proposal_folder_url = drive_folder_url(proposal_folder)
        submitted_at = utc_now()
        approved_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(proposals_folder.get("id"), "id"),
                "approved",
            ),
            label="Google Drive approved folder",
        )
        rejected_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(proposals_folder.get("id"), "id"),
                "rejected",
            ),
            label="Google Drive rejected folder",
        )
        released_folder = require_drive_file(
            self.drive_client.ensure_folder(
                require_non_blank_string(proposals_folder.get("id"), "id"),
                "released",
            ),
            label="Google Drive released folder",
        )
        proposal_json = drive_review_packet_payload(
            payload,
            proposal_folder_id=proposal_folder_id,
            proposal_folder_url=proposal_folder_url,
            submitted_at=submitted_at,
        )
        base_skill_file = require_drive_file(
            self.drive_client.upsert_text_file(
                proposal_folder_id,
                "base.SKILL.md",
                base_skill_markdown,
                "text/markdown",
            ),
            label="Google Drive base skill file",
        )
        proposed_skill_file = require_drive_file(
            self.drive_client.upsert_text_file(
                proposal_folder_id,
                "proposed.SKILL.md",
                proposed_skill_markdown,
                "text/markdown",
            ),
            label="Google Drive proposed skill file",
        )
        proposal_json_file = require_drive_file(
            self.drive_client.upsert_text_file(
                proposal_folder_id,
                "proposal.json",
                json.dumps(proposal_json, indent=2, sort_keys=True) + "\n",
                "application/json",
            ),
            label="Google Drive proposal json file",
        )
        return {
            "status": "submitted_for_review",
            "proposal_folder_id": proposal_folder_id,
            "proposal_folder_url": proposal_folder_url,
            "backend_review_state": "in_review",
            "plugins_folder_id": require_non_blank_string(plugins_folder.get("id"), "plugins_folder_id"),
            "plugin_folder_id": require_non_blank_string(plugin_folder.get("id"), "plugin_folder_id"),
            "proposals_folder_id": require_non_blank_string(proposals_folder.get("id"), "proposals_folder_id"),
            "in_review_folder_id": require_non_blank_string(in_review_folder.get("id"), "in_review_folder_id"),
            "approved_folder_id": require_non_blank_string(approved_folder.get("id"), "approved_folder_id"),
            "rejected_folder_id": require_non_blank_string(rejected_folder.get("id"), "rejected_folder_id"),
            "released_folder_id": require_non_blank_string(released_folder.get("id"), "released_folder_id"),
            "base_skill_file_id": require_non_blank_string(base_skill_file.get("id"), "base_skill_file_id"),
            "proposed_skill_file_id": require_non_blank_string(
                proposed_skill_file.get("id"),
                "proposed_skill_file_id",
            ),
            "proposal_json_file_id": require_non_blank_string(
                proposal_json_file.get("id"),
                "proposal_json_file_id",
            ),
        }


def proposal_state_status_label(status: str) -> str:
    return {
        "staged": "Staged",
        "submitted_for_review": "Submitted for review",
        "approved_pending_publish": "Approved pending publish",
        "needs_reapproval": "Needs reapproval",
        "publishing": "Publishing",
        "released": "Released",
        "rejected": "Rejected",
    }.get(status, status.replace("_", " ").capitalize())


def drive_review_state_response(proposal: dict[str, Any]) -> dict[str, Any]:
    response = {
        "status": require_non_blank_string(proposal.get("status"), "status"),
        "status_label": proposal_state_status_label(require_non_blank_string(proposal.get("status"), "status")),
        "proposal_id": proposal["proposal_id"],
        "draft_id": proposal["draft_id"],
        "plugin_id": proposal["plugin_id"],
        "skill_id": proposal["skill_id"],
        "target_scope": proposal["target_scope"],
        "backend_kind": "google_drive",
        "backend_ref": require_non_blank_string(proposal.get("backend_ref"), "backend_ref"),
        "marketplace_id": require_marketplace_id(proposal.get("marketplace_id")),
        "proposal_folder_id": require_non_blank_string(proposal.get("proposal_folder_id"), "proposal_folder_id"),
        "proposal_folder_url": require_non_blank_string(proposal.get("proposal_folder_url"), "proposal_folder_url"),
        "backend_review_state": require_non_blank_string(
            proposal.get("backend_review_state") or "in_review",
            "backend_review_state",
        ),
    }
    for key in (
        "approved_at",
        "approved_proposed_skill_file_id",
        "approved_proposed_skill_md5",
        "approved_proposed_skill_modified_time",
        "rejected_at",
        "released_at",
    ):
        value = proposal.get(key)
        if isinstance(value, str) and value.strip():
            response[key] = value
    return response


def refresh_proposal_state(
    aiws_root: Path,
    proposal_id: str,
    *,
    drive_client: Any | None = None,
) -> dict[str, Any]:
    proposal = load_proposal_record(aiws_root, proposal_id)
    backend_kind = require_backend_kind(proposal.get("backend_kind", "github"))
    if backend_kind != "google_drive":
        raise SkillManagerError(f"refresh_proposal_state is only implemented for google_drive proposals, got {backend_kind}.")
    client = drive_client
    if client is None:
        token = google_drive_api_token_from_env()
        if token is None:
            raise SkillManagerError(
                "Google Drive refresh requires AIWS_GOOGLE_DRIVE_TOKEN, GOOGLE_DRIVE_TOKEN, or GOOGLE_OAUTH_ACCESS_TOKEN."
            )
        client = GoogleDriveApiClient(token=token)

    proposal_folder_id = require_non_blank_string(proposal.get("proposal_folder_id"), "proposal_folder_id")
    proposal_folder = require_drive_file(client.get_file(proposal_folder_id), label="Google Drive proposal folder")
    parents = proposal_folder.get("parents")
    if not isinstance(parents, list) or not parents:
        raise SkillManagerError("Google Drive proposal folder has no parent metadata.")
    current_parent_id = require_non_blank_string(parents[0], "proposal_folder_parent")
    in_review_folder_id = require_non_blank_string(proposal.get("in_review_folder_id"), "in_review_folder_id")
    approved_folder_id = require_non_blank_string(proposal.get("approved_folder_id"), "approved_folder_id")
    rejected_folder_id = require_non_blank_string(proposal.get("rejected_folder_id"), "rejected_folder_id")
    released_folder_id = require_non_blank_string(proposal.get("released_folder_id"), "released_folder_id")

    updated = dict(proposal)
    updated["proposal_folder_url"] = drive_folder_url(proposal_folder)
    now = utc_now()

    if current_parent_id == approved_folder_id:
        proposed_skill_file_id = require_non_blank_string(
            updated.get("proposed_skill_file_id"),
            "proposed_skill_file_id",
        )
        proposed_skill_file = require_drive_file(
            client.get_file(proposed_skill_file_id),
            label="Google Drive proposed skill file",
        )
        approved_md5 = require_non_blank_string(proposed_skill_file.get("md5Checksum"), "md5Checksum")
        approved_modified_time = require_non_blank_string(
            proposed_skill_file.get("modifiedTime"),
            "modifiedTime",
        )
        previous_md5 = updated.get("approved_proposed_skill_md5")
        if isinstance(previous_md5, str) and previous_md5 and previous_md5 != approved_md5:
            moved_folder = require_drive_file(
                client.move_file(proposal_folder_id, in_review_folder_id),
                label="Google Drive proposal move",
            )
            updated["proposal_folder_url"] = drive_folder_url(moved_folder)
            updated["status"] = "needs_reapproval"
            updated["backend_review_state"] = "in_review"
        else:
            updated["status"] = "approved_pending_publish"
            updated["backend_review_state"] = "approved"
            updated["approved_at"] = str(updated.get("approved_at") or now)
            updated["approved_proposed_skill_file_id"] = proposed_skill_file_id
            updated["approved_proposed_skill_md5"] = approved_md5
            updated["approved_proposed_skill_modified_time"] = approved_modified_time
    elif current_parent_id == rejected_folder_id:
        updated["status"] = "rejected"
        updated["backend_review_state"] = "rejected"
        updated["rejected_at"] = str(updated.get("rejected_at") or now)
    elif current_parent_id == released_folder_id:
        updated["status"] = "released"
        updated["backend_review_state"] = "released"
        updated["released_at"] = str(updated.get("released_at") or now)
    elif current_parent_id == in_review_folder_id:
        if updated.get("status") == "needs_reapproval":
            updated["backend_review_state"] = "in_review"
        else:
            updated["status"] = "submitted_for_review"
            updated["backend_review_state"] = "in_review"
    else:
        raise SkillManagerError("Google Drive proposal folder is not under a recognized review state folder.")

    updated["updated_at"] = now
    write_proposal_record(aiws_root, proposal_id, updated)
    proposal_json = dict(updated)
    proposal_json.pop("draft_path", None)
    client.upsert_text_file(
        proposal_folder_id,
        "proposal.json",
        json.dumps(proposal_json, indent=2, sort_keys=True) + "\n",
        "application/json",
    )
    return drive_review_state_response(updated)


def submit_pr(
    aiws_root: Path,
    proposal_id: str,
    submitter: Any,
    *,
    required_review_roles: list[str] | tuple[str, ...] | None = None,
    allowed_target_repos: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, Any]:
    proposal_id = require_non_blank_string(proposal_id, "proposal_id")
    proposal = load_proposal_record(aiws_root, proposal_id)
    backend_kind = require_backend_kind(proposal.get("backend_kind", "github"))
    target_repo = proposal.get("target_repo")
    if backend_kind == "github":
        target_repo = require_non_blank_string(target_repo, "target_repo")
        if allowed_target_repos is not None and target_repo not in set(allowed_target_repos):
            raise SkillManagerError(f"target_repo is not allowed: {target_repo}")

    status = proposal.get("status")
    if status == "submitted_for_review":
        try:
            return submitted_review_response(proposal)
        except SkillManagerError as exc:
            raise SkillManagerError(f"submitted proposal metadata is incomplete: {proposal_id}") from exc
    if status != "staged":
        raise SkillManagerError(f"Proposal {proposal_id} is not staged for review.")
    if proposal.get("validation_status") != "passed":
        raise SkillManagerError(f"Proposal {proposal_id} validation status is not passed.")

    record_id = require_non_blank_string(proposal.get("draft_id"), "draft_id")
    record = safely_identify_draft_record(aiws_root, record_id)
    canonical_record_id = draft_id(record.plugin_id, record.skill_id, record.origin_repo)
    if canonical_record_id != record_id or canonical_record_id != proposal.get("draft_id"):
        raise SkillManagerError(f"Draft record id does not match canonical draft id {canonical_record_id}.")

    plugins_root = aiws_root / "plugins"
    draft_path = require_path_under(Path(record.draft_path), plugins_root, label="Draft path")
    expected_draft_path = require_path_under(
        draft_worktree_path(aiws_root, record.origin_marketplace, record.plugin_id, record.origin_repo),
        plugins_root,
        label="Expected draft path",
    )
    if draft_path != expected_draft_path:
        raise SkillManagerError(f"Draft record {record_id} points to an unexpected draft path.")

    current_tree_digest = tree_digest(draft_path)
    validation_tree_digest = require_non_blank_string(
        proposal.get("validation_tree_digest"), "validation_tree_digest"
    )
    if current_tree_digest != validation_tree_digest:
        raise SkillManagerError(f"Draft {record_id} changed since staging; restage before submit.")
    require_changes_only_under_skill(aiws_root, record_id, draft_path, record.skill_id)

    validation = validate_plugin(draft_path, expected_name=record.plugin_id, expected_version=record.base_version)
    skill_names = {skill["name"] for skill in validation["skills"]}
    if record.skill_id not in skill_names:
        raise SkillManagerError(f"Requested skill {record.skill_id!r} does not exist in plugin {record.plugin_id!r}.")

    review_roles = normalize_review_roles(required_review_roles)
    branch_name = proposal_branch_name(proposal_id)
    submitter_payload = {
        **proposal,
        "branch_name": branch_name,
        "target_repo": target_repo,
        "draft_path": record.draft_path,
        "validation_tree_digest": validation_tree_digest,
    }
    submitter_payload.pop("required_review_roles", None)
    if review_roles:
        submitter_payload["required_review_roles"] = review_roles
    submitter_result = call_proposal_submitter(submitter, submitter_payload)
    if submitter_result.get("status") == "no_changes_to_submit":
        response = {
            "status": "no_changes_to_submit",
            "status_label": "No changes to submit",
            "proposal_id": proposal["proposal_id"],
            "draft_id": proposal["draft_id"],
            "plugin_id": proposal["plugin_id"],
            "skill_id": proposal["skill_id"],
            "target_scope": proposal["target_scope"],
            "branch_name": branch_name,
        }
        if backend_kind == "github":
            response["target_repo"] = proposal["target_repo"]
        else:
            response["backend_kind"] = backend_kind
            response["backend_ref"] = proposal.get("backend_ref")
            response["marketplace_id"] = proposal.get("marketplace_id")
        return response
    if submitter_result.get("status") == "submit_handoff_required":
        if backend_kind != "github":
            raise SkillManagerError("submitter returned unsupported handoff metadata for non-GitHub proposal.")
        try:
            handoff_branch_name = require_non_blank_string(submitter_result.get("branch_name"), "branch_name")
            handoff_target_repo = require_non_blank_string(submitter_result.get("target_repo"), "target_repo")
            handoff_proposal_id = require_non_blank_string(submitter_result.get("proposal_id"), "proposal_id")
            handoff_draft_id = require_non_blank_string(submitter_result.get("draft_id"), "draft_id")
        except SkillManagerError as exc:
            raise SkillManagerError("submitter returned invalid handoff metadata.") from exc
        if (
            handoff_branch_name != branch_name
            or handoff_target_repo != target_repo
            or handoff_proposal_id != proposal_id
            or handoff_draft_id != proposal["draft_id"]
        ):
            raise SkillManagerError("submitter returned invalid handoff metadata.")
        handoff_response = {
            **submitter_result,
            "status": "submit_handoff_required",
            "status_label": str(submitter_result.get("status_label") or "GitHub submit handoff required"),
            "reason_code": str(submitter_result.get("reason_code") or "github_cli_unavailable"),
            "proposal_id": proposal["proposal_id"],
            "draft_id": proposal["draft_id"],
            "plugin_id": proposal["plugin_id"],
            "skill_id": proposal["skill_id"],
            "target_scope": proposal["target_scope"],
            "target_repo": target_repo,
            "branch_name": branch_name,
            "terminal": False,
            "no_pr_created": True,
            "repository_review_policy": repository_review_policy_from_codeowners("unknown"),
            "post_merge_delivery": post_merge_delivery_guidance(target_repo),
        }
        returned_review_roles = []
        if review_roles:
            returned_review_roles = normalize_review_roles(
                submitter_result["required_review_roles"]
                if isinstance(submitter_result.get("required_review_roles"), (list, tuple))
                else review_roles
            )
        if returned_review_roles:
            handoff_response["required_review_roles"] = returned_review_roles
        else:
            handoff_response.pop("required_review_roles", None)
        return handoff_response

    submitted_at = utc_now()
    updated_proposal = {**proposal, "status": "submitted_for_review", "submitted_at": submitted_at, "updated_at": submitted_at}
    updated_proposal.pop("required_review_roles", None)
    if review_roles:
        updated_proposal["required_review_roles"] = review_roles
    if backend_kind == "github":
        try:
            submitted_branch_name = require_non_blank_string(submitter_result.get("branch_name"), "branch_name")
            pr_url = require_non_blank_string(submitter_result.get("pr_url"), "pr_url")
        except SkillManagerError as exc:
            raise SkillManagerError("submitter returned invalid review metadata.") from exc
        if submitted_branch_name != branch_name:
            raise SkillManagerError("submitter returned invalid review metadata.")
        repository_review_policy = submitter_result.get("repository_review_policy")
        if not isinstance(repository_review_policy, dict):
            repository_review_policy = repository_review_policy_from_codeowners("unknown")
        updated_proposal.update(
            {
                "branch_name": submitted_branch_name,
                "pr_url": pr_url,
                "repository_review_policy": repository_review_policy,
            }
        )
    elif backend_kind == "google_drive":
        try:
            proposal_folder_id = require_non_blank_string(submitter_result.get("proposal_folder_id"), "proposal_folder_id")
            proposal_folder_url = require_non_blank_string(
                submitter_result.get("proposal_folder_url"),
                "proposal_folder_url",
            )
        except SkillManagerError as exc:
            raise SkillManagerError("submitter returned invalid review metadata.") from exc
        updated_proposal.update(
            {
                "proposal_folder_id": proposal_folder_id,
                "proposal_folder_url": proposal_folder_url,
                "backend_review_state": require_non_blank_string(
                    submitter_result.get("backend_review_state") or "in_review",
                    "backend_review_state",
                ),
            }
        )
        for key in (
            "plugins_folder_id",
            "plugin_folder_id",
            "proposals_folder_id",
            "in_review_folder_id",
            "approved_folder_id",
            "rejected_folder_id",
            "released_folder_id",
            "base_skill_file_id",
            "proposed_skill_file_id",
            "proposal_json_file_id",
        ):
            value = submitter_result.get(key)
            if value is not None:
                updated_proposal[key] = require_non_blank_string(value, key)
    else:
        raise SkillManagerError(f"{backend_kind} proposal submitter is not implemented yet.")
    write_proposal_record(aiws_root, proposal_id, updated_proposal)
    return submitted_review_response(updated_proposal)


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
    snapshot_path = draft_base_snapshot_path(aiws_root, record_id)
    require_record_path_under(snapshot_path, state_root)
    if snapshot_path.exists():
        if snapshot_path.is_symlink() or not snapshot_path.is_dir():
            raise SkillManagerError(f"Draft base snapshot path is unsafe: {snapshot_path}")
        shutil.rmtree(snapshot_path)
    record_path.unlink()
    return {"status": "reverted", "record_id": record_id}


def update_from_github_decision(record: DraftRecord | None) -> dict[str, Any]:
    if record is not None and record.modified:
        return {
            "allowed": False,
            "reason": "modified_draft_or_pending_upload",
            "choices": UPDATE_CONFLICT_CHOICES,
        }
    return {"allowed": True, "reason": "no_modified_draft_or_pending_upload", "choices": []}
