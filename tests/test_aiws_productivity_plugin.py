from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


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

        self.assertEqual(plugin_json["version"], contract["version"])
        self.assertEqual(plugin_json["version"], marketplace_entry["version"])

    def test_meeting_followup_belongs_to_aiws_productivity_not_core(self) -> None:
        productivity_contract = json.loads(
            (REPO_ROOT / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json").read_text()
        )
        core_contract = json.loads((REPO_ROOT / "core-aiws" / "contracts" / "core-aiws.contract.json").read_text())

        self.assertEqual(productivity_contract["plugin_id"], "aiws-productivity")
        self.assertIn("meeting-followup", productivity_contract["public_skills"])
        self.assertNotIn("meeting-followup", core_contract["public_skills"])
        self.assertIn("aiws-improve", core_contract["public_skills"])
        self.assertIn("aiws-install-drive-skill-library", core_contract["public_skills"])
        self.assertIn("aiws-propose-skill-update", core_contract["public_skills"])
        self.assertIn("aiws-refresh-skill-library", core_contract["public_skills"])
        self.assertIn("aiws-update-skill-library", core_contract["public_skills"])
        self.assertIn("aiws-validate-skill-library", core_contract["public_skills"])

    def test_meeting_followup_scope_excludes_broad_productivity(self) -> None:
        content = (REPO_ROOT / "aiws-productivity" / "skills" / "meeting-followup" / "SKILL.md").read_text()

        self.assertIn("meeting transcript", content.lower())
        self.assertIn("decisions", content.lower())
        self.assertIn("action items", content.lower())
        self.assertIn("do not create task dashboards", content.lower())
        self.assertIn("perform daily planning", content.lower())
        self.assertIn("do not sync tasks", content.lower())

    def test_aiws_productivity_does_not_register_slack_mcp_server(self) -> None:
        self.assertFalse(
            (REPO_ROOT / "aiws-productivity" / ".mcp.json").exists(),
            "aiws-productivity must not register a Slack MCP server. Install the dedicated Slack plugin instead.",
        )

    def test_aiws_productivity_declares_optional_slack_connector(self) -> None:
        contract = json.loads(
            (REPO_ROOT / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json").read_text()
        )

        # Contract documentation block (informational; not consumed by the loader).
        slack = next(conn for conn in contract["connectors"] if conn["id"] == "slack")
        self.assertEqual(slack["kind"], "optional-external-plugin")
        self.assertFalse(slack["required"])
        self.assertIn("messages.read", slack["capabilities"])
        self.assertIn("messages.write", slack["capabilities"])
        self.assertIn("messages.schedule", slack["capabilities"])
        self.assertNotIn(".mcp.json", contract["improve_targets"])

    def test_meeting_followup_requires_explicit_approval_for_slack_writes(self) -> None:
        content = (REPO_ROOT / "aiws-productivity" / "skills" / "meeting-followup" / "SKILL.md").read_text()

        self.assertIn("**Slack**", content)
        self.assertIn("Do not send or schedule Slack messages without explicit approval.", content)


if __name__ == "__main__":
    unittest.main()
