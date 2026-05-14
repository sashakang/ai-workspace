from __future__ import annotations

import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Iterable


SMOKE_PLUGIN_RELATIVE = Path("experiments/cowork-mcp-smoke")
STATIC_PACKAGE_FILES = (
    Path(".claude-plugin/plugin.json"),
    Path(".mcp.json"),
    Path("README.md"),
)
EXECUTABLE_RELATIVE = Path("bin/aiws-mcp-smoke")


def detect_c_compiler() -> str | None:
    candidates: list[str] = []
    cc = os.environ.get("CC")
    if cc:
        candidates.append(cc)
    candidates.extend(["cc", "clang", "gcc"])

    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return None


def compile_smoke_executable(repo_root: Path, output_path: Path, compiler: str | None = None) -> Path:
    repo_root = repo_root.resolve()
    compiler = compiler or detect_c_compiler()
    if compiler is None:
        raise RuntimeError("No C compiler found. Install cc/clang/gcc to build the Cowork MCP smoke executable.")

    source = repo_root / SMOKE_PLUGIN_RELATIVE / "src" / "aiws_mcp_smoke.c"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-O2",
        str(source),
        "-o",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    output_path.chmod(output_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return output_path


def create_package_root(repo_root: Path, package_root: Path, executable_path: Path) -> Path:
    repo_root = repo_root.resolve()
    smoke_root = repo_root / SMOKE_PLUGIN_RELATIVE

    if package_root.exists():
        shutil.rmtree(package_root)
    package_root.mkdir(parents=True)

    for relative_path in STATIC_PACKAGE_FILES:
        target = package_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(smoke_root / relative_path, target)

    executable_target = package_root / EXECUTABLE_RELATIVE
    executable_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable_path, executable_target)
    executable_target.chmod(executable_target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return package_root


def build_smoke_package(repo_root: Path, output_dir: Path, compiler: str | None = None) -> Path:
    repo_root = repo_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    smoke_root = repo_root / SMOKE_PLUGIN_RELATIVE
    manifest = json.loads((smoke_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    package_path = output_dir / f"{manifest['name']}-{manifest['version']}-{platform.system().lower()}-{platform.machine().lower()}.zip"

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        executable_path = compile_smoke_executable(repo_root, temp_path / EXECUTABLE_RELATIVE, compiler=compiler)
        package_root = create_package_root(repo_root, temp_path / "package", executable_path)
        write_zip(package_root, package_path)

    return package_path


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
    mode = source.stat().st_mode
    if mode & stat.S_IXUSR:
        info.external_attr = 0o755 << 16
    else:
        info.external_attr = 0o644 << 16
    package.writestr(info, source.read_bytes())


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if argv:
        print("usage: python -m scripts.build_cowork_mcp_smoke", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[1]
    package_path = build_smoke_package(repo_root, repo_root / "dist" / "cowork-smoke")
    print(package_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
