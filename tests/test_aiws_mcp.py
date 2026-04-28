from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp.runtime import AiwsRuntime, SkillValidationError  # noqa: E402


class AiwsMcpSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / ".aiws"
        self.claude_home = Path(self.tempdir.name) / ".claude"
        self.codex_home = Path(self.tempdir.name) / ".codex"
        self.env = {
            "CLAUDE_HOME": str(self.claude_home),
            "CODEX_HOME": str(self.codex_home),
        }
        self.runtime = AiwsRuntime(root=self.root, env=self.env)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_personal_skill(self, skill_id: str, description: str = "A local test skill.") -> Path:
        skill_root = self.root / "personal" / "skills" / skill_id
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: {description}\n---\n\n# {skill_id}\n\nUse this skill.\n"
        )
        return skill_root

    def test_clean_machine_has_sop_and_aiws_improve_without_plugins(self) -> None:
        local = self.runtime.list_local_skills()
        skill_ids = {item["skill_id"] for item in local["skills"]}

        self.assertIn("aiws-improve", skill_ids)
        self.assertIn("meeting-followup", skill_ids)
        sop = self.runtime.get_resource("aiws://protocols/sop")
        improve = self.runtime.get_resource("aiws://skills/aiws-improve")

        self.assertIn("Standard Operating Procedure", sop)
        self.assertIn("Self-Improvement", improve)
        self.assertNotIn("CLAUDE_PLUGIN_DATA", improve)
        self.assertNotIn("registry/plugins", improve)

    def test_validator_rejects_invalid_skill_frontmatter(self) -> None:
        skill_root = self.root / "personal" / "skills" / "Bad_Name"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text("---\nname: Bad_Name\ndescription: x\n---\n")

        with self.assertRaises(SkillValidationError):
            self.runtime.list_local_skills()

    def test_host_identity_is_persisted_and_conflicts_fail_closed(self) -> None:
        host = self.runtime.ensure_host(host_kind="claude-code")

        self.assertTrue(host.host_id.startswith("claude-code-"))
        host_json = self.root / "hosts" / host.host_id / "host.json"
        self.assertTrue(host_json.exists())
        payload = json.loads(host_json.read_text())
        self.assertEqual(payload["host_kind"], "claude-code")
        self.assertEqual(payload["config_root"], str(self.claude_home.resolve()))

        loaded = self.runtime.ensure_host(host_id=host.host_id)
        self.assertEqual(loaded.host_kind, "claude-code")

        with self.assertRaises(ValueError):
            self.runtime.ensure_host(host_id=host.host_id, host_kind="codex")

        with self.assertRaises(ValueError):
            self.runtime.ensure_host(host_id="missing-host")

    def test_materialize_generates_claude_adapter_and_integrity(self) -> None:
        self.write_personal_skill("local-review", "Review local work.")

        result = self.runtime.materialize_skill(
            skill_id="local-review",
            host_kind="claude-code",
        )

        self.assertEqual(result["status"], "materialized")
        self.assertTrue(result["integrity_hash"].startswith("sha256:"))
        cache_path = Path(result["cache_path"])
        adapter_path = Path(result["adapter_path"])
        self.assertTrue(cache_path.is_relative_to(self.runtime.root))
        self.assertTrue(adapter_path.is_relative_to(self.runtime.root))
        self.assertTrue((adapter_path / ".claude" / "skills" / "local-review" / "SKILL.md").exists())
        self.assertFalse((self.claude_home / "skills" / "local-review" / "SKILL.md").exists())

    def test_materialize_rejects_symlinks_and_path_escape(self) -> None:
        skill_root = self.write_personal_skill("unsafe-skill")
        (skill_root / "refs").mkdir()
        os.symlink("/tmp", skill_root / "refs" / "escape")

        with self.assertRaises(ValueError):
            self.runtime.materialize_skill(skill_id="unsafe-skill", host_kind="claude-code")

    def test_duplicate_shared_skill_ids_fail_closed_unless_pinned(self) -> None:
        fixtures = self.root / "fixtures" / "remote-skills"
        fixtures.mkdir(parents=True)
        (fixtures / "unit.json").write_text(
            json.dumps(
                {
                    "skill_id": "shared-review",
                    "name": "shared-review",
                    "description": "Unit review skill.",
                    "scope": "unit:analytics",
                    "version": "1.0.0",
                    "supported_hosts": ["claude-code"],
                }
            )
        )
        (fixtures / "company.json").write_text(
            json.dumps(
                {
                    "skill_id": "shared-review",
                    "name": "shared-review",
                    "description": "Company review skill.",
                    "scope": "company",
                    "version": "1.0.0",
                    "supported_hosts": ["claude-code"],
                }
            )
        )

        ambiguous = self.runtime.resolve_skill("shared-review")
        self.assertEqual(ambiguous["status"], "ambiguous")
        self.assertEqual(len(ambiguous["candidates"]), 2)

        resolved = self.runtime.resolve_skill("shared-review", scope="company")
        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["manifest"]["scope"], "company")

    def test_cowork_and_codex_adapters_are_generated_under_aiws_only(self) -> None:
        self.write_personal_skill("local-review", "Review local work.")

        cowork = self.runtime.materialize_skill(skill_id="local-review", host_kind="cowork")
        cowork_adapter = Path(cowork["adapter_path"])
        self.assertTrue((cowork_adapter / "aiws-generated-plugin" / ".claude-plugin" / "plugin.json").exists())
        self.assertTrue((cowork_adapter / "aiws-generated-plugin" / "skills" / "local-review" / "SKILL.md").exists())

        codex = self.runtime.materialize_skill(skill_id="local-review", host_kind="codex")
        codex_adapter = Path(codex["adapter_path"])
        self.assertTrue((codex_adapter / "skills" / "local-review" / "SKILL.md").exists())
        self.assertTrue((codex_adapter / "aiws-codex-export.json").exists())

    def test_stage_change_is_immutable_and_local(self) -> None:
        proposal = self.runtime.stage_change(
            skill_id="meeting-followup",
            target_scope="company",
            summary="Separate decisions from action items.",
            rationale="Repeated corrections showed they were mixed.",
            host_kind="claude-code",
        )
        proposal_path = Path(proposal["proposal_path"])

        self.assertEqual(proposal["status"], "staged")
        self.assertTrue(proposal_path.is_relative_to(self.runtime.root))
        self.assertTrue(proposal_path.exists())

        with self.assertRaises(FileExistsError):
            proposal_path.open("x").close()

        payload = json.loads(proposal_path.read_text())
        self.assertNotIn("transcript", json.dumps(payload).lower())
        self.assertEqual(payload["target_scope"], "company")

    def test_meeting_followup_scope_excludes_broad_productivity(self) -> None:
        skill = self.runtime.get_skill("meeting-followup", include_content=True)
        content = skill["entrypoint_content"]

        self.assertIn("meeting transcript", content.lower())
        self.assertIn("decisions", content.lower())
        self.assertIn("action items", content.lower())
        self.assertIn("do not create task dashboards", content.lower())
        self.assertIn("do not perform daily planning", content.lower())
        self.assertIn("do not sync tasks", content.lower())


if __name__ == "__main__":
    unittest.main()
