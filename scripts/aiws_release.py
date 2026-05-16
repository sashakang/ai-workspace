from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.build_cowork_import import build_plugin_package


SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VALID_BUMPS = {"patch", "minor", "major"}


class ReleaseError(ValueError):
    pass


@dataclass(frozen=True)
class PluginReleaseTarget:
    plugin_id: str
    plugin_root: Path
    manifest_path: Path
    contract_path: Path | None
    marketplace_path: Path
    marketplace_entry: dict[str, Any]
    manifest: dict[str, Any]
    contract: dict[str, Any] | None
    marketplace: dict[str, Any]


def prepare_plugin_release(
    repo_root: Path,
    plugin_id: str,
    *,
    bump_type: str | None = None,
    explicit_version: str | None = None,
) -> dict[str, Any]:
    target = resolve_release_target(repo_root, plugin_id)
    validate_plugin_release(repo_root, plugin_id)
    old_version = require_semver(str(target.manifest["version"]), "current plugin version")
    new_version = choose_next_version(old_version, bump_type=bump_type, explicit_version=explicit_version)

    if compare_semver(new_version, old_version) <= 0:
        raise ReleaseError(f"New version {new_version} must be greater than current version {old_version}.")

    target.manifest["version"] = new_version
    write_json(target.manifest_path, target.manifest)

    changed = [relative_to_repo(repo_root, target.manifest_path)]
    if target.contract is not None and target.contract_path is not None:
        target.contract["version"] = new_version
        write_json(target.contract_path, target.contract)
        changed.append(relative_to_repo(repo_root, target.contract_path))

    target.marketplace_entry["version"] = new_version
    write_json(target.marketplace_path, target.marketplace)
    changed.append(relative_to_repo(repo_root, target.marketplace_path))

    validate_plugin_release(repo_root, plugin_id)
    return {
        "status": "prepared",
        "plugin_id": plugin_id,
        "old_version": old_version,
        "new_version": new_version,
        "changed": changed,
    }


def validate_plugin_release(repo_root: Path, plugin_id: str) -> dict[str, Any]:
    target = resolve_release_target(repo_root, plugin_id)
    manifest_version = require_semver(str(target.manifest.get("version", "")), "plugin manifest version")
    marketplace_version = require_semver(str(target.marketplace_entry.get("version", "")), "marketplace plugin version")
    if target.manifest.get("name") != plugin_id:
        raise ReleaseError(f"Plugin manifest name must be {plugin_id!r}.")
    if manifest_version != marketplace_version:
        raise ReleaseError(
            f"Plugin version drift: manifest has {manifest_version}, marketplace has {marketplace_version}."
        )

    skills = sorted(
        path.name for path in (target.plugin_root / "skills").iterdir() if path.is_dir()
    ) if (target.plugin_root / "skills").is_dir() else []
    for skill_id in skills:
        skill_file = target.plugin_root / "skills" / skill_id / "SKILL.md"
        if not skill_file.is_file():
            raise ReleaseError(f"Missing SKILL.md for public skill candidate: {skill_id}")

    if target.contract is not None:
        validate_contract_schema(repo_root, target.contract)
        contract_version = require_semver(str(target.contract.get("version", "")), "contract version")
        if target.contract.get("plugin_id") != plugin_id:
            raise ReleaseError(f"Contract plugin_id must be {plugin_id!r}.")
        if contract_version != manifest_version:
            raise ReleaseError(
                f"Plugin version drift: manifest has {manifest_version}, contract has {contract_version}."
            )
        public_skills = target.contract.get("public_skills")
        missing = sorted(set(public_skills) - set(skills))
        if missing:
            raise ReleaseError(f"Contract public_skills missing skill folders: {missing}")

    return {
        "status": "ok",
        "plugin_id": plugin_id,
        "version": manifest_version,
        "skills": skills,
    }


def build_release_package(repo_root: Path, plugin_id: str, output_dir: Path) -> Path:
    validate_plugin_release(repo_root, plugin_id)
    return build_plugin_package(repo_root, plugin_id, output_dir)


