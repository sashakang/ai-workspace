from __future__ import annotations

import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SMOKE_PLUGIN_RELATIVE = Path("experiments/cowork-http-mcp-smoke")
VARIANTS_RELATIVE = SMOKE_PLUGIN_RELATIVE / "variants"
OUTPUT_RELATIVE = Path("dist/cowork-http-smoke")
STATIC_PACKAGE_FILES = (
    Path(".claude-plugin/plugin.json"),
    Path(".mcp.json"),
    Path("README.md"),
)
STATIC_PACKAGE_DIRS = (Path("skills"),)
ENDPOINT_URL = "https://code.claude.com/docs/mcp"


@dataclass(frozen=True)
class SmokeVariant:
    key: str
    source_relative: Path
    plugin_name: str
    server_name: str


VARIANTS = (
    SmokeVariant(
        key="claude-documented-shape",
        source_relative=VARIANTS_RELATIVE / "claude-documented-shape",
        plugin_name="aiws-cowork-http-mcp-smoke-claude-shape",
        server_name="aiws-cowork-http-smoke-claude-docs",
    ),
    SmokeVariant(
        key="cowork-array-hypothesis",
        source_relative=VARIANTS_RELATIVE / "cowork-array-hypothesis",
        plugin_name="aiws-cowork-http-mcp-smoke-cowork-array",
        server_name="aiws-cowork-http-smoke-cowork-array-docs",
    ),
)


def create_package_root(repo_root: Path, variant: SmokeVariant, package_root: Path) -> Path:
    repo_root = repo_root.resolve()
    source_root = repo_root / variant.source_relative

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    for relative_path in STATIC_PACKAGE_FILES:
        target = package_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_root / relative_path, target)

    for relative_dir in STATIC_PACKAGE_DIRS:
        source_dir = source_root / relative_dir
        if source_dir.exists():
            shutil.copytree(source_dir, package_root / relative_dir)

    return package_root


def build_http_smoke_packages(repo_root: Path, output_dir: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_paths: list[Path] = []

    for variant in VARIANTS:
        source_root = repo_root / variant.source_relative
        manifest = json.loads((source_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        package_path = output_dir / f"{manifest['name']}-{manifest['version']}.zip"
        package_root = output_dir / ".build" / variant.key
        create_package_root(repo_root, variant, package_root)
        write_zip(package_root, package_path)
        shutil.rmtree(package_root)
        package_paths.append(package_path)

    build_root = output_dir / ".build"
    if build_root.exists():
        shutil.rmtree(build_root)

    return package_paths


def write_zip(package_root: Path, package_path: Path) -> None:
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        for source in iter_package_files(package_root):
            write_file(package, source, source.relative_to(package_root))


def iter_package_files(package_root: Path) -> Iterable[Path]:
    for path in sorted(package_root.rglob("*")):
        if path.is_file():
            yield path


def write_file(package: zipfile.ZipFile, source: Path, archive_name: Path) -> None:
    info = zipfile.ZipInfo(str(archive_name))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    package.writestr(info, source.read_bytes())


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if argv:
        print("usage: python -m scripts.build_cowork_http_mcp_smoke", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    package_paths = build_http_smoke_packages(repo_root, repo_root / OUTPUT_RELATIVE)
    for package_path in package_paths:
        print(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
