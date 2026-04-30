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


if __name__ == "__main__":
    unittest.main()
