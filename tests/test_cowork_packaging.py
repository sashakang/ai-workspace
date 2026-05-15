from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_cowork_import import (  # noqa: E402
    build_core_aiws_package,
    build_cowork_import_packages,
    build_productivity_package,
    launcher_check,
    _iter_files,
)


class CoworkPackagingTests(unittest.TestCase):
    def test_builds_all_cowork_import_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package_paths = build_cowork_import_packages(REPO_ROOT, Path(temp))

        self.assertEqual(
            {package.name for package in package_paths},
            {"core-aiws-0.3.10.zip", "aiws-productivity-0.2.1.zip"},
        )

    def test_core_package_includes_mcp_config_launcher_and_server_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package_path = build_core_aiws_package(REPO_ROOT, Path(temp))

            with zipfile.ZipFile(package_path) as package:
                archived_names = package.namelist()
                names = set(archived_names)
                mcp = json.loads(package.read(".mcp.json"))

        self.assertEqual(len(archived_names), len(names))
        server_entries = [name for name in archived_names if name.startswith("servers/aiws-mcp/")]
        self.assertEqual(len(server_entries), len(set(server_entries)))
        self.assertIn(".claude-plugin/plugin.json", names)
        self.assertIn(".mcp.json", names)
        self.assertIn("bin/aiws-mcp-launcher", names)
        self.assertIn("servers/aiws-mcp/pyproject.toml", names)
        self.assertIn("servers/aiws-mcp/aiws_mcp/server.py", names)
        self.assertFalse(any(name.startswith("servers/aiws-mcp/build/") for name in names))
        self.assertFalse(any(name.startswith("servers/aiws-mcp/dist/") for name in names))
        self.assertEqual(mcp["mcpServers"]["aiws"]["command"], "sh")
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-launcher", mcp["mcpServers"]["aiws"]["args"])

    def test_bundled_mcp_server_source_matches_root_source(self) -> None:
        root_server = REPO_ROOT / "aiws-mcp"
        bundled_server = REPO_ROOT / "core-aiws" / "servers" / "aiws-mcp"

        root_files = [source.relative_to(root_server) for source in _iter_files(root_server)]
        bundled_files = [source.relative_to(bundled_server) for source in _iter_files(bundled_server)]

        self.assertEqual(bundled_files, root_files)
        for relative_path in root_files:
            self.assertEqual(
                (bundled_server / relative_path).read_bytes(),
                (root_server / relative_path).read_bytes(),
                str(relative_path),
            )

    def test_productivity_package_is_flat_importable_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package_path = build_productivity_package(REPO_ROOT, Path(temp))

            with zipfile.ZipFile(package_path) as package:
                names = set(package.namelist())

        self.assertIn(".claude-plugin/plugin.json", names)
        self.assertIn("contracts/aiws-productivity.contract.json", names)
        self.assertIn("skills/meeting-followup/SKILL.md", names)
        self.assertNotIn("servers/aiws-mcp/pyproject.toml", names)
        self.assertFalse(any(name.startswith("build/") for name in names))
        self.assertFalse(any(name.startswith("dist/") for name in names))

    def test_launcher_check_reports_missing_uvx_clearly(self) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            result = launcher_check()

        self.assertEqual(result["status"], "missing_uvx")
        self.assertIn("uvx", result["message"])

    def test_packaged_launcher_invokes_bundled_server_source_with_uvx(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            package_path = build_core_aiws_package(REPO_ROOT, temp_path / "dist")
            extracted_root = temp_path / "package"
            fake_bin = temp_path / "bin"
            args_path = temp_path / "uvx-args.json"
            fake_bin.mkdir()

            _extract_package_preserving_modes(package_path, extracted_root)

            fake_uvx = fake_bin / "uvx"
            fake_uvx.write_text(
                f"#!{sys.executable}\n"
                "import json\n"
                "import os\n"
                "import sys\n"
                "with open(os.environ['AIWS_UVX_ARGS_PATH'], 'w', encoding='utf-8') as handle:\n"
                "    json.dump(sys.argv[1:], handle)\n",
                encoding="utf-8",
            )
            fake_uvx.chmod(0o755)

            launcher = extracted_root / "bin" / "aiws-mcp-launcher"
            env = {
                **os.environ,
                "CLAUDE_PLUGIN_ROOT": str(extracted_root),
                "AIWS_UVX_ARGS_PATH": str(args_path),
                "PATH": str(fake_bin),
            }

            result = subprocess.run(
                [str(launcher)],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            actual_args = json.loads(args_path.read_text(encoding="utf-8"))

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            actual_args,
            ["--from", str(extracted_root / "servers" / "aiws-mcp"), "aiws-mcp", "serve"],
        )


def _extract_package_preserving_modes(package_path: Path, output_dir: Path) -> None:
    with zipfile.ZipFile(package_path) as package:
        for member in package.infolist():
            package.extract(member, output_dir)
            mode = member.external_attr >> 16
            if mode:
                (output_dir / member.filename).chmod(mode)


if __name__ == "__main__":
    unittest.main()
