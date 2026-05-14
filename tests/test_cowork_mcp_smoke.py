from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_cowork_mcp_smoke import (  # noqa: E402
    EXECUTABLE_RELATIVE,
    SMOKE_PLUGIN_RELATIVE,
    STATIC_PACKAGE_FILES,
    build_smoke_package,
    create_package_root,
    detect_c_compiler,
    write_zip,
)


class CoworkMcpSmokeTests(unittest.TestCase):
    def test_mcp_config_points_directly_to_bundled_executable(self) -> None:
        mcp_path = REPO_ROOT / SMOKE_PLUGIN_RELATIVE / ".mcp.json"
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        server = mcp["mcpServers"]["aiws-cowork-mcp-smoke"]

        self.assertEqual(server["command"], "${CLAUDE_PLUGIN_ROOT}/bin/aiws-mcp-smoke")
        self.assertEqual(server["args"], [])

        forbidden = ("sh", "python", "python3", "uv", "uvx", "gh", "git")
        command_parts = [server["command"], *server["args"]]
        self.assertFalse(
            any(Path(part).name in forbidden for part in command_parts),
            command_parts,
        )

    def test_static_package_shape_is_testable_without_compiler(self) -> None:
        smoke_root = REPO_ROOT / SMOKE_PLUGIN_RELATIVE

        for relative_path in STATIC_PACKAGE_FILES:
            self.assertTrue((smoke_root / relative_path).is_file(), str(relative_path))

        manifest = json.loads((smoke_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "aiws-cowork-mcp-smoke")
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertTrue((smoke_root / "src" / "aiws_mcp_smoke.c").is_file())

    def test_package_root_and_zip_preserve_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake_executable = temp_path / "fake-aiws-mcp-smoke"
            fake_executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake_executable.chmod(0o755)

            package_root = create_package_root(REPO_ROOT, temp_path / "package", fake_executable)
            package_path = temp_path / "smoke.zip"
            write_zip(package_root, package_path)

            with zipfile.ZipFile(package_path) as package:
                names = set(package.namelist())
                mode = package.getinfo(str(EXECUTABLE_RELATIVE)).external_attr >> 16

        self.assertEqual(
            names,
            {
                ".claude-plugin/plugin.json",
                ".mcp.json",
                "README.md",
                str(EXECUTABLE_RELATIVE),
            },
        )
        self.assertEqual(mode, 0o755)

    @unittest.skipIf(detect_c_compiler() is None, "No C compiler available for smoke binary build")
    def test_build_package_and_binary_self_test_when_compiler_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            package_path = build_smoke_package(REPO_ROOT, temp_path / "dist")
            extracted_root = temp_path / "extracted"
            _extract_package_preserving_modes(package_path, extracted_root)
            executable = extracted_root / EXECUTABLE_RELATIVE

            result = subprocess.run(
                [str(executable), "--self-test"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "aiws-cowork-mcp-smoke self-test ok")

    @unittest.skipIf(detect_c_compiler() is None, "No C compiler available for smoke binary build")
    def test_smoke_binary_handles_minimal_mcp_stdio_flow_when_compiler_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            package_path = build_smoke_package(REPO_ROOT, temp_path / "dist")
            extracted_root = temp_path / "extracted"
            _extract_package_preserving_modes(package_path, extracted_root)
            executable = extracted_root / EXECUTABLE_RELATIVE

            input_text = "\n".join(
                [
                    '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
                    '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}',
                    '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
                    '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"aiws.smoke.ping","arguments":{}}}',
                    "",
                ]
            )
            result = subprocess.run(
                [str(executable)],
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            responses = [json.loads(line) for line in result.stdout.splitlines()]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([response["id"] for response in responses], [1, 2, 3])
        self.assertEqual(responses[1]["result"]["tools"][0]["name"], "aiws.smoke.ping")
        self.assertEqual(
            responses[2]["result"]["content"][0]["text"],
            "aiws-cowork-mcp-smoke pong",
        )

    @unittest.skipIf(detect_c_compiler() is None, "No C compiler available for smoke binary build")
    def test_smoke_binary_preserves_string_json_rpc_ids_when_compiler_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            package_path = build_smoke_package(REPO_ROOT, temp_path / "dist")
            extracted_root = temp_path / "extracted"
            _extract_package_preserving_modes(package_path, extracted_root)
            executable = extracted_root / EXECUTABLE_RELATIVE

            input_text = "\n".join(
                [
                    '{"jsonrpc":"2.0","id":"init-1","method":"initialize","params":{}}',
                    '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}',
                    '{"jsonrpc":"2.0","id":"list-2","method":"tools/list","params":{}}',
                    '{"jsonrpc":"2.0","id":"call-3","method":"tools/call","params":{"name":"aiws.smoke.ping","arguments":{}}}',
                    "",
                ]
            )
            result = subprocess.run(
                [str(executable)],
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            responses = [json.loads(line) for line in result.stdout.splitlines()]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([response["id"] for response in responses], ["init-1", "list-2", "call-3"])
        self.assertEqual(
            responses[2]["result"]["content"][0]["text"],
            "aiws-cowork-mcp-smoke pong",
        )

    @unittest.skipIf(detect_c_compiler() is None, "No C compiler available for smoke binary build")
    def test_smoke_binary_accepts_tool_name_with_json_whitespace_when_compiler_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            package_path = build_smoke_package(REPO_ROOT, temp_path / "dist")
            extracted_root = temp_path / "extracted"
            _extract_package_preserving_modes(package_path, extracted_root)
            executable = extracted_root / EXECUTABLE_RELATIVE

            input_text = '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name" : "aiws.smoke.ping","arguments":{}}}\n'
            result = subprocess.run(
                [str(executable)],
                input=input_text,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            response = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(response["id"], 1)
        self.assertFalse(response["result"]["isError"])
        self.assertEqual(
            response["result"]["content"][0]["text"],
            "aiws-cowork-mcp-smoke pong",
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
