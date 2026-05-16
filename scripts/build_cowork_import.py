from __future__ import annotations

import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path
from typing import Iterable


EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "build",
    "dist",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def launcher_check() -> dict[str, str]:
    if shutil.which("uvx") is None:
        return {
            "status": "missing_uvx",
            "message": "uvx is required to start the bundled aiws-mcp server from Cowork.",
        }
    return {"status": "ok", "message": "uvx is available."}


def build_core_aiws_package(repo_root: Path, output_dir: Path) -> Path:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    core_root = repo_root / "core-aiws"
    manifest_path = core_root / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_path = output_dir / f"{manifest['name']}-{manifest['version']}.zip"

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for source in _iter_files(core_root):
            _write_file(package, source, source.relative_to(core_root))

    return package_path


def build_productivity_package(repo_root: Path, output_dir: Path) -> Path:
    return build_plugin_package(repo_root, "aiws-productivity", output_dir)


def build_cowork_import_packages(repo_root: Path, output_dir: Path) -> list[Path]:
    return [
        build_core_aiws_package(repo_root, output_dir),
        build_productivity_package(repo_root, output_dir),
    ]


def build_plugin_package(repo_root: Path, plugin_name: str, output_dir: Path) -> Path:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    plugin_root = resolve_marketplace_plugin_root(repo_root, plugin_name)
    manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    package_path = output_dir / f"{manifest['name']}-{manifest['version']}.zip"

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for source in _iter_files(plugin_root):
            _write_file(package, source, source.relative_to(plugin_root))

    return package_path


def resolve_marketplace_plugin_root(repo_root: Path, plugin_name: str) -> Path:
    repo_root = repo_root.resolve()
    marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    matches = [
        item
        for item in marketplace.get("plugins", [])
        if isinstance(item, dict) and item.get("name") == plugin_name
    ]
    if len(matches) != 1:
        raise ValueError(f"Plugin {plugin_name!r} must appear exactly once in marketplace.json.")
    source = matches[0].get("source")
    if not isinstance(source, str) or not source:
        raise ValueError(f"Plugin {plugin_name!r} must define marketplace source.")
    plugin_root = (repo_root / source).resolve()
    try:
        plugin_root.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(f"Marketplace source escapes repository: {source}") from exc
    if not plugin_root.is_dir():
        raise ValueError(f"Marketplace source is not a plugin directory: {source}")
    return plugin_root


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if _is_excluded(path, root):
            continue
        yield path


def _is_excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIR_NAMES for part in relative.parts):
        return True
    if any(part.endswith(".egg-info") for part in relative.parts):
        return True
    return path.suffix in EXCLUDED_SUFFIXES


def _write_file(package: zipfile.ZipFile, source: Path, archive_name: Path) -> None:
    info = zipfile.ZipInfo(str(archive_name))
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = source.stat().st_mode
    if mode & stat.S_IXUSR:
        info.external_attr = 0o755 << 16
    else:
        info.external_attr = 0o644 << 16
    package.writestr(info, source.read_bytes())


if __name__ == "__main__":
    if "--plugin-id" in sys.argv:
        plugin_id = sys.argv[sys.argv.index("--plugin-id") + 1]
        packages = [build_plugin_package(Path(__file__).resolve().parents[1], plugin_id, Path("dist/cowork-import"))]
    else:
        packages = build_cowork_import_packages(Path(__file__).resolve().parents[1], Path("dist/cowork-import"))
    for package in packages:
        print(package)
