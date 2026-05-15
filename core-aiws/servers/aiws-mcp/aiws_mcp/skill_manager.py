from __future__ import annotations

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
        roots.append(Path(cowork_home).expanduser())
    roots.append(Path("~/.cowork").expanduser())

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
            return refreshed

    if expected_draft_path.exists():
        raise SkillManagerError(f"Draft path already exists without a usable record: {expected_draft_path}")

    expected_draft_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_plugin_root, expected_draft_path)
    base_tree_digest = tree_digest(expected_draft_path)
    write_base_tree_manifest(aiws_root, record_id, expected_draft_path)

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
    target_repo: str,
    summary: str,
    rationale: str,
) -> dict[str, Any]:
    record_id = require_non_blank_string(record_id, "record_id")
    target_scope = require_non_blank_string(target_scope, "target_scope")
    target_repo = require_non_blank_string(target_repo, "target_repo")
    summary = require_non_blank_string(summary, "summary")
    rationale = require_non_blank_string(rationale, "rationale")

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
            "target_repo": target_repo,
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
                "target_repo": target_repo,
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


def submitted_review_response(proposal: dict[str, Any]) -> dict[str, Any]:
    branch_name = require_non_blank_string(proposal.get("branch_name"), "branch_name")
    pr_url = require_non_blank_string(proposal.get("pr_url"), "pr_url")
    return {
        "status": "submitted_for_review",
        "status_label": "Submitted for review",
        "proposal_id": proposal["proposal_id"],
        "draft_id": proposal["draft_id"],
        "plugin_id": proposal["plugin_id"],
        "skill_id": proposal["skill_id"],
        "target_scope": proposal["target_scope"],
        "target_repo": proposal["target_repo"],
        "branch_name": branch_name,
        "pr_url": pr_url,
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


def write_pr_body(path: Path, payload: dict[str, Any], *, codeowners_status: str) -> None:
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
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        write_pr_body(body_path, payload, codeowners_status=detect_codeowners(repo_dir))
        if isinstance(existing_prs, list) and existing_prs and isinstance(existing_prs[0], dict):
            pr_url = require_non_blank_string(existing_prs[0].get("url"), "pr_url")
            update_existing_pr_metadata(
                self,
                target_repo=target_repo,
                pr_url=pr_url,
                is_draft=bool(existing_prs[0].get("isDraft")),
                body_path=body_path,
            )
            return {"status": "submitted_for_review", "branch_name": branch_name, "pr_url": pr_url}

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
        return {"status": "submitted_for_review", "branch_name": branch_name, "pr_url": pr_url}


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
    target_repo = require_non_blank_string(proposal.get("target_repo"), "target_repo")
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
        return {
            "status": "no_changes_to_submit",
            "status_label": "No changes to submit",
            "proposal_id": proposal["proposal_id"],
            "draft_id": proposal["draft_id"],
            "plugin_id": proposal["plugin_id"],
            "skill_id": proposal["skill_id"],
            "target_scope": proposal["target_scope"],
            "target_repo": proposal["target_repo"],
            "branch_name": branch_name,
        }
    if submitter_result.get("status") == "submit_handoff_required":
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
    try:
        submitted_branch_name = require_non_blank_string(submitter_result.get("branch_name"), "branch_name")
        pr_url = require_non_blank_string(submitter_result.get("pr_url"), "pr_url")
    except SkillManagerError as exc:
        raise SkillManagerError("submitter returned invalid review metadata.") from exc
    if submitted_branch_name != branch_name:
        raise SkillManagerError("submitter returned invalid review metadata.")

    submitted_at = utc_now()
    updated_proposal = {
        **proposal,
        "status": "submitted_for_review",
        "branch_name": submitted_branch_name,
        "pr_url": pr_url,
        "submitted_at": submitted_at,
        "updated_at": submitted_at,
    }
    updated_proposal.pop("required_review_roles", None)
    if review_roles:
        updated_proposal["required_review_roles"] = review_roles
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
    record_path.unlink()
    return {"status": "reverted", "record_id": record_id}


def update_from_github_decision(record: DraftRecord | None) -> dict[str, Any]:
    if record is not None and record.modified:
        return {
            "allowed": False,
            "reason": "modified_draft_or_pending_upload",
            "choices": ["keep_local_draft_and_pending_package", "discard_local_changes_and_update", "submit_or_upload_first"],
        }
    return {"allowed": True, "reason": "no_modified_draft_or_pending_upload", "choices": []}
