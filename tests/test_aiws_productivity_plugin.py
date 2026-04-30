from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SLACK_MCP_URL = "https://mcp.slack.com/mcp"


class AiwsProductivityPluginTests(unittest.TestCase):
    def test_marketplace_lists_aiws_productivity_demo_plugin(self) -> None:
        marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())
        plugins = {item["name"]: item for item in marketplace["plugins"]}

        self.assertIn("aiws-productivity", plugins)
        self.assertEqual(plugins["aiws-productivity"]["source"], "./aiws-productivity")

    def test_aiws_productivity_marketplace_version_matches_plugin(self) -> None:
        marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())
        plugin_json = json.loads(
            (REPO_ROOT / "aiws-productivity" / ".claude-plugin" / "plugin.json").read_text()
        )
        contract = json.loads(
            (REPO_ROOT / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json").read_text()
        )
        marketplace_entry = next(
            entry for entry in marketplace["plugins"] if entry["name"] == "aiws-productivity"
        )

        self.assertEqual(plugin_json["version"], "0.2.0")
        self.assertEqual(contract["version"], "0.2.0")
        self.assertEqual(marketplace_entry["version"], "0.2.0")

    def test_meeting_followup_belongs_to_aiws_productivity_not_core(self) -> None:
        productivity_contract = json.loads(
            (REPO_ROOT / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json").read_text()
        )
        core_contract = json.loads((REPO_ROOT / "core-aiws" / "contracts" / "core-aiws.contract.json").read_text())

        self.assertEqual(productivity_contract["plugin_id"], "aiws-productivity")
        self.assertIn("meeting-followup", productivity_contract["public_skills"])
        self.assertNotIn("meeting-followup", core_contract["public_skills"])
        self.assertIn("aiws-improve", core_contract["public_skills"])

    def test_meeting_followup_scope_excludes_broad_productivity(self) -> None:
        content = (REPO_ROOT / "aiws-productivity" / "skills" / "meeting-followup" / "SKILL.md").read_text()

        self.assertIn("meeting transcript", content.lower())
        self.assertIn("decisions", content.lower())
        self.assertIn("action items", content.lower())
        self.assertIn("do not create task dashboards", content.lower())
        self.assertIn("do not perform daily planning", content.lower())
        self.assertIn("do not sync tasks", content.lower())

    def test_mcp_config_uses_real_claude_code_schema(self) -> None:
        """Fail on the old fabricated top-level 'servers' schema; pass only with 'mcpServers'."""
        mcp_config = json.loads(
            (REPO_ROOT / "aiws-productivity" / ".mcp.json").read_text()
        )

        self.assertNotIn(
            "servers",
            mcp_config,
            "aiws-productivity/.mcp.json must use the real Claude Code key 'mcpServers' "
            "(not the fabricated top-level 'servers'). Plugin loaders ignore the old shape.",
        )
        self.assertIn("mcpServers", mcp_config)

    def test_aiws_productivity_declares_optional_slack_connector(self) -> None:
        contract = json.loads(
            (REPO_ROOT / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json").read_text()
        )
        mcp_config = json.loads(
            (REPO_ROOT / "aiws-productivity" / ".mcp.json").read_text()
        )

        # Contract documentation block (informational; not consumed by the loader).
        slack = next(conn for conn in contract["connectors"] if conn["id"] == "slack")
        self.assertEqual(slack["kind"], "host-managed-mcp")
        self.assertFalse(slack["required"])
        self.assertIn("messages.read", slack["capabilities"])
        self.assertIn("messages.write", slack["capabilities"])
        self.assertIn("messages.schedule", slack["capabilities"])
        self.assertIn(".mcp.json", contract["improve_targets"])

        # The actual loader-facing shape: mcpServers + http + canonical Slack URL.
        self.assertIn("mcpServers", mcp_config)
        self.assertIn("slack", mcp_config["mcpServers"])
        slack_server = mcp_config["mcpServers"]["slack"]
        self.assertEqual(slack_server["type"], "http")
        self.assertEqual(slack_server["url"], SLACK_MCP_URL)

    def test_meeting_followup_requires_explicit_approval_for_slack_writes(self) -> None:
        content = (REPO_ROOT / "aiws-productivity" / "skills" / "meeting-followup" / "SKILL.md").read_text()

        self.assertIn("optional Slack connector", content)
        self.assertIn("Do not send or schedule Slack messages without explicit approval.", content)


if __name__ == "__main__":
    unittest.main()