def resolve_release_target(repo_root: Path, plugin_id: str) -> PluginReleaseTarget:
    repo_root = repo_root.resolve()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*[a-z0-9]", plugin_id):
        raise ReleaseError(f"Invalid plugin_id: {plugin_id!r}")

    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = read_json(marketplace_path)
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        raise ReleaseError("marketplace.json must contain a plugins list.")
    matches = [entry for entry in plugins if isinstance(entry, dict) and entry.get("name") == plugin_id]
    if len(matches) != 1:
        raise ReleaseError(f"Plugin {plugin_id!r} must appear exactly once in marketplace.json.")
    entry = matches[0]
    source = entry.get("source")
    if not isinstance(source, str) or not source:
        raise ReleaseError(f"Marketplace entry for {plugin_id} must define source.")
    plugin_root = (repo_root / source).resolve()
    try:
        plugin_root.relative_to(repo_root)
    except ValueError as exc:
        raise ReleaseError(f"Marketplace source escapes repository: {source}") from exc
    if plugin_root.is_symlink():
        raise ReleaseError(f"Plugin root must not be a symlink: {source}")

    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    manifest = read_json(manifest_path)
    contract_path = plugin_root / "contracts" / f"{plugin_id}.contract.json"
    contract = read_json(contract_path) if contract_path.exists() else None
    return PluginReleaseTarget(
        plugin_id=plugin_id,
        plugin_root=plugin_root,
        manifest_path=manifest_path,
        contract_path=contract_path if contract_path.exists() else None,
        marketplace_path=marketplace_path,
        marketplace_entry=entry,
        manifest=manifest,
        contract=contract,
        marketplace=marketplace,
    )


def choose_next_version(
    current_version: str,
    *,
    bump_type: str | None = None,
    explicit_version: str | None = None,
) -> str:
    if bool(bump_type) == bool(explicit_version):
        raise ReleaseError("Specify exactly one of bump_type or explicit_version.")
    current = parse_semver(current_version, "current version")
    if explicit_version is not None:
        return require_semver(explicit_version, "explicit_version")
    if bump_type not in VALID_BUMPS:
        raise ReleaseError(f"bump_type must be one of {sorted(VALID_BUMPS)}.")
    major, minor, patch = current
    if bump_type == "major":
        return f"{major + 1}.0.0"
    if bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"


def compare_semver(left: str, right: str) -> int:
    left_tuple = parse_semver(left, "left version")
    right_tuple = parse_semver(right, "right version")
    return (left_tuple > right_tuple) - (left_tuple < right_tuple)


def require_semver(value: str, label: str) -> str:
    parse_semver(value, label)
    return value


def parse_semver(value: str, label: str) -> tuple[int, int, int]:
    match = SEMVER_RE.fullmatch(value)
    if match is None:
        raise ReleaseError(f"{label} must be SemVer MAJOR.MINOR.PATCH: {value!r}")
    return tuple(int(part) for part in match.groups())


def validate_contract_schema(repo_root: Path, contract: dict[str, Any]) -> None:
    schema_path = repo_root / "core-aiws" / "contracts" / "plugin-contract.schema.json"
    schema = read_json(schema_path)
    _validate_schema_node(contract, schema, "$")


def _validate_schema_node(value: Any, schema: dict[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            raise ReleaseError(f"{path} must be an object.")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise ReleaseError(f"{path} missing required property {key!r}.")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    raise ReleaseError(f"{path} has additional property {key!r}.")
        for key, child_schema in properties.items():
            if key in value:
                _validate_schema_node(value[key], child_schema, f"{path}.{key}")
    elif expected_type == "array":
        if not isinstance(value, list):
            raise ReleaseError(f"{path} must be an array.")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_node(item, item_schema, f"{path}[{index}]")
    elif expected_type == "string":
        if not isinstance(value, str):
            raise ReleaseError(f"{path} must be a string.")
        if schema.get("minLength", 0) and len(value) < schema["minLength"]:
            raise ReleaseError(f"{path} must not be empty.")
    elif expected_type == "boolean":
        if not isinstance(value, bool):
            raise ReleaseError(f"{path} must be a boolean.")


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"Missing JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleaseError(f"JSON file must contain an object: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def relative_to_repo(repo_root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare and validate AIWS plugin releases.")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--plugin-id", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--plugin-id", required=True)
    prepare.add_argument("--bump-type", choices=sorted(VALID_BUMPS))
    prepare.add_argument("--explicit-version")

    package = subparsers.add_parser("package")
    package.add_argument("--plugin-id", required=True)
    package.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_plugin_release(args.repo_root, args.plugin_id)
        elif args.command == "prepare":
            result = prepare_plugin_release(
                args.repo_root,
                args.plugin_id,
                bump_type=args.bump_type,
                explicit_version=args.explicit_version,
            )
        else:
            package_path = build_release_package(args.repo_root, args.plugin_id, args.output_dir)
            result = {"status": "packaged", "package_path": str(package_path)}
    except ReleaseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
