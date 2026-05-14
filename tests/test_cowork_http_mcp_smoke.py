from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_cowork_http_mcp_smoke import (  # noqa: E402
    ENDPOINT_URL,
    SMOKE_PLUGIN_RELATIVE,
    STATIC_PACKAGE_DIRS,
    STATIC_PACKAGE_FILES,
    VARIANTS,
    build_http_smoke_packages,
    create_package_root,
    write_zip,
)


FORBIDDEN_RUNTIME_KEYS = {"command", "args", "env", "headers"}
FORBIDDEN_RUNTIME_VALUES = {"sh", "bash", "zsh", "python", "python3", "uv", "uvx", "gh", "git"}
EXPECTED_ZIP_NAMES = {
    "aiws-cowork-http-mcp-smoke-claude-shape-0.1.0.zip",
    "aiws-cowork-http-mcp-smoke-cowork-array-0.1.0.zip",
}


class CoworkHttpMcpSmokeTests(unittest.TestCase):
    def test_static_variant_layout_and_identifiers_are_distinct(self) -> None:
        plugin_names: set[str] = set()
        server_names: set[str] = set()

        for variant in VARIANTS:
            source_root = REPO_ROOT / variant.source_relative
            for relative_path in STATIC_PACKAGE_FILES:
                self.assertTrue((source_root / relative_path).is_file(), f"{variant.key}: {relative_path}")
            for relative_dir in STATIC_PACKAGE_DIRS:
                self.assertTrue((source_root / relative_dir).is_dir(), f"{variant.key}: {relative_dir}")

            manifest = json.loads((source_root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
            mcp = json.loads((source_root / ".mcp.json").read_text(encoding="utf-8"))
            names = _server_names(mcp)

            self.assertEqual(manifest["name"], variant.plugin_name)
            self.assertEqual(names, {variant.server_name})
            plugin_names.add(manifest["name"])
            server_names.update(names)

        self.assertEqual(len(plugin_names), len(VARIANTS))
        self.assertEqual(len(server_names), len(VARIANTS))

    def test_mcp_configs_use_exact_endpoint_and_no_stdio_runtime_fields(self) -> None:
        for variant in VARIANTS:
            mcp_path = REPO_ROOT / variant.source_relative / ".mcp.json"
            mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
            self.assertIn(ENDPOINT_URL, _all_string_values(mcp), variant.key)
            self.assertEqual(_endpoint_urls(mcp), {ENDPOINT_URL})
            self.assertFalse(_contains_forbidden_key(mcp), variant.key)
            self.assertFalse(_contains_forbidden_runtime_value(mcp), variant.key)

    def test_variant_shapes_match_gate_one_proof(self) -> None:
        claude_mcp = json.loads(
            (REPO_ROOT / SMOKE_PLUGIN_RELATIVE / "variants" / "claude-documented-shape" / ".mcp.json").read_text(
                encoding="utf-8"
            )
        )
        claude_servers = claude_mcp["mcpServers"]
        self.assertIsInstance(claude_servers, dict)
        self.assertEqual(
            claude_servers["aiws-cowork-http-smoke-claude-docs"],
            {"type": "http", "url": ENDPOINT_URL},
        )

        cowork_mcp = json.loads(
            (REPO_ROOT / SMOKE_PLUGIN_RELATIVE / "variants" / "cowork-array-hypothesis" / ".mcp.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIsInstance(cowork_mcp, list)
        self.assertEqual(
            cowork_mcp,
            [
                {
                    "name": "aiws-cowork-http-smoke-cowork-array-docs",
                    "url": ENDPOINT_URL,
                    "transport": "http",
                }
            ],
        )

    def test_skills_are_packaged_and_point_to_claude_docs_tools(self) -> None:
        for variant in VARIANTS:
            skill_path = REPO_ROOT / variant.source_relative / "skills" / "smoke-check" / "SKILL.md"
            skill_text = skill_path.read_text(encoding="utf-8")

            self.assertTrue(skill_text.startswith("---\n"), variant.key)
            self.assertIn("name: smoke-check", skill_text)
            self.assertIn(variant.server_name, skill_text)
            self.assertIn("Claude docs", skill_text)
            self.assertIn("search/read", skill_text)
            self.assertIn("remote HTTP MCP registration only", skill_text)
            self.assertIn("not test AIWS production runtime readiness", skill_text)
            self.assertIn("aiws.smoke.ping", skill_text)
            self.assertIn("Do not look for or call `aiws.smoke.ping`", skill_text)

    def test_package_root_and_zip_contain_only_static_upload_files(self) -> None:
        expected_names = {
            ".claude-plugin/plugin.json",
            ".mcp.json",
            "README.md",
            "skills/smoke-check/SKILL.md",
        }

        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            for variant in VARIANTS:
                package_root = create_package_root(REPO_ROOT, variant, temp_path / variant.key / "package")
                package_path = temp_path / f"{variant.key}.zip"
                write_zip(package_root, package_path)

                with zipfile.ZipFile(package_path) as package:
                    names = set(package.namelist())
                    modes = {name: package.getinfo(name).external_attr >> 16 for name in names}
                    manifest = json.loads(package.read(".claude-plugin/plugin.json"))
                    mcp = json.loads(package.read(".mcp.json"))

                self.assertEqual(names, expected_names)
                self.assertTrue(all(mode == 0o644 for mode in modes.values()), modes)
                self.assertEqual(manifest["name"], variant.plugin_name)
                self.assertEqual(_server_names(mcp), {variant.server_name})
                self.assertFalse(any(name.startswith(("bin/", "src/")) for name in names))

    def test_builds_both_zip_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package_paths = build_http_smoke_packages(REPO_ROOT, Path(temp))

            self.assertEqual({path.name for path in package_paths}, EXPECTED_ZIP_NAMES)
            for package_path in package_paths:
                with zipfile.ZipFile(package_path) as package:
                    names = set(package.namelist())
                self.assertIn("skills/smoke-check/SKILL.md", names)
                self.assertNotIn("bin/aiws-mcp-smoke", names)
                self.assertFalse(any(name.startswith(("bin/", "src/")) for name in names))

    def test_docs_capture_prompts_and_acceptance_conditions(self) -> None:
        experiment_readme = (REPO_ROOT / SMOKE_PLUGIN_RELATIVE / "README.md").read_text(encoding="utf-8")
        phase_plan = (REPO_ROOT / "docs" / "aiws-cowork-phase2b-runtime-plan.md").read_text(encoding="utf-8")

        for variant in VARIANTS:
            self.assertIn(variant.plugin_name, experiment_readme)
            self.assertIn(variant.server_name, experiment_readme)
            self.assertIn("Cowork test prompt:", experiment_readme)
            self.assertIn("Acceptance condition:", experiment_readme)

        self.assertIn("Use the aiws-cowork-http-mcp-smoke-claude-shape smoke-check skill.", experiment_readme)
        self.assertIn("Use the aiws-cowork-http-mcp-smoke-cowork-array smoke-check skill.", experiment_readme)
        self.assertIn("remote HTTP MCP registration through uploaded plugins", phase_plan)
        self.assertIn("executable packaging is no longer the primary next slice", phase_plan)
        self.assertIn("Claude docs MCP search/read tools", phase_plan)


def _server_names(value: Any) -> set[str]:
    if isinstance(value, list):
        return {server["name"] for server in value}

    servers = value["mcpServers"]
    if isinstance(servers, dict):
        return set(servers)
    return {server["name"] for server in servers}


def _endpoint_urls(value: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "url" and isinstance(nested, str):
                urls.add(nested)
            urls.update(_endpoint_urls(nested))
    elif isinstance(value, list):
        for nested in value:
            urls.update(_endpoint_urls(nested))
    return urls


def _all_string_values(value: Any) -> set[str]:
    strings: set[str] = set()
    if isinstance(value, dict):
        for nested in value.values():
            strings.update(_all_string_values(nested))
    elif isinstance(value, list):
        for nested in value:
            strings.update(_all_string_values(nested))
    elif isinstance(value, str):
        strings.add(value)
    return strings


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in FORBIDDEN_RUNTIME_KEYS or _contains_forbidden_key(nested) for key, nested in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(nested) for nested in value)
    return False


def _contains_forbidden_runtime_value(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_forbidden_runtime_value(nested) for nested in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_runtime_value(nested) for nested in value)
    if isinstance(value, str):
        return Path(value).name in FORBIDDEN_RUNTIME_VALUES
    return False


if __name__ == "__main__":
    unittest.main()
