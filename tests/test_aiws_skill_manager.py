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
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp.skill_manager import (  # noqa: E402
    SkillManagerError,
    activate_draft,
    build_draft_package,
    create_or_open_draft,
    create_draft_record,
    deactivate_draft,
    delete_draft_file,
    discover_installed_plugins,
    draft_id,
    draft_worktree_path,
    GhCliProposalSubmitter,
    GithubHandoffProposalSubmitter,
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    load_draft_record,
    list_draft_files,
    read_draft_file,
    refresh_modified_status,
    revert_draft,
    stage_proposal,
    submit_pr,
    tree_digest,
    update_from_github_decision,
    validate_marketplace,
    validate_plugin,
    validate_draft,
    validate_mcp_config,
    validate_skill_creator_compat,
    default_command_runner,
    write_draft_file,
)


class FakeProposalSubmitter:
    def __init__(self, response: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        if self.error is not None:
            raise self.error
        if self.response is not None:
            return self.response
        return {
            "branch_name": payload["branch_name"],
            "pr_url": "https://github.com/example/review/pull/123",
        }


class RecordingHandoffSubmitter(GithubHandoffProposalSubmitter):
    def __init__(self, *, aiws_root: Path) -> None:
        super().__init__(aiws_root=aiws_root)
        self.calls: list[dict[str, object]] = []

    def submit(self, payload: dict[str, object]) -> dict[str, object]:
        self.calls.append(payload)
        return super().submit(payload)


class FakeCommandRunner:
    def __init__(
        self,
        target_repo: Path,
        *,
        existing_pr_url: str | None = None,
        existing_pr_is_draft: bool = False,
        no_changes: bool = False,
    ) -> None:
        self.target_repo = target_repo
        self.existing_pr_url = existing_pr_url
        self.existing_pr_is_draft = existing_pr_is_draft
        self.no_changes = no_changes
        self.calls: list[tuple[list[str], Path | None]] = []

    def __call__(
        self,
        args: list[str],
        *,
        cwd: Path | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append((list(args), cwd))
        if args[:3] == ["gh", "api", "repos/example/review"]:
            return subprocess.CompletedProcess(args, 0, '{"default_branch":"main","permissions":{"push":true}}\n', "")
        if args[:4] == ["gh", "repo", "clone", "example/review"]:
            destination = Path(args[4])
            shutil.copytree(self.target_repo, destination)
            (destination / ".git").mkdir()
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["git", "checkout", "-B"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["git", "status", "--porcelain"]:
            stdout = "" if self.no_changes else " M skills/meeting-followup/SKILL.md\n"
            return subprocess.CompletedProcess(args, 0, stdout, "")
        if args[:2] == ["git", "add"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["git", "commit"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["git", "push", "--force-with-lease"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["gh", "pr", "list"]:
            stdout = (
                json.dumps([{"url": self.existing_pr_url, "isDraft": self.existing_pr_is_draft}])
                if self.existing_pr_url
                else "[]"
            )
            return subprocess.CompletedProcess(args, 0, stdout, "")
        if args[:3] == ["gh", "pr", "edit"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["gh", "pr", "ready"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(args, 0, "https://github.com/example/review/pull/7\n", "")
        raise AssertionError(f"Unexpected command: {args}")


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
        self.assertEqual(decision["reason"], "modified_draft_or_pending_upload")
        self.assertEqual(
            decision["choices"],
            ["keep_local_draft_and_pending_package", "discard_local_changes_and_update", "submit_or_upload_first"],
        )

    def test_create_or_open_draft_copies_valid_plugin_and_records_origin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            record = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )

            draft_path = Path(record.draft_path)
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")

            self.assertTrue((draft_path / ".claude-plugin" / "plugin.json").is_file())
            self.assertTrue((draft_path / "skills" / "meeting-followup" / "SKILL.md").is_file())
            self.assertEqual(load_draft_record(aiws_root, record_id), record)
            self.assertTrue(record.active)
            self.assertFalse(record.modified)
            self.assertEqual(record.last_validation_status, "passed")
            self.assertIsInstance(record.base_tree_digest, str)
            self.assertIsInstance(record.current_tree_digest, str)
            self.assertEqual(record.base_tree_digest, record.current_tree_digest)

    def test_create_or_open_draft_rejects_source_plugin_symlinks_before_copy(self) -> None:
        for planted in ("skill-file", "nested-file", "directory"):
            with self.subTest(planted=planted):
                with tempfile.TemporaryDirectory() as temp:
                    temp_root = Path(temp)
                    aiws_root = temp_root / ".aiws"
                    plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
                    skill_file = self.write_skill(plugin_root, "meeting-followup")
                    outside = temp_root / "outside.md"
                    outside.write_text("outside\n")
                    if planted == "skill-file":
                        skill_file.unlink()
                        skill_file.symlink_to(outside)
                    elif planted == "nested-file":
                        refs = plugin_root / "skills" / "meeting-followup" / "references"
                        refs.mkdir()
                        (refs / "linked.md").symlink_to(outside)
                    else:
                        outside_dir = temp_root / "outside-dir"
                        outside_dir.mkdir()
                        (plugin_root / "skills" / "meeting-followup" / "references").symlink_to(
                            outside_dir,
                            target_is_directory=True,
                        )

                    with self.assertRaisesRegex(SkillManagerError, "Source plugin tree must not contain symlinks"):
                        create_or_open_draft(
                            aiws_root,
                            source_plugin_root=plugin_root,
                            plugin_id="example-plugin",
                            skill_id="meeting-followup",
                            origin_marketplace="ai-workspace",
                            origin_repo="https://github.com/example/example-plugin",
                            origin_ref="master",
                            base_version="1.0.0",
                            base_commit="abc123",
                        )

                    self.assertFalse((aiws_root / "plugins").exists())

    def test_refresh_modified_status_keeps_unchanged_draft_unmodified_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(Path(temp))

            refreshed = refresh_modified_status(aiws_root, record_id)
            loaded = load_draft_record(aiws_root, record_id)

            self.assertFalse(refreshed.modified)
            self.assertEqual(refreshed, loaded)
            self.assertEqual(refreshed.base_tree_digest, refreshed.current_tree_digest)

    def test_refresh_modified_status_marks_skill_file_edit_modified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")

            refreshed = refresh_modified_status(aiws_root, record_id)

            self.assertTrue(refreshed.modified)
            self.assertNotEqual(refreshed.base_tree_digest, refreshed.current_tree_digest)
            self.assertTrue(load_draft_record(aiws_root, record_id).modified)

    def test_refresh_modified_status_preserves_legacy_modified_record_without_base_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            legacy_payload = record.to_json()
            legacy_payload.pop("base_tree_digest")
            legacy_payload.pop("current_tree_digest")
            legacy_payload.pop("last_validation_tree_digest")
            legacy_payload["modified"] = True
            legacy_payload["updated_at"] = "2026-05-09T00:00:00Z"
            record_path.write_text(json.dumps(legacy_payload))

            refreshed = refresh_modified_status(aiws_root, record_id)
            loaded = load_draft_record(aiws_root, record_id)

            self.assertTrue(refreshed.modified)
            self.assertIsNone(refreshed.base_tree_digest)
            self.assertIsInstance(refreshed.current_tree_digest, str)
            self.assertIsNone(refreshed.last_validation_tree_digest)
            self.assertEqual(refreshed, loaded)

    def test_refresh_modified_status_marks_added_or_deleted_file_modified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            draft_root = Path(record.draft_path)
            extra = draft_root / "skills" / "meeting-followup" / "references" / "extra.md"
            extra.parent.mkdir()
            extra.write_text("Extra reference.\n")

            added = refresh_modified_status(aiws_root, record_id)
            self.assertTrue(added.modified)

            extra.unlink()
            skill_file = draft_root / "skills" / "meeting-followup" / "SKILL.md"
            skill_file.unlink()
            deleted = refresh_modified_status(aiws_root, record_id)

            self.assertTrue(deleted.modified)
            self.assertNotEqual(deleted.base_tree_digest, deleted.current_tree_digest)

    def test_reopened_changed_draft_refresh_preserves_local_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")

            reopened = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )
            refreshed = refresh_modified_status(aiws_root, record_id)

            self.assertEqual(Path(reopened.draft_path), Path(record.draft_path))
            self.assertIn("Local draft edit.", draft_skill.read_text())
            self.assertTrue(reopened.modified)
            self.assertTrue(refreshed.modified)

    def test_upstream_source_change_after_draft_creation_does_not_change_base_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            original_base_digest = record.base_tree_digest
            source_skill = plugin_root / "skills" / "meeting-followup" / "SKILL.md"
            source_skill.write_text(source_skill.read_text() + "\nUpstream-only change.\n")

            refreshed = refresh_modified_status(aiws_root, record_id)

            self.assertFalse(refreshed.modified)
            self.assertEqual(refreshed.base_tree_digest, original_base_digest)
            self.assertEqual(refreshed.base_tree_digest, refreshed.current_tree_digest)

    def test_refresh_modified_status_fails_closed_on_symlink_in_draft_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            draft_root = Path(record.draft_path)
            outside = Path(temp) / "outside.md"
            outside.write_text("outside\n")
            (draft_root / "skills" / "meeting-followup" / "escape.md").symlink_to(outside)

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                refresh_modified_status(aiws_root, record_id)

            self.assertFalse(load_draft_record(aiws_root, record_id).modified)

    def test_draft_file_tools_are_limited_to_requested_skill_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(Path(temp))

            listed = list_draft_files(aiws_root, record_id)
            self.assertIn("skills/meeting-followup/SKILL.md", listed["files"])

            original = read_draft_file(aiws_root, record_id, "skills/meeting-followup/SKILL.md")
            self.assertIn("name: meeting-followup", original["content"])

            written = write_draft_file(
                aiws_root,
                record_id,
                "skills/meeting-followup/references/notes.md",
                "Review notes.\n",
            )
            self.assertEqual(written["status"], "written")
            self.assertTrue(load_draft_record(aiws_root, record_id).modified)
            self.assertEqual(
                read_draft_file(aiws_root, record_id, "skills/meeting-followup/references/notes.md")["content"],
                "Review notes.\n",
            )

            deleted = delete_draft_file(aiws_root, record_id, "skills/meeting-followup/references/notes.md")
            self.assertEqual(deleted["status"], "deleted")
            self.assertNotIn("references/notes.md", "\n".join(list_draft_files(aiws_root, record_id)["files"]))

            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                write_draft_file(aiws_root, record_id, "contracts/example-plugin.contract.json", "{}\n")
            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                read_draft_file(aiws_root, record_id, "../escape.md")

    def test_draft_file_tools_reject_symlinked_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            outside = temp_root / "outside.md"
            outside.write_text("outside\n")
            link = Path(record.draft_path) / "skills" / "meeting-followup" / "linked.md"
            link.symlink_to(outside)

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                read_draft_file(aiws_root, record_id, "skills/meeting-followup/linked.md")

    def test_build_draft_package_creates_flat_zip_and_preserves_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            self.set_record_validation_status(aiws_root, record_id, "failed")

            result = build_draft_package(aiws_root, record_id, package_dir)

            package_path = Path(result["package_path"])
            self.assertEqual(result["status"], "packaged")
            self.assertEqual(result["record_id"], record_id)
            self.assertEqual(result["plugin_id"], "example-plugin")
            self.assertEqual(result["skill_id"], "meeting-followup")
            self.assertTrue(result["modified"])
            self.assertEqual(result["status_label"], "Modified locally")
            self.assertEqual(result["validation_status"], "passed")
            self.assertTrue(package_path.is_file())
            with zipfile.ZipFile(package_path) as package:
                names = package.namelist()
                self.assertIn(".claude-plugin/plugin.json", names)
                self.assertIn("contracts/example-plugin.contract.json", names)
                self.assertIn("skills/meeting-followup/SKILL.md", names)
                self.assertNotIn("example-plugin/.claude-plugin/plugin.json", names)
                self.assertTrue(all(not name.startswith("/") and ".." not in Path(name).parts for name in names))
                manifest = json.loads(package.read(".claude-plugin/plugin.json"))
                skill = package.read("skills/meeting-followup/SKILL.md").decode()

            self.assertEqual(manifest["name"], "example-plugin")
            self.assertEqual(manifest["version"], "1.0.0")
            self.assertIn("name: meeting-followup", skill)
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "passed")

    def test_activate_draft_modified_returns_cowork_manual_upload_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            self.set_record_validation_status(aiws_root, record_id, "failed")

            result = activate_draft(aiws_root, record_id, "cowork", package_dir, host_id="cowork-test")

            self.assertEqual(result["status"], "host_capability_missing")
            self.assertEqual(result["activation_status"], "pending_upload")
            self.assertEqual(result["record_id"], record_id)
            self.assertEqual(result["host_id"], "cowork-test")
            self.assertEqual(result["plugin_id"], "example-plugin")
            self.assertEqual(result["skill_id"], "meeting-followup")
            self.assertTrue(result["modified"])
            self.assertEqual(result["status_label"], "Modified locally")
            self.assertFalse(result["activation_effective"])
            self.assertTrue(result["requires_manual_upload"])
            self.assertEqual(len(result["actions"]), 1)
            self.assertEqual(
                result["actions"][0],
                {
                    "type": "package_upload",
                    "terminal": False,
                    "host_kind": "cowork",
                    "package_path": result["package_path"],
                    "label": "Upload draft package to Cowork",
                },
            )
            self.assertTrue(Path(result["package_path"]).is_file())
            activation_record_path = Path(result["activation_record_path"])
            self.assertEqual(
                activation_record_path,
                aiws_root / "state" / "draft-activations" / "cowork-test" / f"{record_id}.json",
            )
            activation_record = json.loads(activation_record_path.read_text())
            self.assertEqual(activation_record["status"], "pending_upload")
            self.assertEqual(activation_record["draft_id"], record_id)
            self.assertEqual(activation_record["host_id"], "cowork-test")
            self.assertEqual(activation_record["package_path"], result["package_path"])
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "passed")

    def test_activate_draft_can_prepare_cowork_package_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            upload_dir = temp_root / "cowork-packages"
            upload_dir.mkdir()

            result = activate_draft(
                aiws_root,
                record_id,
                "cowork",
                package_dir,
                host_id="cowork-test",
                package_upload_dir=upload_dir,
            )

            package_path = Path(result["package_path"])
            copied_package_path = Path(result["copied_package_path"])
            self.assertEqual(result["status"], "handoff_prepared")
            self.assertEqual(result["activation_status"], "pending_upload")
            self.assertFalse(result["activation_effective"])
            self.assertFalse(result["requires_manual_upload"])
            self.assertTrue(result["requires_cowork_confirmation"])
            self.assertEqual(result["package_upload_surface"], str(upload_dir.resolve()))
            self.assertTrue(package_path.is_file())
            self.assertTrue(copied_package_path.is_file())
            self.assertEqual(copied_package_path.parent, upload_dir.resolve())
            self.assertEqual(copied_package_path.read_bytes(), package_path.read_bytes())
            self.assertEqual(
                result["actions"][0],
                {
                    "type": "cowork_package_handoff",
                    "terminal": False,
                    "host_kind": "cowork",
                    "package_path": result["package_path"],
                    "copied_package_path": result["copied_package_path"],
                    "label": "Confirm draft package in Cowork",
                },
            )
            activation_record = json.loads(Path(result["activation_record_path"]).read_text())
            self.assertEqual(activation_record["status"], "pending_upload")
            self.assertEqual(activation_record["handoff_status"], "handoff_prepared")
            self.assertEqual(activation_record["copied_package_path"], result["copied_package_path"])

    def test_activate_draft_reuses_existing_identical_cowork_handoff_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            upload_dir = temp_root / "cowork-packages"
            upload_dir.mkdir()

            first = activate_draft(
                aiws_root,
                record_id,
                "cowork",
                package_dir,
                host_id="cowork-test",
                package_upload_dir=upload_dir,
            )
            second = activate_draft(
                aiws_root,
                record_id,
                "cowork",
                package_dir,
                host_id="cowork-test",
                package_upload_dir=upload_dir,
            )

            self.assertEqual(second["status"], "handoff_prepared")
            self.assertEqual(second["copied_package_path"], first["copied_package_path"])
            self.assertEqual(Path(second["copied_package_path"]).read_bytes(), Path(second["package_path"]).read_bytes())

    def test_activate_draft_refuses_unsafe_cowork_package_handoff_surface(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"

            with self.assertRaisesRegex(SkillManagerError, "must already exist"):
                activate_draft(
                    aiws_root,
                    record_id,
                    "cowork",
                    package_dir,
                    host_id="cowork-test",
                    package_upload_dir=temp_root / "missing-upload-dir",
                )

            upload_dir = temp_root / "cowork-packages"
            upload_dir.mkdir()
            destination = upload_dir / f"{record_id}.zip"
            destination.write_text("different package")
            with self.assertRaisesRegex(SkillManagerError, "already exists with different content"):
                activate_draft(
                    aiws_root,
                    record_id,
                    "cowork",
                    package_dir,
                    host_id="cowork-test",
                    package_upload_dir=upload_dir,
                )

    def test_activate_draft_unchanged_returns_not_modified_without_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(temp_root)
            package_dir = temp_root / "packages"
            self.set_record_validation_status(aiws_root, record_id, "failed")

            result = activate_draft(aiws_root, record_id, "cowork", package_dir, host_id="cowork-test")

            self.assertEqual(
                result,
                {
                    "status": "not_modified",
                    "record_id": record_id,
                    "plugin_id": "example-plugin",
                    "skill_id": "meeting-followup",
                    "modified": False,
                    "status_label": "Current",
                    "actions": [],
                },
            )
            self.assertFalse(package_dir.exists())
            self.assertFalse((aiws_root / "state" / "draft-activations").exists())
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "passed")

    def test_deactivate_draft_clears_matching_pending_upload_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            activated = activate_draft(aiws_root, record_id, "cowork", package_dir, host_id="cowork-test")
            package_path = Path(activated["package_path"])

            result = deactivate_draft(aiws_root, record_id, "cowork", "cowork-test")

            self.assertEqual(result["status"], "deactivated")
            self.assertEqual(result["activation_status"], "inactive")
            self.assertTrue(result["cleared"])
            self.assertFalse(Path(activated["activation_record_path"]).exists())
            self.assertTrue(package_path.exists())
            loaded = load_draft_record(aiws_root, record_id)
            self.assertTrue(loaded.modified)

    def test_deactivate_draft_rejects_mismatched_pending_upload_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            activated = activate_draft(aiws_root, record_id, "cowork", package_dir, host_id="cowork-test")
            activation_record_path = Path(activated["activation_record_path"])
            payload = json.loads(activation_record_path.read_text())
            payload["draft_id"] = "other-draft"
            activation_record_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(SkillManagerError, "does not match requested draft"):
                deactivate_draft(aiws_root, record_id, "cowork", "cowork-test")

            self.assertTrue(activation_record_path.exists())

    def test_activate_draft_rejects_tampered_record_id_before_package_or_pending_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            wrong_record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/other")
            shutil.copyfile(
                aiws_root / "state" / "skill-drafts" / f"{record_id}.json",
                aiws_root / "state" / "skill-drafts" / f"{wrong_record_id}.json",
            )
            package_dir = temp_root / "packages"

            with self.assertRaisesRegex(SkillManagerError, "canonical draft id"):
                activate_draft(aiws_root, wrong_record_id, "cowork", package_dir, host_id="cowork-test")

            self.assert_no_package_artifacts(package_dir)
            self.assertFalse((aiws_root / "state" / "draft-activations").exists())

    def test_build_draft_package_missing_requested_skill_fails_closed_without_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_root = Path(record.draft_path)
            (draft_root / "skills" / "meeting-followup" / "SKILL.md").unlink()
            package_dir = temp_root / "packages"

            with self.assertRaises(SkillManagerError):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assert_no_package_artifacts(package_dir)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)

    def test_build_draft_package_symlink_in_draft_tree_fails_closed_without_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            outside = temp_root / "outside.md"
            outside.write_text("outside\n")
            (Path(record.draft_path) / "skills" / "meeting-followup" / "escape.md").symlink_to(outside)
            package_dir = temp_root / "packages"

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assert_no_package_artifacts(package_dir)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)
            self.assertEqual(loaded.base_tree_digest, record.base_tree_digest)
            self.assertIsNone(loaded.current_tree_digest)

    def test_activate_draft_symlink_refresh_failure_marks_modified_without_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            outside = temp_root / "outside.md"
            outside.write_text("outside\n")
            (Path(record.draft_path) / "skills" / "meeting-followup" / "escape.md").symlink_to(outside)
            package_dir = temp_root / "packages"

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                activate_draft(aiws_root, record_id, "cowork", package_dir, host_id="cowork-test")

            self.assert_no_package_artifacts(package_dir)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)
            self.assertEqual(loaded.base_tree_digest, record.base_tree_digest)
            self.assertIsNone(loaded.current_tree_digest)

    def test_build_draft_package_rejects_symlinked_output_directory_or_package_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            real_output = temp_root / "real-output"
            real_output.mkdir()
            symlinked_output = temp_root / "packages-link"
            symlinked_output.symlink_to(real_output, target_is_directory=True)

            with self.assertRaisesRegex(SkillManagerError, "Package output directory must not be a symlink"):
                build_draft_package(aiws_root, record_id, symlinked_output)

            self.assertEqual(list(real_output.iterdir()), [])
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "failed")

            package_dir = temp_root / "packages"
            package_dir.mkdir()
            outside_zip = temp_root / "outside.zip"
            outside_zip.write_text("outside\n")
            (package_dir / f"{record_id}.zip").symlink_to(outside_zip)
            self.set_record_validation_status(aiws_root, record_id, "passed")

            with self.assertRaisesRegex(SkillManagerError, "Package path must not be a symlink"):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assertEqual(outside_zip.read_text(), "outside\n")
            self.assertFalse(any(path.suffix == ".tmp" for path in package_dir.iterdir()))
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "failed")

    def test_build_draft_package_rejects_symlinked_output_parent_without_writing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            real_output = temp_root / "real-output"
            real_output.mkdir()
            link_parent = temp_root / "link-parent"
            link_parent.symlink_to(real_output, target_is_directory=True)

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                build_draft_package(aiws_root, record_id, link_parent / "nested")

            self.assertEqual(list(real_output.iterdir()), [])
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)

    def test_build_draft_package_rejects_output_directory_inside_draft_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = Path(record.draft_path) / "packages"

            with self.assertRaisesRegex(SkillManagerError, "must not be inside the draft tree"):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assertFalse(package_dir.exists())
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_status, "failed")

    def test_build_draft_package_rejects_aiws_memory_import_export_output_dirs_without_creating_them(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            for name in ("memory", "imports", "exports"):
                with self.subTest(name=name):
                    temp_root = Path(temp) / name
                    temp_root.mkdir()
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
                    draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
                    draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
                    package_dir = aiws_root / name

                    with self.assertRaisesRegex(SkillManagerError, "disallowed package output directory"):
                        build_draft_package(aiws_root, record_id, package_dir)

                    self.assertFalse(package_dir.exists())
                    loaded = load_draft_record(aiws_root, record_id)
                    self.assertEqual(loaded.last_validation_status, "failed")
                    self.assertTrue(loaded.modified)

    def test_build_draft_package_rejects_claude_memory_data_output_dir_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = temp_root / ".claude" / "plugins" / "data" / "global-memory"

            with self.assertRaisesRegex(SkillManagerError, "disallowed package output directory"):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assertFalse(package_dir.exists())
            self.assertFalse((temp_root / ".claude").exists())
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)

    def test_build_draft_package_rejects_any_claude_output_dir_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = temp_root / ".claude" / "packages"

            with self.assertRaisesRegex(SkillManagerError, "disallowed package output directory: .claude"):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assertFalse(package_dir.exists())
            self.assertFalse((temp_root / ".claude").exists())
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)

    def test_build_draft_package_failed_rebuild_removes_stale_final_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            package_dir = temp_root / "packages"
            first = build_draft_package(aiws_root, record_id, package_dir)
            package_path = Path(first["package_path"])
            self.assertTrue(package_path.is_file())

            draft_skill.unlink()

            with self.assertRaises(SkillManagerError):
                build_draft_package(aiws_root, record_id, package_dir)

            self.assertFalse(package_path.exists())
            self.assertFalse(any(path.suffix == ".tmp" for path in package_dir.iterdir()))
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertTrue(loaded.modified)

    def test_draft_status_persistence_rejects_planted_json_tmp_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(temp_root)
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            outside = temp_root / "outside.json"
            outside.write_text("outside\n")
            record_tmp = record_path.with_suffix(record_path.suffix + ".tmp")
            record_tmp.symlink_to(outside)
            real_output = temp_root / "real-output"
            real_output.mkdir()
            link_parent = temp_root / "link-parent"
            link_parent.symlink_to(real_output, target_is_directory=True)

            with self.assertRaisesRegex(SkillManagerError, "JSON temporary path must not be a symlink"):
                build_draft_package(aiws_root, record_id, link_parent / "nested")

            self.assertEqual(outside.read_text(), "outside\n")
            self.assertTrue(record_tmp.is_symlink())
            self.assertEqual(list(real_output.iterdir()), [])

    def test_activate_draft_unsupported_host_kind_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(Path(temp))

            with self.assertRaisesRegex(SkillManagerError, "Only host_kind='cowork'"):
                activate_draft(aiws_root, record_id, "codex", Path(temp) / "packages", host_id="codex-test")

    def test_activate_draft_does_not_create_cowork_rpm_host_or_memory_dirs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")

            activate_draft(aiws_root, record_id, "cowork", temp_root / "packages", host_id="cowork-test")

            self.assertFalse((aiws_root / "hosts").exists())
            self.assertFalse((aiws_root / "memory").exists())
            self.assertFalse((aiws_root / "imports").exists())
            self.assertFalse((aiws_root / "exports").exists())
            self.assertFalse((aiws_root / "rpm").exists())
            self.assertFalse((temp_root / ".claude").exists())

    def test_validate_draft_changed_skill_passes_without_proposal_or_package(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal validation edit.\n")
            package_dir = temp_root / "packages"
            source_before = {
                path.relative_to(plugin_root).as_posix(): path.read_bytes()
                for path in sorted(plugin_root.rglob("*"))
                if path.is_file()
            }

            result = validate_draft(aiws_root, record_id)

            current_digest = tree_digest(Path(record.draft_path))
            source_after = {
                path.relative_to(plugin_root).as_posix(): path.read_bytes()
                for path in sorted(plugin_root.rglob("*"))
                if path.is_file()
            }
            self.assertEqual(result["status"], "validated")
            self.assertEqual(result["validation_status"], "passed")
            self.assertTrue(result["modified"])
            self.assertEqual(result["current_tree_digest"], current_digest)
            self.assertEqual(source_after, source_before)
            self.assert_no_proposals(aiws_root)
            self.assert_no_package_artifacts(package_dir)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "passed")
            self.assertEqual(loaded.last_validation_tree_digest, current_digest)
            self.assertEqual(loaded.current_tree_digest, current_digest)
            self.assertTrue(loaded.modified)

    def test_validate_draft_unchanged_passes_and_marks_unmodified(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))

            result = validate_draft(aiws_root, record_id)

            current_digest = tree_digest(Path(record.draft_path))
            self.assertEqual(result["validation_status"], "passed")
            self.assertFalse(result["modified"])
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "passed")
            self.assertEqual(loaded.last_validation_tree_digest, current_digest)
            self.assertEqual(loaded.current_tree_digest, current_digest)
            self.assertFalse(loaded.modified)
            self.assert_no_proposals(aiws_root)

    def test_validate_draft_invalid_plugin_or_missing_skill_fails_without_proposal(self) -> None:
        for breakage in ("invalid-plugin", "missing-skill"):
            with self.subTest(breakage=breakage):
                with tempfile.TemporaryDirectory() as temp:
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
                    self.edit_draft_skill(record, "\nLocal validation edit.\n")
                    draft_root = Path(record.draft_path)
                    if breakage == "invalid-plugin":
                        manifest_path = draft_root / ".claude-plugin" / "plugin.json"
                        manifest = json.loads(manifest_path.read_text())
                        manifest["name"] = "other-plugin"
                        manifest_path.write_text(json.dumps(manifest))
                    else:
                        (draft_root / "skills" / "meeting-followup" / "SKILL.md").unlink()

                    with self.assertRaises(SkillManagerError):
                        validate_draft(aiws_root, record_id)

                    self.assert_no_proposals(aiws_root)
                    loaded = load_draft_record(aiws_root, record_id)
                    self.assertEqual(loaded.last_validation_status, "failed")
                    self.assertIsNone(loaded.last_validation_tree_digest)

    def test_validate_draft_rejects_changes_outside_requested_skill_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal validation edit.\n")
            contract = Path(record.draft_path) / "contracts" / "example-plugin.contract.json"
            contract.write_text(contract.read_text() + "\n")

            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                validate_draft(aiws_root, record_id)

            self.assert_no_proposals(aiws_root)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertIsNone(loaded.last_validation_tree_digest)

    def test_validate_draft_root_level_out_of_scope_file_persists_failed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            (Path(record.draft_path) / "plugin.yaml").write_text("name: test-only\n")

            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                validate_draft(aiws_root, record_id)

            self.assert_no_proposals(aiws_root)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertIsNone(loaded.last_validation_tree_digest)
            self.assertTrue(loaded.modified)
            self.assertNotEqual(loaded.current_tree_digest, record.base_tree_digest)

            reopened = create_or_open_draft(
                aiws_root,
                source_plugin_root=_plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )

            self.assertEqual(reopened.last_validation_status, "failed")
            self.assertIsNone(reopened.last_validation_tree_digest)
            self.assertTrue(reopened.modified)
            self.assertTrue((Path(reopened.draft_path) / "plugin.yaml").is_file())

    def test_create_or_open_draft_reopens_dirty_draft_when_source_marketplace_slug_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")
            origin_repo = "https://github.com/example/example-plugin"

            record = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="rpm",
                origin_repo=origin_repo,
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )
            (Path(record.draft_path) / "plugin.yaml").write_text("name: test-only\n")
            record_id = draft_id("example-plugin", "meeting-followup", origin_repo)
            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                validate_draft(aiws_root, record_id)

            reopened = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="cowork-upload",
                origin_repo=origin_repo,
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )

            self.assertEqual(Path(reopened.draft_path), Path(record.draft_path))
            self.assertEqual(reopened.origin_marketplace, "rpm")
            self.assertEqual(reopened.last_validation_status, "failed")
            self.assertIsNone(reopened.last_validation_tree_digest)
            self.assertTrue(reopened.modified)
            self.assertTrue((Path(reopened.draft_path) / "plugin.yaml").is_file())

    def test_create_or_open_draft_rejects_tampered_existing_record_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")
            requested_repo = "https://github.com/example/example-plugin"
            record_id = draft_id("example-plugin", "meeting-followup", requested_repo)
            tampered_repo = "https://github.com/example/other-plugin"
            tampered_draft = draft_worktree_path(aiws_root, "rpm", "other-plugin", tampered_repo)
            tampered_draft.mkdir(parents=True)
            payload = {
                "plugin_id": "other-plugin",
                "skill_id": "meeting-followup",
                "origin_marketplace": "rpm",
                "origin_repo": tampered_repo,
                "origin_ref": "master",
                "base_version": "1.0.0",
                "base_commit": "abc123",
                "draft_path": str(tampered_draft),
                "base_tree_digest": "base",
                "current_tree_digest": "base",
                "active": True,
                "modified": False,
                "publish_target": None,
                "branch_name": None,
                "pr_url": None,
                "last_validation_status": "passed",
                "last_validation_tree_digest": "base",
                "updated_at": "2026-05-09T00:00:00Z",
            }
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(SkillManagerError, "does not match requested draft identity"):
                create_or_open_draft(
                    aiws_root,
                    source_plugin_root=plugin_root,
                    plugin_id="example-plugin",
                    skill_id="meeting-followup",
                    origin_marketplace="cowork-upload",
                    origin_repo=requested_repo,
                    origin_ref="master",
                    base_version="1.0.0",
                    base_commit="abc123",
                )

            self.assertEqual(json.loads(record_path.read_text())["plugin_id"], "other-plugin")
            self.assertTrue(tampered_draft.exists())

    def test_validate_draft_rejects_legacy_record_missing_base_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal validation edit.\n")
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            payload = json.loads(record_path.read_text())
            payload.pop("base_tree_digest")
            record_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(SkillManagerError, "base_tree_digest"):
                validate_draft(aiws_root, record_id)

            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertIsNone(loaded.last_validation_tree_digest)
            self.assertTrue(loaded.modified)
            self.assert_no_proposals(aiws_root)

    def test_validate_draft_rejects_unexpected_path_and_symlink_escape(self) -> None:
        for breakage in ("unexpected-path", "symlink"):
            with self.subTest(breakage=breakage):
                with tempfile.TemporaryDirectory() as temp:
                    temp_root = Path(temp)
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
                    if breakage == "unexpected-path":
                        record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
                        payload = json.loads(record_path.read_text())
                        payload["draft_path"] = str(temp_root / "outside-draft")
                        record_path.write_text(json.dumps(payload))
                        expected = "outside AIWS draft plugin root|unexpected draft path"
                    else:
                        outside = temp_root / "outside.txt"
                        outside.write_text("escape")
                        (Path(record.draft_path) / "skills" / "meeting-followup" / "escape.md").symlink_to(outside)
                        expected = "must not contain symlinks"

                    with self.assertRaisesRegex(SkillManagerError, expected):
                        validate_draft(aiws_root, record_id)

                    self.assert_no_proposals(aiws_root)
                    loaded = load_draft_record(aiws_root, record_id)
                    self.assertEqual(loaded.last_validation_status, "failed")
                    self.assertIsNone(loaded.last_validation_tree_digest)
                    self.assertTrue(loaded.modified)

    def test_stage_proposal_writes_local_proposal_and_preserves_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")

            result = stage_proposal(
                aiws_root,
                record_id,
                "  Cowork shared skill  ",
                "  ai-workspace-skills-review  ",
                "  Improve meeting follow-up  ",
                "  The current instructions miss owner handoffs.  ",
            )

            self.assertEqual(result["status"], "staged")
            self.assertEqual(result["draft_id"], record_id)
            self.assertEqual(result["plugin_id"], "example-plugin")
            self.assertEqual(result["skill_id"], "meeting-followup")
            self.assertEqual(result["target_scope"], "Cowork shared skill")
            self.assertEqual(result["target_repo"], "ai-workspace-skills-review")
            self.assertEqual(result["next_action"], "submit_for_review")
            proposal_path = Path(result["proposal_path"])
            self.assertEqual(proposal_path.parent, aiws_root / "state" / "skill-proposals")
            self.assertTrue(proposal_path.is_file())

            proposal = json.loads(proposal_path.read_text())
            current_digest = tree_digest(Path(record.draft_path))
            self.assertEqual(proposal["proposal_id"], result["proposal_id"])
            self.assertEqual(proposal["draft_id"], record_id)
            self.assertNotIn("record_id", proposal)
            self.assertEqual(proposal["plugin_id"], "example-plugin")
            self.assertEqual(proposal["skill_id"], "meeting-followup")
            self.assertEqual(proposal["origin_marketplace"], "ai-workspace")
            self.assertEqual(proposal["origin_repo"], "https://github.com/example/example-plugin")
            self.assertEqual(proposal["origin_ref"], "master")
            self.assertEqual(proposal["base_version"], "1.0.0")
            self.assertEqual(proposal["base_commit"], "abc123")
            self.assertEqual(proposal["draft_path"], record.draft_path)
            self.assertEqual(proposal["base_tree_digest"], record.base_tree_digest)
            self.assertEqual(proposal["current_tree_digest"], current_digest)
            self.assertEqual(proposal["validation_status"], "passed")
            self.assertEqual(proposal["validation_tree_digest"], current_digest)
            self.assertEqual(proposal["target_scope"], "Cowork shared skill")
            self.assertEqual(proposal["target_repo"], "ai-workspace-skills-review")
            self.assertEqual(proposal["summary"], "Improve meeting follow-up")
            self.assertEqual(proposal["rationale"], "The current instructions miss owner handoffs.")
            self.assertTrue(proposal["active"])
            self.assertTrue(proposal["modified"])
            self.assertEqual(proposal["status"], "staged")
            self.assertIsNone(proposal["branch_name"])
            self.assertIsNone(proposal["pr_url"])

            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "passed")
            self.assertEqual(loaded.last_validation_tree_digest, current_digest)
            self.assertEqual(loaded.current_tree_digest, current_digest)

    def test_stage_proposal_allows_separate_target_repos_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")

            first = stage_proposal(aiws_root, record_id, "Cowork", "review-repo-one", "Summary", "Rationale")
            second = stage_proposal(aiws_root, record_id, "Cowork", "review-repo-two", "Summary", "Rationale")

            self.assertNotEqual(first["proposal_id"], second["proposal_id"])
            self.assertNotEqual(first["proposal_path"], second["proposal_path"])
            proposals = self.proposal_payloads(aiws_root)
            self.assertEqual({proposal["target_repo"] for proposal in proposals}, {"review-repo-one", "review-repo-two"})

    def test_stage_proposal_rejects_blank_or_non_string_required_fields(self) -> None:
        cases = [
            ("record_id", " "),
            ("record_id", 123),
            ("target_scope", " "),
            ("target_scope", None),
            ("target_repo", " "),
            ("target_repo", {"repo": "review"}),
            ("summary", "\t"),
            ("summary", ["summary"]),
            ("rationale", "\n"),
            ("rationale", False),
        ]
        for field, bad_value in cases:
            with self.subTest(field=field, value=bad_value):
                with tempfile.TemporaryDirectory() as temp:
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
                    self.edit_draft_skill(record, "\nLocal proposal edit.\n")
                    args = {
                        "record_id": record_id,
                        "target_scope": "Cowork",
                        "target_repo": "review-repo",
                        "summary": "Summary",
                        "rationale": "Rationale",
                    }
                    args[field] = bad_value

                    with self.assertRaisesRegex(SkillManagerError, "must be a non-blank string"):
                        stage_proposal(
                            aiws_root,
                            args["record_id"],
                            args["target_scope"],
                            args["target_repo"],
                            args["summary"],
                            args["rationale"],
                        )

                    self.assert_no_proposals(aiws_root)

    def test_stage_proposal_rejects_unchanged_draft_and_marks_validation_failed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, _record = self.create_meeting_followup_draft(Path(temp))

            with self.assertRaisesRegex(SkillManagerError, "does not differ from its base"):
                stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assert_no_proposals(aiws_root)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertIsNone(loaded.last_validation_tree_digest)

    def test_stage_proposal_rejects_changes_outside_requested_skill_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            contract = Path(record.draft_path) / "contracts" / "example-plugin.contract.json"
            contract.write_text(contract.read_text() + "\n")

            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assert_no_proposals(aiws_root)

    def test_stage_proposal_rejects_legacy_record_missing_base_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            payload = json.loads(record_path.read_text())
            payload.pop("base_tree_digest")
            record_path.write_text(json.dumps(payload))

            with self.assertRaisesRegex(SkillManagerError, "base_tree_digest"):
                stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assert_no_proposals(aiws_root)
            loaded = load_draft_record(aiws_root, record_id)
            self.assertEqual(loaded.last_validation_status, "failed")
            self.assertIsNone(loaded.last_validation_tree_digest)

    def test_stage_proposal_invalid_plugin_or_missing_skill_writes_no_proposal_and_marks_failed(self) -> None:
        for breakage in ("invalid-plugin", "missing-skill"):
            with self.subTest(breakage=breakage):
                with tempfile.TemporaryDirectory() as temp:
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
                    self.edit_draft_skill(record, "\nLocal proposal edit.\n")
                    draft_root = Path(record.draft_path)
                    if breakage == "invalid-plugin":
                        manifest_path = draft_root / ".claude-plugin" / "plugin.json"
                        manifest = json.loads(manifest_path.read_text())
                        manifest["name"] = "other-plugin"
                        manifest_path.write_text(json.dumps(manifest))
                    else:
                        (draft_root / "skills" / "meeting-followup" / "SKILL.md").unlink()

                    with self.assertRaises(SkillManagerError):
                        stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

                    self.assert_no_proposals(aiws_root)
                    loaded = load_draft_record(aiws_root, record_id)
                    self.assertEqual(loaded.last_validation_status, "failed")
                    self.assertIsNone(loaded.last_validation_tree_digest)

    def test_stage_proposal_revalidates_current_tree_after_prior_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nFirst local edit.\n")
            first = stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")
            first_payload = json.loads(Path(first["proposal_path"]).read_text())

            self.edit_draft_skill(record, "\nSecond local edit after validation.\n")
            second = stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary again", "Rationale again")
            second_payload = json.loads(Path(second["proposal_path"]).read_text())
            current_digest = tree_digest(Path(record.draft_path))

            self.assertNotEqual(first_payload["validation_tree_digest"], current_digest)
            self.assertEqual(second_payload["validation_tree_digest"], current_digest)
            self.assertEqual(load_draft_record(aiws_root, record_id).last_validation_tree_digest, current_digest)

    def test_stage_proposal_rejects_canonical_draft_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            wrong_record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/other-plugin")
            wrong_path = aiws_root / "state" / "skill-drafts" / f"{wrong_record_id}.json"
            wrong_path.write_text((aiws_root / "state" / "skill-drafts" / f"{record_id}.json").read_text())

            with self.assertRaisesRegex(SkillManagerError, "canonical draft id"):
                stage_proposal(aiws_root, wrong_record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assert_no_proposals(aiws_root)

    def test_stage_proposal_never_overwrites_existing_proposal_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            proposal_root = aiws_root / "state" / "skill-proposals"
            proposal_root.mkdir(parents=True)
            planted = proposal_root / "skillprop_collision.json"
            planted.write_text('{"keep": true}\n')

            with mock.patch(
                "aiws_mcp.skill_manager.uuid.uuid4",
                side_effect=[mock.Mock(hex="collision"), mock.Mock(hex="collision"), mock.Mock(hex="fresh")],
            ):
                result = stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assertEqual(json.loads(planted.read_text()), {"keep": True})
            self.assertEqual(result["proposal_id"], "skillprop_fresh")
            self.assertTrue((proposal_root / "skillprop_fresh.json").is_file())

    def test_stage_proposal_rejects_symlinked_proposal_root_final_and_tmp_paths(self) -> None:
        for planted in ("root", "final", "tmp"):
            with self.subTest(planted=planted):
                with tempfile.TemporaryDirectory() as temp:
                    temp_root = Path(temp)
                    aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
                    self.edit_draft_skill(record, "\nLocal proposal edit.\n")
                    proposal_root = aiws_root / "state" / "skill-proposals"
                    external = temp_root / "external-proposals"
                    external.mkdir()
                    outside = temp_root / "outside.json"
                    outside.write_text("outside\n")
                    if planted == "root":
                        proposal_root.symlink_to(external, target_is_directory=True)
                        expected = "must not be a symlink"
                    else:
                        proposal_root.mkdir(parents=True)
                        proposal_path = proposal_root / "skillprop_blocked.json"
                        if planted == "final":
                            proposal_path.symlink_to(outside)
                            expected = "Proposal path must not be a symlink"
                        else:
                            proposal_path.with_suffix(proposal_path.suffix + ".tmp").symlink_to(outside)
                            expected = "Proposal temporary path must not be a symlink"

                    with mock.patch("aiws_mcp.skill_manager.uuid.uuid4", return_value=mock.Mock(hex="blocked")):
                        with self.assertRaisesRegex(SkillManagerError, expected):
                            stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

                    self.assertEqual(outside.read_text(), "outside\n")
                    if planted == "root":
                        self.assertEqual(list(external.iterdir()), [])

    def test_stage_proposal_writes_only_local_draft_and_proposal_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")

            stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")

            self.assertTrue((aiws_root / "state" / "skill-drafts" / f"{record_id}.json").is_file())
            self.assertEqual(len(self.proposal_payloads(aiws_root)), 1)
            self.assertFalse((aiws_root / "hosts").exists())
            self.assertFalse((aiws_root / "memory").exists())
            self.assertFalse((aiws_root / "imports").exists())
            self.assertFalse((aiws_root / "exports").exists())
            self.assertFalse((aiws_root / "rpm").exists())
            self.assertFalse((aiws_root / "packages").exists())
            self.assertFalse((aiws_root / "managed-plugins").exists())
            self.assertFalse((temp_root / ".claude").exists())

    def test_discover_installed_plugins_finds_single_match_and_reports_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            first_root = temp_root / "uploads" / "one"
            plugin_root = self.write_plugin(first_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            found = discover_installed_plugins(plugin_id="example-plugin", search_roots=[first_root])
            self.assertEqual(found["status"], "ok")
            self.assertEqual(len(found["plugins"]), 1)
            self.assertEqual(found["plugins"][0]["plugin_id"], "example-plugin")
            self.assertEqual(found["plugins"][0]["base_version"], "1.0.0")

            second_root = temp_root / "uploads" / "two"
            other_plugin = self.write_plugin(second_root, public_skills=["meeting-followup"])
            self.write_skill(other_plugin, "meeting-followup")
            ambiguous = discover_installed_plugins(plugin_id="example-plugin", search_roots=[temp_root / "uploads"])

            self.assertEqual(ambiguous["status"], "ambiguous_installed_plugin")
            self.assertEqual(len(ambiguous["plugins"]), 2)

            missing = discover_installed_plugins(plugin_id="missing-plugin", search_roots=[first_root])
            self.assertEqual(missing["status"], "installed_plugin_not_found")

    def test_submit_pr_submits_staged_proposal_and_persists_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record, staged = self.create_staged_meeting_followup_proposal(Path(temp))
            submitter = FakeProposalSubmitter()

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            expected_branch = f"aiws/skill-proposals/{staged['proposal_id']}"
            self.assertEqual(result["status"], "submitted_for_review")
            self.assertEqual(result["status_label"], "Submitted for review")
            self.assertEqual(result["proposal_id"], staged["proposal_id"])
            self.assertEqual(result["draft_id"], record_id)
            self.assertEqual(result["target_repo"], "review-repo")
            self.assertEqual(result["branch_name"], expected_branch)
            self.assertEqual(result["pr_url"], "https://github.com/example/review/pull/123")
            self.assertEqual(len(submitter.calls), 1)
            self.assertEqual(submitter.calls[0]["branch_name"], expected_branch)
            self.assertEqual(submitter.calls[0]["target_repo"], "review-repo")
            self.assertEqual(submitter.calls[0]["draft_path"], record.draft_path)
            self.assertEqual(submitter.calls[0]["validation_tree_digest"], tree_digest(Path(record.draft_path)))
            self.assertNotIn("required_review_roles", submitter.calls[0])

            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "submitted_for_review")
            self.assertEqual(proposal["branch_name"], expected_branch)
            self.assertEqual(proposal["pr_url"], "https://github.com/example/review/pull/123")
            self.assertNotIn("required_review_roles", proposal)
            self.assertIn("submitted_at", proposal)

            loaded = load_draft_record(aiws_root, record_id)
            self.assertIsNone(loaded.branch_name)
            self.assertIsNone(loaded.pr_url)

    def test_submit_pr_already_submitted_proposal_returns_existing_metadata_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            first_submitter = FakeProposalSubmitter()
            first = submit_pr(aiws_root, staged["proposal_id"], first_submitter)
            second_submitter = FakeProposalSubmitter()

            second = submit_pr(aiws_root, staged["proposal_id"], second_submitter)

            self.assertEqual(second["status"], "submitted_for_review")
            self.assertEqual(second["branch_name"], first["branch_name"])
            self.assertEqual(second["pr_url"], first["pr_url"])
            self.assertEqual(second_submitter.calls, [])

    def test_submit_pr_strips_stale_review_roles_from_normal_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["required_review_roles"] = ["AI engineer"]
            proposal_path.write_text(json.dumps(proposal))
            submitter = FakeProposalSubmitter()

            submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertNotIn("required_review_roles", submitter.calls[0])
            self.assertNotIn("required_review_roles", self.proposal_payload(aiws_root, staged["proposal_id"]))

    def test_submit_pr_preserves_explicit_product_specific_review_roles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            submitter = FakeProposalSubmitter()

            submit_pr(aiws_root, staged["proposal_id"], submitter, required_review_roles=["Skill maintainer"])

            self.assertEqual(submitter.calls[0]["required_review_roles"], ["Skill maintainer"])
            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["required_review_roles"], ["Skill maintainer"])

    def test_submit_pr_already_submitted_proposal_still_honors_target_repo_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            submit_pr(aiws_root, staged["proposal_id"], FakeProposalSubmitter())
            second_submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "target_repo is not allowed"):
                submit_pr(aiws_root, staged["proposal_id"], second_submitter, allowed_target_repos=["other-repo"])

            self.assertEqual(second_submitter.calls, [])

    def test_submit_pr_rejects_incomplete_submitted_metadata_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["status"] = "submitted_for_review"
            proposal["branch_name"] = "aiws/skill-proposals/" + staged["proposal_id"]
            proposal["pr_url"] = None
            proposal_path.write_text(json.dumps(proposal))
            submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "submitted proposal metadata is incomplete"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_rejects_missing_proposal_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "Proposal record not found"):
                submit_pr(Path(temp) / ".aiws", "skillprop_missing", submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_rejects_failed_validation_proposal_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["validation_status"] = "failed"
            proposal_path.write_text(json.dumps(proposal))
            submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "validation status is not passed"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_rejects_post_stage_draft_edits_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, record, staged = self.create_staged_meeting_followup_proposal(Path(temp))
            self.edit_draft_skill(record, "\nEdit after staging.\n")
            submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "changed since staging"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"])["status"], "staged")

    def test_submit_pr_rejects_invalid_draft_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, record, staged = self.create_staged_meeting_followup_proposal(Path(temp))
            skill_path = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            skill_path.unlink()
            submitter = FakeProposalSubmitter()

            with self.assertRaises(SkillManagerError):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"])["status"], "staged")

    def test_submit_pr_submitter_failure_leaves_proposal_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            before = self.proposal_payload(aiws_root, staged["proposal_id"])
            submitter = FakeProposalSubmitter(error=RuntimeError("remote unavailable"))

            with self.assertRaisesRegex(RuntimeError, "remote unavailable"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"]), before)

    def test_submit_pr_invalid_submitter_metadata_leaves_proposal_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            before = self.proposal_payload(aiws_root, staged["proposal_id"])
            submitter = FakeProposalSubmitter(response={"branch_name": " ", "pr_url": ""})

            with self.assertRaisesRegex(SkillManagerError, "submitter returned invalid review metadata"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"]), before)

    def test_submit_pr_rejects_target_repo_outside_allowlist_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            submitter = FakeProposalSubmitter()

            with self.assertRaisesRegex(SkillManagerError, "target_repo is not allowed"):
                submit_pr(aiws_root, staged["proposal_id"], submitter, allowed_target_repos=["other-repo"])

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_no_gh_handoff_preserves_staged_proposal_after_gates_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            before = self.proposal_payload(aiws_root, staged["proposal_id"])
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            result = submit_pr(aiws_root, staged["proposal_id"], submitter, allowed_target_repos=["review-repo"])

            expected_branch = f"aiws/skill-proposals/{staged['proposal_id']}"
            self.assertEqual(result["status"], "submit_handoff_required")
            self.assertEqual(result["reason_code"], "github_cli_unavailable")
            self.assertEqual(result["proposal_id"], staged["proposal_id"])
            self.assertEqual(result["draft_id"], record_id)
            self.assertEqual(result["target_repo"], "review-repo")
            self.assertEqual(result["branch_name"], expected_branch)
            self.assertFalse(result["terminal"])
            self.assertTrue(result["no_pr_created"])
            self.assertNotIn("required_review_roles", result)
            self.assertGreaterEqual(len(result["actions"]), 1)
            self.assertEqual(len(submitter.calls), 1)
            self.assertEqual(submitter.calls[0]["branch_name"], expected_branch)
            self.assertNotIn("required_review_roles", submitter.calls[0])
            self.assertNotIn("required_review_roles", result["actions"][0])
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"]), before)

    def test_submit_pr_no_gh_handoff_rejects_allowlist_mismatch_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            with self.assertRaisesRegex(SkillManagerError, "target_repo is not allowed"):
                submit_pr(aiws_root, staged["proposal_id"], submitter, allowed_target_repos=["other-repo"])

            self.assertEqual(submitter.calls, [])
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"])["status"], "staged")

    def test_submit_pr_no_gh_handoff_rejects_digest_divergence_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            self.edit_draft_skill(record, "\nEdit after staging.\n")
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            with self.assertRaisesRegex(SkillManagerError, "changed since staging"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])
            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "staged")
            self.assertIsNone(proposal["branch_name"])
            self.assertIsNone(proposal["pr_url"])

    def test_submit_pr_no_gh_handoff_rejects_non_staged_proposal_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["status"] = "draft"
            proposal_path.write_text(json.dumps(proposal))
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            with self.assertRaisesRegex(SkillManagerError, "not staged for review"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_no_gh_handoff_rejects_failed_validation_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["validation_status"] = "failed"
            proposal_path.write_text(json.dumps(proposal))
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            with self.assertRaisesRegex(SkillManagerError, "validation status is not passed"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_no_gh_handoff_rejects_out_of_scope_changes_before_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            draft_path = Path(record.draft_path)
            (draft_path / "plugin.yaml").write_text("name: outside-skill\n")
            proposal_path = Path(staged["proposal_path"])
            proposal = json.loads(proposal_path.read_text())
            proposal["validation_tree_digest"] = tree_digest(draft_path)
            proposal_path.write_text(json.dumps(proposal))
            submitter = RecordingHandoffSubmitter(aiws_root=aiws_root)

            with self.assertRaisesRegex(SkillManagerError, "outside the managed skill folder"):
                submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(submitter.calls, [])

    def test_submit_pr_writes_only_local_proposal_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                temp_root
            )

            submit_pr(aiws_root, staged["proposal_id"], FakeProposalSubmitter())

            self.assertEqual(len(self.proposal_payloads(aiws_root)), 1)
            self.assertFalse((aiws_root / "hosts").exists())
            self.assertFalse((aiws_root / "memory").exists())
            self.assertFalse((aiws_root / "imports").exists())
            self.assertFalse((aiws_root / "exports").exists())
            self.assertFalse((aiws_root / "rpm").exists())
            self.assertFalse((aiws_root / "packages").exists())
            self.assertFalse((aiws_root / "managed-plugins").exists())
            self.assertFalse((temp_root / ".claude").exists())

    def test_default_command_runner_disables_prompts_and_detaches_stdin(self) -> None:
        completed = subprocess.CompletedProcess(["gh", "pr", "list"], 0, "", "")
        with mock.patch("aiws_mcp.skill_manager.subprocess.run", return_value=completed) as run:
            with mock.patch.dict(os.environ, {"AIWS_KEEP": "yes", "GH_PROMPT_DISABLED": "0"}, clear=True):
                result = default_command_runner(["gh", "pr", "list"], cwd=Path("/tmp"))

        self.assertIs(result, completed)
        run.assert_called_once()
        _args, kwargs = run.call_args
        self.assertEqual(kwargs["cwd"], Path("/tmp"))
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["env"]["AIWS_KEEP"], "yes")
        self.assertEqual(kwargs["env"]["GH_PROMPT_DISABLED"], "1")
        self.assertEqual(kwargs["timeout"], DEFAULT_COMMAND_TIMEOUT_SECONDS)
        self.assertIs(kwargs["stdout"], subprocess.PIPE)
        self.assertIs(kwargs["stderr"], subprocess.PIPE)
        self.assertFalse(kwargs["check"])

    def test_gh_submitter_syncs_only_skill_folder_and_creates_non_draft_pr_without_reviewers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                temp_root
            )
            self.set_proposal_target_repo(aiws_root, staged["proposal_id"], "example/review")
            target_repo = temp_root / "target-repo"
            target_repo.mkdir()
            self.write_plugin(target_repo, public_skills=["meeting-followup"])
            self.write_skill(target_repo / "example-plugin", "meeting-followup").write_text(
                "---\nname: meeting-followup\ndescription: Old skill.\n---\n\n# Old\n"
            )
            (target_repo / "README.md").write_text("keep\n")
            runner = FakeCommandRunner(target_repo)
            submitter = GhCliProposalSubmitter(aiws_root=aiws_root, runner=runner)

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(result["status"], "submitted_for_review")
            self.assertEqual(result["pr_url"], "https://github.com/example/review/pull/7")
            command_lines = [" ".join(call[0]) for call in runner.calls]
            pr_create = next(command for command in command_lines if command.startswith("gh pr create"))
            self.assertIn("--repo example/review", pr_create)
            self.assertIn("--base main", pr_create)
            self.assertIn("--head aiws/skill-proposals/", pr_create)
            self.assertNotIn("--draft", pr_create)
            self.assertNotIn("--reviewer", pr_create)
            git_add = next(command for command in command_lines if command.startswith("git add"))
            self.assertIn("example-plugin/skills/meeting-followup", git_add)

            clone_dir = aiws_root / "state" / "git-worktrees" / "example__review" / staged["proposal_id"] / "repo"
            self.assertEqual((clone_dir / "README.md").read_text(), "keep\n")
            self.assertIn("Local proposal edit.", (clone_dir / "example-plugin" / "skills" / "meeting-followup" / "SKILL.md").read_text())
            body_files = [
                Path(call[0][call[0].index("--body-file") + 1])
                for call in runner.calls
                if call[0][:3] == ["gh", "pr", "create"]
            ]
            body = body_files[0].read_text()
            self.assertIn("CODEOWNERS: not_detected", body)
            self.assertIn("Review and merge are managed by the target repository's maintainers and policies.", body)
            self.assertNotIn("Required review role", body)
            self.assertNotIn("AI engineer", body)

    def test_gh_submitter_no_changes_keeps_proposal_staged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                temp_root
            )
            self.set_proposal_target_repo(aiws_root, staged["proposal_id"], "example/review")
            target_repo = temp_root / "target-repo"
            target_repo.mkdir()
            self.write_plugin(target_repo, public_skills=["meeting-followup"])
            self.write_skill(target_repo / "example-plugin", "meeting-followup")
            runner = FakeCommandRunner(target_repo, no_changes=True)
            submitter = GhCliProposalSubmitter(aiws_root=aiws_root, runner=runner)

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(result["status"], "no_changes_to_submit")
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"])["status"], "staged")

    def test_gh_submitter_reuses_existing_pr_only_after_refreshing_body_and_marking_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                temp_root
            )
            self.set_proposal_target_repo(aiws_root, staged["proposal_id"], "example/review")
            target_repo = temp_root / "target-repo"
            target_repo.mkdir()
            self.write_plugin(target_repo, public_skills=["meeting-followup"])
            self.write_skill(target_repo / "example-plugin", "meeting-followup")
            (target_repo / ".github").mkdir()
            (target_repo / ".github" / "CODEOWNERS").write_text("* @example/ai-engineers\n")
            runner = FakeCommandRunner(
                target_repo,
                existing_pr_url="https://github.com/example/review/pull/7",
                existing_pr_is_draft=True,
            )
            submitter = GhCliProposalSubmitter(aiws_root=aiws_root, runner=runner)

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(result["status"], "submitted_for_review")
            command_lines = [" ".join(call[0]) for call in runner.calls]
            self.assertTrue(any(command.startswith("gh pr ready ") for command in command_lines))
            edit_command = next(command for command in command_lines if command.startswith("gh pr edit "))
            self.assertIn("--body-file", edit_command)
            self.assertNotIn("--reviewer", edit_command)
            body_files = [
                Path(call[0][call[0].index("--body-file") + 1])
                for call in runner.calls
                if call[0][:3] == ["gh", "pr", "edit"]
            ]
            body = body_files[0].read_text()
            self.assertIn("CODEOWNERS: detected", body)
            self.assertIn("Review and merge are managed by the target repository's maintainers and policies.", body)
            self.assertNotIn("Required review role", body)
            self.assertNotIn("AI engineer", body)

    def test_create_or_open_draft_reopens_existing_draft_without_overwriting_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            skill_file = self.write_skill(plugin_root, "meeting-followup")

            record = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )
            draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
            draft_skill.write_text(draft_skill.read_text() + "\nLocal draft edit.\n")
            skill_file.write_text(skill_file.read_text() + "\nUpstream source edit that must not overwrite.\n")

            reopened = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )

            self.assertEqual(Path(reopened.draft_path), Path(record.draft_path))
            self.assertIn("Local draft edit.", draft_skill.read_text())
            self.assertNotIn("Upstream source edit", draft_skill.read_text())

    def test_create_or_open_draft_rejects_orphaned_draft_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")
            orphan = (
                aiws_root
                / "plugins"
                / "ai-workspace"
                / f"example-plugin-{draft_id('example-plugin', 'meeting-followup', 'https://github.com/example/example-plugin').rsplit('--', 1)[1]}"
            )
            orphan.mkdir(parents=True)

            with self.assertRaisesRegex(SkillManagerError, "already exists without a usable record"):
                create_or_open_draft(
                    aiws_root,
                    source_plugin_root=plugin_root,
                    plugin_id="example-plugin",
                    skill_id="meeting-followup",
                    origin_marketplace="ai-workspace",
                    origin_repo="https://github.com/example/example-plugin",
                    origin_ref="master",
                    base_version="1.0.0",
                    base_commit="abc123",
                )

            self.assertTrue(orphan.exists())

    def test_revert_draft_removes_draft_files_and_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            record = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/example-plugin",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")

            result = revert_draft(aiws_root, record_id)

            self.assertEqual(result["status"], "reverted")
            self.assertFalse(Path(record.draft_path).exists())
            self.assertFalse((aiws_root / "state" / "skill-drafts" / f"{record_id}.json").exists())
            self.assertTrue((aiws_root / "plugins").exists())

    def test_revert_draft_refuses_paths_outside_aiws_draft_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            outside = temp_root / "outside-plugin"
            outside.mkdir()
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            record = {
                "plugin_id": "example-plugin",
                "skill_id": "meeting-followup",
                "origin_marketplace": "ai-workspace",
                "origin_repo": "https://github.com/example/example-plugin",
                "origin_ref": "master",
                "base_version": "1.0.0",
                "base_commit": "abc123",
                "draft_path": str(outside),
                "active": True,
                "modified": False,
                "publish_target": None,
                "branch_name": None,
                "pr_url": None,
                "last_validation_status": "passed",
                "updated_at": "2026-05-09T00:00:00Z",
            }
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(record))

            with self.assertRaisesRegex(SkillManagerError, "outside AIWS draft plugin root"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(outside.exists())
            self.assertTrue(record_path.exists())

    def test_revert_draft_refuses_symlinked_plugins_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            external_plugins = temp_root / "external-plugins"
            external_plugins.mkdir()
            (aiws_root).mkdir()
            (aiws_root / "plugins").symlink_to(external_plugins, target_is_directory=True)
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            draft = external_plugins / "ai-workspace" / f"example-plugin-{record_id.rsplit('--', 1)[1]}"
            draft.mkdir(parents=True)
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(self.draft_record_payload(draft)))

            with self.assertRaisesRegex(SkillManagerError, "must not be a symlink"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(draft.exists())
            self.assertTrue(record_path.exists())

    def test_revert_draft_rejects_traversal_record_id_before_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            escaped_record = aiws_root / "state" / "outside.json"
            escaped_record.parent.mkdir(parents=True)
            escaped_record.write_text(json.dumps({"draft_path": str(aiws_root / "plugins" / "ai-workspace" / "x")}))

            with self.assertRaisesRegex(SkillManagerError, "outside AIWS draft state root"):
                revert_draft(aiws_root, "../outside")

            self.assertTrue(escaped_record.exists())

    def test_revert_draft_refuses_symlinked_state_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            external_state = temp_root / "external-state"
            external_state.mkdir()
            aiws_root.mkdir()
            (aiws_root / "state").symlink_to(external_state, target_is_directory=True)
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            external_record = external_state / "skill-drafts" / f"{record_id}.json"
            external_record.parent.mkdir()
            external_record.write_text(
                json.dumps(
                    self.draft_record_payload(
                        aiws_root / "plugins" / "ai-workspace" / f"example-plugin-{record_id.rsplit('--', 1)[1]}"
                    )
                )
            )

            with self.assertRaisesRegex(SkillManagerError, "must not be a symlink"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(external_record.exists())

    def test_revert_draft_refuses_non_deterministic_draft_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            marketplace_root = aiws_root / "plugins" / "ai-workspace"
            marketplace_root.mkdir(parents=True)
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(self.draft_record_payload(marketplace_root)))

            with self.assertRaisesRegex(SkillManagerError, "unexpected draft path"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(marketplace_root.exists())
            self.assertTrue(record_path.exists())

    def test_revert_draft_refuses_deterministic_draft_path_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            marketplace_root = aiws_root / "plugins" / "ai-workspace"
            target = marketplace_root / "other-draft"
            target.mkdir(parents=True)
            deterministic = marketplace_root / f"example-plugin-{record_id.rsplit('--', 1)[1]}"
            deterministic.symlink_to(target, target_is_directory=True)
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(self.draft_record_payload(deterministic)))

            with self.assertRaisesRegex(SkillManagerError, "must not contain symlinks"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(target.exists())
            self.assertTrue(deterministic.is_symlink())
            self.assertTrue(record_path.exists())

    def test_revert_draft_refuses_plugins_root_as_draft_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugins_root = aiws_root / "plugins"
            plugins_root.mkdir(parents=True)
            record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
            record = {
                "plugin_id": "example-plugin",
                "skill_id": "meeting-followup",
                "origin_marketplace": "ai-workspace",
                "origin_repo": "https://github.com/example/example-plugin",
                "origin_ref": "master",
                "base_version": "1.0.0",
                "base_commit": "abc123",
                "draft_path": str(plugins_root),
                "active": True,
                "modified": False,
                "publish_target": None,
                "branch_name": None,
                "pr_url": None,
                "last_validation_status": "passed",
                "updated_at": "2026-05-09T00:00:00Z",
            }
            record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
            record_path.parent.mkdir(parents=True)
            record_path.write_text(json.dumps(record))

            with self.assertRaisesRegex(SkillManagerError, "outside AIWS draft plugin root"):
                revert_draft(aiws_root, record_id)

            self.assertTrue(plugins_root.exists())
            self.assertTrue(record_path.exists())

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

    def write_skill(self, plugin_root: Path, name: str) -> Path:
        skill_root = plugin_root / "skills" / name
        skill_root.mkdir(parents=True)
        skill_file = skill_root / "SKILL.md"
        skill_file.write_text(f"---\nname: {name}\ndescription: Test skill.\n---\n\n# Test Skill\n")
        return skill_file

    def create_meeting_followup_draft(self, temp_root: Path) -> tuple[Path, str, Path, object]:
        aiws_root = temp_root / ".aiws"
        plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
        self.write_skill(plugin_root, "meeting-followup")
        record = create_or_open_draft(
            aiws_root,
            source_plugin_root=plugin_root,
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            origin_marketplace="ai-workspace",
            origin_repo="https://github.com/example/example-plugin",
            origin_ref="master",
            base_version="1.0.0",
            base_commit="abc123",
        )
        record_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/example-plugin")
        return aiws_root, record_id, plugin_root, record

    def create_staged_meeting_followup_proposal(
        self, temp_root: Path
    ) -> tuple[Path, str, Path, object, dict[str, object]]:
        aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
        self.edit_draft_skill(record, "\nLocal proposal edit.\n")
        staged = stage_proposal(aiws_root, record_id, "Cowork", "review-repo", "Summary", "Rationale")
        return aiws_root, record_id, plugin_root, record, staged

    def assert_no_package_artifacts(self, package_dir: Path) -> None:
        if not package_dir.exists():
            return
        self.assertFalse(any(path.suffix in {".zip", ".tmp"} for path in package_dir.iterdir()))

    def assert_no_proposals(self, aiws_root: Path) -> None:
        proposal_root = aiws_root / "state" / "skill-proposals"
        if not proposal_root.exists():
            return
        self.assertEqual(list(proposal_root.iterdir()), [])

    def proposal_payloads(self, aiws_root: Path) -> list[dict[str, object]]:
        proposal_root = aiws_root / "state" / "skill-proposals"
        return [json.loads(path.read_text()) for path in sorted(proposal_root.glob("*.json"))]

    def proposal_payload(self, aiws_root: Path, proposal_id: str) -> dict[str, object]:
        return json.loads((aiws_root / "state" / "skill-proposals" / f"{proposal_id}.json").read_text())

    def edit_draft_skill(self, record: object, content: str) -> None:
        draft_skill = Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md"
        draft_skill.write_text(draft_skill.read_text() + content)

    def set_record_validation_status(self, aiws_root: Path, record_id: str, status: str) -> None:
        record_path = aiws_root / "state" / "skill-drafts" / f"{record_id}.json"
        payload = json.loads(record_path.read_text())
        payload["last_validation_status"] = status
        record_path.write_text(json.dumps(payload))

    def set_proposal_target_repo(self, aiws_root: Path, proposal_id: str, target_repo: str) -> None:
        proposal_path = aiws_root / "state" / "skill-proposals" / f"{proposal_id}.json"
        payload = json.loads(proposal_path.read_text())
        payload["target_repo"] = target_repo
        proposal_path.write_text(json.dumps(payload))

    def draft_record_payload(self, draft_path: Path) -> dict[str, object]:
        return {
            "plugin_id": "example-plugin",
            "skill_id": "meeting-followup",
            "origin_marketplace": "ai-workspace",
            "origin_repo": "https://github.com/example/example-plugin",
            "origin_ref": "master",
            "base_version": "1.0.0",
            "base_commit": "abc123",
            "draft_path": str(draft_path),
            "active": True,
            "modified": False,
            "publish_target": None,
            "branch_name": None,
            "pr_url": None,
            "last_validation_status": "passed",
            "updated_at": "2026-05-09T00:00:00Z",
        }


if __name__ == "__main__":
    unittest.main()
