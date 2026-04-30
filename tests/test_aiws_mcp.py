from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp.runtime import AiwsRuntime, SkillValidationError  # noqa: E402
import aiws_mcp.runtime as runtime_module  # noqa: E402


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

    def materialize_codex_skill(self, skill_id: str = "local-review") -> dict[str, object]:
        self.write_personal_skill(skill_id, "Review local work.")
        return self.runtime.materialize_skill(skill_id=skill_id, host_kind="codex")

    def read_tree(self, root: Path) -> dict[str, bytes]:
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }

    def assert_paths_under_allowed_roots(self, payload: dict[str, object]) -> None:
        allowed_roots = [self.root.resolve(), (self.codex_home / "skills").resolve()]
        for key in ("planned_writes", "write_paths", "stale_aiws_managed"):
            for raw_path in payload.get(key, []):
                path = Path(raw_path).resolve()
                self.assertTrue(
                    any(path.is_relative_to(root) for root in allowed_roots),
                    f"{path} was not under an allowed root",
                )

    def test_clean_machine_has_sop_and_aiws_improve_without_plugins(self) -> None:
        local = self.runtime.list_local_skills()
        skill_ids = {item["skill_id"] for item in local["skills"]}

        self.assertIn("aiws-improve", skill_ids)
        self.assertNotIn("meeting-followup", skill_ids)
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

    def test_safe_copytree_rejects_source_root_symlink(self) -> None:
        source = self.root / "source"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text("---\nname: source\ndescription: Source.\n---\n")
        link = self.root / "source-link"
        os.symlink(source, link)

        with self.assertRaises(ValueError):
            runtime_module.safe_copytree(link, self.root / "destination")

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

    def test_install_host_codex_copies_materialized_adapter_skill(self) -> None:
        self.materialize_codex_skill()

        result = self.runtime.install_host(host_kind="codex")

        target = self.codex_home / "skills" / "local-review"
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["installed"], ["local-review"])
        self.assertTrue((target / "SKILL.md").exists())
        marker = json.loads((target / ".aiws-managed.json").read_text())
        self.assertEqual(marker["managed_by"], "aiws")
        self.assertEqual(marker["installed_by"], "aiws-mcp")
        self.assertEqual(marker["schema_version"], 1)
        self.assertEqual(marker["skill_id"], "local-review")
        self.assertEqual(marker["host_id"], result["host_id"])
        self.assertTrue(result["restart_required"])
        self.assert_paths_under_allowed_roots(result)

    def test_install_host_codex_dry_run_writes_nothing(self) -> None:
        self.materialize_codex_skill()

        result = self.runtime.install_host(host_kind="codex", dry_run=True)

        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["installed"], [])
        self.assertEqual(
            [Path(path).resolve() for path in result["planned_writes"]],
            [(self.codex_home / "skills" / "local-review").resolve()],
        )
        self.assertFalse((self.codex_home / "skills" / "local-review").exists())
        self.assert_paths_under_allowed_roots(result)

    def test_install_host_rejects_unsupported_host_kind(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime.install_host(host_kind="claude-code")

    def test_install_host_codex_fails_closed_for_non_aiws_target(self) -> None:
        self.materialize_codex_skill()
        target = self.codex_home / "skills" / "local-review"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("user-owned")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "conflict")
        self.assertEqual((target / "SKILL.md").read_text(), "user-owned")
        self.assertEqual(result["installed"], [])

    def test_install_host_codex_updates_aiws_owned_target_and_repeats_byte_stable(self) -> None:
        materialized = self.materialize_codex_skill()
        target = self.codex_home / "skills" / "local-review"
        first = self.runtime.install_host(host_kind="codex")
        self.assertEqual(first["status"], "ok")
        first_tree = self.read_tree(target)

        second = self.runtime.install_host(host_kind="codex")
        self.assertEqual(second["status"], "unchanged")
        self.assertEqual(first_tree, self.read_tree(target))

        source_skill = Path(materialized["adapter_path"]) / "skills" / "local-review" / "SKILL.md"
        source_skill.write_text(source_skill.read_text() + "\nUpdated guidance.\n")
        updated = self.runtime.install_host(host_kind="codex")

        self.assertEqual(updated["status"], "ok")
        self.assertEqual(updated["installed"], ["local-review"])
        self.assertIn("Updated guidance.", (target / "SKILL.md").read_text())

    def test_install_host_rejects_conflicting_host_id_and_config_root(self) -> None:
        materialized = self.materialize_codex_skill()
        host_id = Path(materialized["adapter_path"]).parent.name

        with self.assertRaises(ValueError):
            self.runtime.install_host(
                host_kind="codex",
                host_id=host_id,
                config_root=Path(self.tempdir.name) / "other-codex",
            )

    def test_install_host_rejects_host_id_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime.install_host(host_kind="codex", host_id="../outside-host")

    def test_install_host_no_skills_writes_nothing(self) -> None:
        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "no_skills")
        self.assertFalse((self.codex_home / "skills").exists())
        self.assertFalse((self.root / "hosts").exists())

    def test_install_host_reports_stale_targets_when_adapter_missing(self) -> None:
        host = self.runtime.ensure_host(host_kind="codex")
        stale = self.codex_home / "skills" / "stale-skill"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("---\nname: stale-skill\ndescription: Stale.\n---\n")
        (stale / ".aiws-managed.json").write_text(
            json.dumps(
                {
                    "host_id": host.host_id,
                    "installed_by": "aiws-mcp",
                    "managed_by": "aiws",
                    "schema_version": 1,
                    "skill_id": "stale-skill",
                    "source_adapter_path": "missing",
                    "source_digest": "sha256:missing",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "no_skills")
        self.assertIn(stale.resolve(), [Path(path).resolve() for path in result["stale_aiws_managed"]])
        self.assertTrue((stale / "SKILL.md").exists())

    def test_install_host_fails_when_codex_skills_root_is_symlink(self) -> None:
        self.materialize_codex_skill()
        outside = Path(self.tempdir.name) / "outside-skills"
        outside.mkdir()
        self.codex_home.mkdir(parents=True)
        os.symlink(outside, self.codex_home / "skills")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["installed"], [])

    def test_install_host_fails_when_adapter_path_is_symlink(self) -> None:
        host = self.runtime.ensure_host(host_kind="codex")
        outside = Path(self.tempdir.name) / "outside-adapter-skills"
        outside.mkdir()
        adapter_root = self.root / "hosts" / host.host_id / "adapter"
        adapter_root.mkdir(parents=True)
        os.symlink(outside, adapter_root / "skills")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertFalse((self.codex_home / "skills").exists())

    def test_install_host_fails_when_aiws_host_root_is_symlink(self) -> None:
        host = self.runtime.ensure_host(host_kind="codex")
        host_root = self.root / "hosts" / host.host_id
        outside = Path(self.tempdir.name) / "outside-host"
        shutil.move(host_root, outside)
        os.symlink(outside, host_root)

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("symlinks", result["errors"][0]["reason"])

    def test_install_host_fails_when_aiws_hosts_root_is_symlink(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        outside = Path(self.tempdir.name) / "outside-hosts"
        outside.mkdir()
        os.symlink(outside, self.root / "hosts")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("symlinks", result["errors"][0]["reason"])

    def test_install_host_rejects_malformed_adapter_skill_id(self) -> None:
        host = self.runtime.ensure_host(host_kind="codex")
        adapter_root = self.root / "hosts" / host.host_id / "adapter"
        bad_root = adapter_root / "skills" / "Bad_Name"
        bad_root.mkdir(parents=True)
        (bad_root / "SKILL.md").write_text("---\nname: Bad_Name\ndescription: Bad.\n---\n")
        (adapter_root / "aiws-codex-export.json").write_text(
            json.dumps({"skills": [{"skill_id": "Bad_Name", "path": "skills/Bad_Name"}]})
        )

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("Invalid skill id", result["errors"][0]["reason"])
        self.assertFalse((self.codex_home / "skills" / "Bad_Name").exists())

    def test_install_host_rejects_tampered_host_json_id(self) -> None:
        host = self.runtime.ensure_host(host_kind="codex")
        host_json = self.root / "hosts" / host.host_id / "host.json"
        payload = json.loads(host_json.read_text())
        payload["host_id"] = "../outside"
        host_json.write_text(json.dumps(payload))

        with self.assertRaises(ValueError):
            self.runtime.install_host(host_kind="codex", host_id=host.host_id)

    def test_install_host_rejects_tampered_source_symlink_without_writing(self) -> None:
        materialized = self.materialize_codex_skill("unsafe-skill")
        source = Path(materialized["adapter_path"]) / "skills" / "unsafe-skill"
        (source / "refs").mkdir()
        os.symlink("/tmp", source / "refs" / "escape")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("Symlinks are not allowed", result["errors"][0]["reason"])
        self.assertFalse((self.codex_home / "skills" / "unsafe-skill").exists())
        self.assertFalse((self.codex_home / "skills").exists())

    def test_install_host_rejects_symlinked_ownership_marker(self) -> None:
        self.materialize_codex_skill()
        target = self.codex_home / "skills" / "local-review"
        target.mkdir(parents=True)
        external_marker = Path(self.tempdir.name) / "marker.json"
        external_marker.write_text("{}")
        os.symlink(external_marker, target / ".aiws-managed.json")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "conflict")
        self.assertEqual(result["installed"], [])

    def test_install_host_repairs_tampered_aiws_owned_target_content(self) -> None:
        self.materialize_codex_skill()
        target = self.codex_home / "skills" / "local-review"
        self.runtime.install_host(host_kind="codex")
        (target / "SKILL.md").write_text("tampered")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["installed"], ["local-review"])
        self.assertIn("name: local-review", (target / "SKILL.md").read_text())

    def test_install_host_digest_includes_nested_marker_named_files(self) -> None:
        materialized = self.materialize_codex_skill()
        source = Path(materialized["adapter_path"]) / "skills" / "local-review"
        nested = source / "references"
        nested.mkdir()
        (nested / ".aiws-managed.json").write_text("source-nested-marker")
        self.runtime.install_host(host_kind="codex")
        target_nested = self.codex_home / "skills" / "local-review" / "references" / ".aiws-managed.json"
        target_nested.write_text("tampered-nested-marker")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(target_nested.read_text(), "source-nested-marker")

    def test_install_host_uses_manifest_not_unlisted_adapter_directories(self) -> None:
        materialized = self.materialize_codex_skill()
        unlisted = Path(materialized["adapter_path"]) / "skills" / "unlisted-skill"
        unlisted.mkdir()
        (unlisted / "SKILL.md").write_text("---\nname: unlisted-skill\ndescription: Unlisted.\n---\n")

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "ok")
        self.assertTrue((self.codex_home / "skills" / "local-review").exists())
        self.assertFalse((self.codex_home / "skills" / "unlisted-skill").exists())

    def test_install_host_rejects_malformed_manifest_entries(self) -> None:
        materialized = self.materialize_codex_skill()
        manifest = Path(materialized["adapter_path"]) / "aiws-codex-export.json"
        manifest.write_text(json.dumps({"skills": ["bad"]}))

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("skill entries must be objects", result["errors"][0]["reason"])
        self.assertFalse((self.codex_home / "skills" / "local-review").exists())

    def test_install_host_rejects_malformed_manifest_field_types(self) -> None:
        materialized = self.materialize_codex_skill()
        manifest = Path(materialized["adapter_path"]) / "aiws-codex-export.json"
        manifest.write_text(json.dumps({"skills": [{"skill_id": 123, "path": "skills/local-review"}]}))

        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("must be strings", result["errors"][0]["reason"])
        self.assertFalse((self.codex_home / "skills" / "local-review").exists())

    def test_install_host_revalidates_target_before_private_replace(self) -> None:
        materialized = self.materialize_codex_skill()
        source = Path(materialized["adapter_path"]) / "skills" / "local-review"
        target = self.codex_home / "skills" / "local-review"
        target.mkdir(parents=True)
        (target / "SKILL.md").write_text("user-owned")

        with self.assertRaises(ValueError):
            self.runtime._install_codex_skill(
                source=source,
                target=target,
                marker={
                    "host_id": Path(materialized["adapter_path"]).parent.name,
                    "installed_by": "aiws-mcp",
                    "managed_by": "aiws",
                    "schema_version": 1,
                    "skill_id": "local-review",
                    "source_adapter_path": str(source),
                    "source_digest": "sha256:test",
                },
            )
        self.assertEqual((target / "SKILL.md").read_text(), "user-owned")

    def test_install_host_revalidates_target_after_copy_before_replace(self) -> None:
        self.materialize_codex_skill()
        target = self.codex_home / "skills" / "local-review"
        self.runtime.install_host(host_kind="codex")
        original_safe_copytree = runtime_module.safe_copytree

        def swap_target_after_copy(source: Path, destination: Path) -> None:
            original_safe_copytree(source, destination)
            shutil.rmtree(target)
            target.mkdir()
            (target / "SKILL.md").write_text("late-user-owned")

        source_skill = self.root / "hosts" / self.runtime.ensure_host(host_kind="codex").host_id / "adapter" / "skills" / "local-review" / "SKILL.md"
        source_skill.write_text(source_skill.read_text() + "\nchange to force reinstall\n")
        with patch.object(runtime_module, "safe_copytree", side_effect=swap_target_after_copy):
            result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "failed")
        self.assertIn("not AIWS-owned", result["errors"][0]["reason"])
        self.assertEqual((target / "SKILL.md").read_text(), "late-user-owned")

    def test_install_host_marker_digest_matches_copied_source_after_source_drift(self) -> None:
        materialized = self.materialize_codex_skill()
        source = Path(materialized["adapter_path"]) / "skills" / "local-review"
        source_skill = source / "SKILL.md"
        original_safe_copytree = runtime_module.safe_copytree

        def change_source_before_copy(source_arg: Path, destination: Path) -> None:
            source_skill.write_text(source_skill.read_text() + "\nlate source change\n")
            original_safe_copytree(source_arg, destination)

        with patch.object(runtime_module, "safe_copytree", side_effect=change_source_before_copy):
            result = self.runtime.install_host(host_kind="codex")

        target = self.codex_home / "skills" / "local-review"
        marker = json.loads((target / ".aiws-managed.json").read_text())
        self.assertEqual(result["status"], "ok")
        self.assertEqual(marker["source_digest"], runtime_module.tree_digest(target, exclude_root_marker=True))
        self.assertIn("late source change", (target / "SKILL.md").read_text())

    def test_install_host_reports_stale_aiws_managed_targets_without_removing(self) -> None:
        self.materialize_codex_skill("active-skill")
        self.runtime.install_host(host_kind="codex")
        stale = self.codex_home / "skills" / "stale-skill"
        stale.mkdir(parents=True)
        (stale / "SKILL.md").write_text("---\nname: stale-skill\ndescription: Stale.\n---\n")
        (stale / ".aiws-managed.json").write_text(
            json.dumps(
                {
                    "host_id": self.runtime.ensure_host(host_kind="codex").host_id,
                    "installed_by": "aiws-mcp",
                    "managed_by": "aiws",
                    "schema_version": 1,
                    "skill_id": "stale-skill",
                    "source_adapter_path": "missing",
                    "source_digest": "sha256:missing",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        result = self.runtime.install_host(host_kind="codex")

        self.assertIn(stale.resolve(), [Path(path).resolve() for path in result["stale_aiws_managed"]])
        self.assertTrue((stale / "SKILL.md").exists())
        self.assert_paths_under_allowed_roots(result)

    def test_install_host_cli_dry_run_and_unsupported_failure(self) -> None:
        self.materialize_codex_skill()
        env = os.environ.copy()
        env["PYTHONPATH"] = AIWS_MCP_PYTHONPATH
        dry_run = subprocess.run(
            [
                sys.executable,
                "-m",
                "aiws_mcp",
                "--root",
                str(self.root),
                "install-host",
                "--host-kind",
                "codex",
                "--config-root",
                str(self.codex_home),
                "--dry-run",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(dry_run.stdout)
        self.assertEqual(payload["status"], "planned")
        self.assertFalse((self.codex_home / "skills" / "local-review").exists())

        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "aiws_mcp",
                "--root",
                str(self.root),
                "install-host",
                "--host-kind",
                "cowork",
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("supports only host_kind='codex'", failed.stderr)

    def test_stage_change_is_immutable_and_local(self) -> None:
        proposal = self.runtime.stage_change(
            skill_id="aiws-improve",
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


if __name__ == "__main__":
    unittest.main()
