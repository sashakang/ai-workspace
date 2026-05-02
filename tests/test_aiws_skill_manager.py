from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp.skill_manager import (  # noqa: E402
    SkillManagerError,
    create_draft_record,
    draft_id,
    load_draft_record,
    update_from_github_decision,
    validate_marketplace,
    validate_plugin,
    validate_mcp_config,
    validate_skill_creator_compat,
)


class AiwsSkillManagerTests(unittest.TestCase):
    def test_release_gate_validates_current_marketplace(self) -> None:
        result = validate_marketplace(REPO_ROOT)
        plugin_names = {plugin["name"] for plugin in result["plugins"]}

        self.assertIn("core-aiws", plugin_names)
        self.assertIn("aiws-productivity", plugin_names)

    def test_mcp_config_rejects_top_level_servers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(json.dumps({"servers": {"slack": {"type": "http", "url": "https://mcp.slack.com/mcp"}}}))

            with self.assertRaisesRegex(SkillManagerError, "mcpServers"):
                validate_mcp_config(path)

    def test_mcp_config_accepts_http_mcp_servers_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps({"mcpServers": {"slack": {"type": "http", "url": "https://mcp.slack.com/mcp"}}})
            )

            result = validate_mcp_config(path)

        self.assertIn("slack", result["mcpServers"])

    def test_mcp_config_rejects_inline_secret_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "slack": {
                                "type": "stdio",
                                "command": "slack-mcp",
                                "env": {"SLACK_BOT_TOKEN": "redacted"},
                            }
                        }
                    }
                )
            )

            with self.assertRaisesRegex(SkillManagerError, "secret-like"):
                validate_mcp_config(path)

    def test_mcp_config_rejects_secret_in_http_url_query(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps({"mcpServers": {"remote": {"type": "http", "url": "https://example.com/mcp?token=abc"}}})
            )

            with self.assertRaisesRegex(SkillManagerError, "secret-like"):
                validate_mcp_config(path)

    def test_mcp_config_rejects_secret_in_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "remote": {
                                "type": "http",
                                "url": "https://example.com/mcp",
                                "headers": {"Authorization": "Bearer abc"},
                            }
                        }
                    }
                )
            )

            with self.assertRaisesRegex(SkillManagerError, "secret-like"):
                validate_mcp_config(path)

    def test_mcp_config_rejects_authorization_header_with_basic_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "remote": {
                                "type": "http",
                                "url": "https://example.com/mcp",
                                "headers": {"Authorization": "Basic abc123"},
                            }
                        }
                    }
                )
            )

            with self.assertRaisesRegex(SkillManagerError, "secret-like"):
                validate_mcp_config(path)

    def test_mcp_config_rejects_auth_url_query_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / ".mcp.json"
            path.write_text(
                json.dumps({"mcpServers": {"remote": {"type": "http", "url": "https://example.com/mcp?auth=abc123"}}})
            )

            with self.assertRaisesRegex(SkillManagerError, "secret-like"):
                validate_mcp_config(path)

    def test_skill_creator_compat_rejects_extra_frontmatter_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_root = Path(temp) / "meeting-followup"
            skill_root.mkdir()
            (skill_root / "SKILL.md").write_text(
                "---\n"
                "name: meeting-followup\n"
                "description: Test skill.\n"
                "metadata: extra\n"
                "---\n"
                "\n"
                "# Meeting Follow-Up\n"
            )

            with self.assertRaisesRegex(SkillManagerError, "Unsupported SKILL.md frontmatter"):
                validate_skill_creator_compat(skill_root)

    def test_skill_creator_compat_rejects_clutter_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill_root = Path(temp) / "meeting-followup"
            skill_root.mkdir()
            (skill_root / "SKILL.md").write_text(
                "---\nname: meeting-followup\ndescription: Test skill.\n---\n\n# Meeting Follow-Up\n"
            )
            (skill_root / "README.md").write_text("Do not keep this inside a skill folder.\n")

            with self.assertRaisesRegex(SkillManagerError, "Unsupported clutter files"):
                validate_skill_creator_compat(skill_root)

    def test_plugin_validation_rejects_skill_directory_without_skill_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.write_plugin(Path(temp), public_skills=[])
            (plugin_root / "skills" / "broken-skill").mkdir(parents=True)

            with self.assertRaisesRegex(SkillManagerError, "Missing SKILL.md"):
                validate_plugin(plugin_root)

    def test_plugin_validation_rejects_public_skill_without_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.write_plugin(Path(temp), public_skills=["missing-skill"])

            with self.assertRaisesRegex(SkillManagerError, "public_skills missing"):
                validate_plugin(plugin_root)

    def test_plugin_validation_rejects_invalid_inline_mcp_servers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = self.write_plugin(Path(temp), public_skills=[])
            manifest = json.loads((plugin_root / ".claude-plugin" / "plugin.json").read_text())
            manifest["mcpServers"] = {"slack": {"type": "http"}}
            (plugin_root / ".claude-plugin" / "plugin.json").write_text(json.dumps(manifest))

            with self.assertRaisesRegex(SkillManagerError, "must define url"):
                validate_plugin(plugin_root)

    def test_skill_management_docs_keep_memory_and_terminal_out_of_user_flow(self) -> None:
        contract = (REPO_ROOT / "core-aiws" / "contracts" / "skill-management.md").read_text()
        protocol = (REPO_ROOT / "core-aiws" / "protocols" / "skill-management.md").read_text()

        self.assertIn("must not run memory import or export flows", contract)
        self.assertIn("must not touch memory paths", contract)
        self.assertIn("Do not ask normal users to run bash commands", protocol)
        self.assertNotIn("pipx install", protocol)
        self.assertNotIn("aiws-host-memory", protocol)

    def test_draft_registry_records_origin_and_fails_closed_on_modified_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / ".aiws"
            record = create_draft_record(
                root,
                plugin_id="aiws-productivity",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/sashakang/ai-workspace",
                origin_ref="master",
                base_version="0.1.0",
                base_commit="18428d0",
            )
            record_id = draft_id("aiws-productivity", "meeting-followup", "https://github.com/sashakang/ai-workspace")
            loaded = load_draft_record(root, record_id)

            self.assertEqual(loaded.plugin_id, "aiws-productivity")
            self.assertEqual(loaded.skill_id, "meeting-followup")
            self.assertIn(".aiws/plugins/ai-workspace/aiws-productivity-", loaded.draft_path)
            self.assertTrue(record.active)
            self.assertTrue(update_from_github_decision(record)["allowed"])

            modified = type(record)(**{**record.to_json(), "modified": True})
            decision = update_from_github_decision(modified)

        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "active_modified_draft")
        self.assertEqual(
            decision["choices"],
            ["keep_local_modified_skill_active", "discard_local_changes_and_update", "submit_or_upload_first"],
        )

    def write_plugin(self, root: Path, *, public_skills: list[str]) -> Path:
        plugin_root = root / "example-plugin"
        (plugin_root / ".claude-plugin").mkdir(parents=True)
        (plugin_root / "contracts").mkdir()
        (plugin_root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "example-plugin", "description": "Example plugin.", "version": "1.0.0"})
        )
        (plugin_root / "contracts" / "example-plugin.contract.json").write_text(
            json.dumps(
                {
                    "plugin_id": "example-plugin",
                    "version": "1.0.0",
                    "public_skills": public_skills,
                    "public_agents": [],
                    "dependencies": [],
                    "project_memory_read_scope": [],
                    "project_memory_write_scope": [],
                    "shared_memory_read_scope": [],
                    "shared_memory_write_scope": [],
                    "improve_targets": [],
                }
            )
        )
        return plugin_root


if __name__ == "__main__":
    unittest.main()
