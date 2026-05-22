from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
import io
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp.runtime import AiwsRuntime, SkillValidationError  # noqa: E402
import aiws_mcp.runtime as runtime_module  # noqa: E402


class FakeRuntimeGoogleDriveClient:
    def __init__(
        self,
        package_bytes: bytes,
        *,
        current_version: str = "1.0.1",
        package_file_id: str = "package-file-1",
    ) -> None:
        self.package_bytes = package_bytes
        self.current_version = current_version
        self.package_file_id = package_file_id

    def find_child(self, parent_id: str, name: str, *, mime_type: str | None = None):
        if parent_id == "drive-root-1" and name == "plugins":
            return {"id": "plugins-folder", "name": "plugins", "mimeType": "application/vnd.google-apps.folder"}
        if parent_id == "plugin-folder-1" and name == "index.json":
            return {"id": "index-file-1", "name": "index.json", "mimeType": "application/json"}
        return None

    def list_children(self, parent_id: str, *, mime_type: str | None = None):
        if parent_id == "plugins-folder":
            return [{"id": "plugin-folder-1", "name": "example-plugin", "mimeType": "application/vnd.google-apps.folder"}]
        return []

    def read_text_file(self, file_id: str) -> str:
        if file_id == "index-file-1":
            return json.dumps(
                {
                    "plugin_id": "example-plugin",
                    "marketplace_id": "checkout-main-real",
                    "current_version": self.current_version,
                    "package_file_id": self.package_file_id,
                }
            )
        raise AssertionError(f"Unexpected read_text_file: {file_id}")

    def download_file_bytes(self, file_id: str) -> bytes:
        if file_id != self.package_file_id:
            raise AssertionError(f"Unexpected download_file_bytes: {file_id}")
        return self.package_bytes


class MixedRuntimeGoogleDriveClient(FakeRuntimeGoogleDriveClient):
    def find_child(self, parent_id: str, name: str, *, mime_type: str | None = None):
        if parent_id == "stale-drive-root":
            raise runtime_module.skill_manager.SkillManagerError("Google Drive API request failed (404): File not found: .")
        return super().find_child(parent_id, name, mime_type=mime_type)


class AiwsMcpSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name) / ".aiws"
        self.claude_home = Path(self.tempdir.name) / ".claude"
        self.cowork_home = Path(self.tempdir.name) / ".cowork"
        self.codex_home = Path(self.tempdir.name) / ".codex"
        self.env = {
            "CLAUDE_HOME": str(self.claude_home),
            "COWORK_HOME": str(self.cowork_home),
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

    def write_cowork_plugin(
        self,
        root: Path,
        *,
        plugin_id: str = "example-plugin",
        version: str = "0.1.0",
        skill_id: str = "meeting-followup",
    ) -> Path:
        plugin_root = root / plugin_id
        skill_root = plugin_root / "skills" / skill_id
        skill_root.mkdir(parents=True)
        (plugin_root / ".claude-plugin").mkdir()
        (plugin_root / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(
                {
                    "name": plugin_id,
                    "description": "Example Cowork plugin.",
                    "version": version,
                },
                sort_keys=True,
            )
            + "\n"
        )
        (plugin_root / "contracts").mkdir()
        (plugin_root / "contracts" / f"{plugin_id}.contract.json").write_text(
            json.dumps(
                {
                    "plugin_id": plugin_id,
                    "version": version,
                    "public_skills": [skill_id],
                },
                sort_keys=True,
            )
            + "\n"
        )
        (skill_root / "SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n"
        )
        return plugin_root

    def update_cowork_plugin(self, plugin_root: Path, *, version: str, skill_edit: str) -> None:
        manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = version
        manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n")
        contract_path = plugin_root / "contracts" / f"{manifest['name']}.contract.json"
        contract = json.loads(contract_path.read_text())
        contract["version"] = version
        contract_path.write_text(json.dumps(contract, sort_keys=True) + "\n")
        skill_file = plugin_root / "skills" / "meeting-followup" / "SKILL.md"
        skill_file.write_text(skill_file.read_text() + skill_edit)

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

    def assert_no_memory_or_claude_writes(self) -> None:
        self.assertFalse((self.root / "memory").exists())
        self.assertFalse((self.root / "imports").exists())
        self.assertFalse((self.root / "exports").exists())
        self.assertFalse(self.claude_home.exists())

    def test_cowork_runtime_discovers_plugin_and_edits_draft_skill_files(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads)
        runtime = AiwsRuntime(
            root=self.root,
            env={
                **self.env,
                "COWORK_HOME": str(Path(self.tempdir.name) / ".cowork-no-packages"),
                "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads),
            },
        )

        discovered = runtime.discover_installed_plugins(plugin_id="example-plugin")
        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/review",
        )
        record_id = draft["record_id"]
        listed = runtime.list_draft_files(record_id)
        original = runtime.read_draft_file(record_id, "skills/meeting-followup/SKILL.md")
        written = runtime.write_draft_file(
            record_id,
            "skills/meeting-followup/references/notes.md",
            "Local edit.\n",
        )
        validated = runtime.validate_draft(record_id)
        deleted = runtime.delete_draft_file(record_id, "skills/meeting-followup/references/notes.md")

        self.assertEqual(discovered["status"], "ok")
        self.assertEqual(len(discovered["plugins"]), 1)
        self.assertEqual(draft["status"], "draft_opened")
        self.assertEqual(draft["origin_repo"], "example/review")
        self.assertIn("skills/meeting-followup/SKILL.md", listed["files"])
        self.assertIn("# Meeting Follow-Up", original["content"])
        self.assertEqual(written["status"], "written")
        self.assertEqual(validated["status"], "validated")
        self.assertEqual(validated["validation_status"], "passed")
        self.assertTrue(validated["modified"])
        self.assertEqual(deleted["status"], "deleted")
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_inspects_installed_skill_duplicates(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads / "first")
        self.write_cowork_plugin(uploads / "second")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )

        result = runtime.inspect_installed_skill(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
        )

        self.assertEqual(result["status"], "duplicate_visible_identity")
        self.assertEqual(result["instance_count"], 2)
        self.assertIsNone(result["selected_instance"])
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_inspects_skill_from_default_rpm_root(self) -> None:
        cowork_home = Path(self.tempdir.name) / ".cowork"
        rpm_root = cowork_home / "rpm"
        plugin_root = self.write_cowork_plugin(rpm_root / "plugin_123")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "COWORK_HOME": str(cowork_home)},
        )

        result = runtime.inspect_installed_skill(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["instance_count"], 1)
        self.assertEqual(result["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_inspects_skill_from_local_agent_session_rpm_root(self) -> None:
        sessions_root = Path(self.tempdir.name) / "local-agent-mode-sessions"
        rpm_root = sessions_root / "session-1" / "workspace-1" / "local-1" / "rpm"
        plugin_root = self.write_cowork_plugin(rpm_root / "plugin_123")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_CLAUDE_LOCAL_AGENT_SESSIONS_ROOT": str(sessions_root)},
        )

        result = runtime.inspect_installed_skill(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["instance_count"], 1)
        self.assertEqual(result["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_prepares_update_candidate_from_installed_plugin(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        plugin_root = self.write_cowork_plugin(uploads, version="0.1.0")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )
        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/review",
        )
        runtime.write_draft_file(
            draft["record_id"],
            "skills/meeting-followup/SKILL.md",
            "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n\nLocal edit.\n",
        )
        self.update_cowork_plugin(plugin_root, version="0.2.0", skill_edit="\nRemote marketplace update.\n")

        candidate = runtime.prepare_update_candidate(draft["record_id"])
        review = runtime.review_update_conflict(draft["record_id"], candidate["update_candidate_id"])

        self.assertEqual(candidate["status"], "update_candidate_created")
        self.assertEqual(candidate["remote_version"], "0.2.0")
        self.assertNotIn("source_plugin_root", candidate)
        self.assertEqual(review["status"], "update_conflict")
        self.assertIn("Local edit", review["local_vs_base_diff"]["content"])
        self.assertIn("Remote marketplace update", review["remote_vs_base_diff"]["content"])
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_create_draft_selects_single_matching_skill_when_plugin_discovery_is_ambiguous(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        plugin_root = self.write_cowork_plugin(uploads / "first")
        self.write_cowork_plugin(uploads / "second", skill_id="other-skill")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )

        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/review",
        )

        self.assertEqual(draft["status"], "draft_opened")
        self.assertEqual(draft["inspection"]["status"], "ok")
        self.assertEqual(draft["inspection"]["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_create_draft_blocks_accidental_parallel_active_draft(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads)
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )

        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/first-review",
        )
        runtime.write_draft_file(
            draft["record_id"],
            "skills/meeting-followup/SKILL.md",
            "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n\nUpdated.\n",
        )

        with self.assertRaisesRegex(ValueError, "Existing active draft"):
            runtime.create_or_open_draft(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                target_repo="example/second-review",
            )

        parallel = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/second-review",
            allow_parallel_draft=True,
        )

        self.assertNotEqual(parallel["record_id"], draft["record_id"])
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_reverts_draft_and_allows_new_draft_after_cleanup(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads)
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )
        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/first-review",
        )

        reverted = runtime.revert_draft(draft["record_id"])

        reopened = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/second-review",
        )

        self.assertEqual(reverted["status"], "reverted")
        self.assertEqual(reverted["record_id"], draft["record_id"])
        self.assertNotEqual(reopened["record_id"], draft["record_id"])
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_create_draft_fails_when_installed_skill_is_duplicated(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads / "first")
        self.write_cowork_plugin(uploads / "second")
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )

        inspection = runtime.inspect_installed_skill(plugin_id="example-plugin", skill_id="meeting-followup")

        self.assertEqual(inspection["status"], "duplicate_visible_identity")
        with self.assertRaisesRegex(ValueError, "duplicate_visible_identity"):
            runtime.create_or_open_draft(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                target_repo="example/review",
            )
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_activate_draft_requires_explicit_package_output_dir(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        self.write_cowork_plugin(uploads)
        runtime = AiwsRuntime(
            root=self.root,
            env={**self.env, "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads)},
        )
        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/review",
        )
        record_id = draft["record_id"]
        runtime.write_draft_file(
            record_id,
            "skills/meeting-followup/SKILL.md",
            "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n\nUpdated.\n",
        )

        with self.assertRaisesRegex(ValueError, "package_output_dir"):
            runtime.activate_draft(record_id, host_kind="cowork", package_output_dir=None)

        package_output_dir = self.root / "packages"
        activated = runtime.activate_draft(
            record_id,
            host_kind="cowork",
            package_output_dir=package_output_dir,
        )

        self.assertEqual(activated["status"], "host_capability_missing")
        self.assertEqual(activated["activation_status"], "pending_upload")
        self.assertEqual(activated["actions"][0]["type"], "package_upload")
        self.assertTrue(Path(activated["activation_record_path"]).is_file())
        with zipfile.ZipFile(activated["package_path"]) as package:
            self.assertIn("skills/meeting-followup/SKILL.md", package.namelist())
        deactivated = runtime.deactivate_draft(record_id, host_kind="cowork")
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertFalse(Path(activated["activation_record_path"]).exists())
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_activate_draft_hands_off_to_existing_package_upload_surface(self) -> None:
        uploads = Path(self.tempdir.name) / "cowork-uploads"
        cowork_home = Path(self.tempdir.name) / ".cowork"
        package_uploads = cowork_home / "packages"
        package_uploads.mkdir(parents=True)
        self.write_cowork_plugin(uploads)
        runtime = AiwsRuntime(
            root=self.root,
            env={
                **self.env,
                "COWORK_HOME": str(cowork_home),
                "AIWS_PLUGIN_SEARCH_ROOTS": str(uploads),
            },
        )
        draft = runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="example/review",
        )
        record_id = draft["record_id"]
        runtime.write_draft_file(
            record_id,
            "skills/meeting-followup/SKILL.md",
            "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n\nUpdated.\n",
        )

        activated = runtime.activate_draft(
            record_id,
            host_kind="cowork",
            package_output_dir=self.root / "packages",
        )

        self.assertEqual(activated["status"], "handoff_prepared")
        self.assertEqual(activated["activation_status"], "pending_upload")
        self.assertEqual(activated["actions"][0]["type"], "cowork_package_handoff")
        self.assertFalse(activated["activation_effective"])
        self.assertFalse(activated["requires_manual_upload"])
        self.assertTrue(activated["requires_cowork_confirmation"])
        self.assertEqual(Path(activated["copied_package_path"]).parent, package_uploads.resolve())
        self.assertEqual(
            Path(activated["copied_package_path"]).read_bytes(),
            Path(activated["package_path"]).read_bytes(),
        )
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_submit_for_review_uses_gh_cli_submitter(self) -> None:
        class FakeGhCliProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGitHubApiProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGithubHandoffProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        captured: dict[str, object] = {}

        def fake_submit_pr(aiws_root: Path, proposal_id: str, submitter: object, **kwargs: object) -> dict[str, object]:
            captured["aiws_root"] = aiws_root
            captured["proposal_id"] = proposal_id
            captured["submitter"] = submitter
            captured["kwargs"] = kwargs
            return {
                "status": "submitted_for_review",
                "proposal_id": proposal_id,
                "branch_name": "aiws/skill-proposals/skillprop_123",
                "pr_url": "https://github.com/example/review/pull/1",
            }

        with (
            patch.dict(os.environ, {"AIWS_GITHUB_TOKEN": "", "GITHUB_TOKEN": "", "GH_TOKEN": ""}),
            patch.object(
                runtime_module.skill_manager,
                "load_proposal_record",
                return_value={"backend_kind": "github"},
            ),
            patch.object(
                runtime_module.skill_manager,
                "GitHubApiProposalSubmitter",
                FakeGitHubApiProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.skill_manager, "GhCliProposalSubmitter", FakeGhCliProposalSubmitter, create=True),
            patch.object(
                runtime_module.skill_manager,
                "GithubHandoffProposalSubmitter",
                FakeGithubHandoffProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(runtime_module.skill_manager, "submit_pr", side_effect=fake_submit_pr),
        ):
            result = self.runtime.submit_for_review(
                "skillprop_123",
                allowed_target_repos=["example/review"],
            )

        self.assertEqual(result["status"], "submitted_for_review")
        self.assertEqual(captured["aiws_root"], self.root.resolve())
        self.assertEqual(captured["proposal_id"], "skillprop_123")
        self.assertIsInstance(captured["submitter"], FakeGhCliProposalSubmitter)
        self.assertEqual(captured["kwargs"], {"allowed_target_repos": ["example/review"]})
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_submit_for_review_prefers_github_api_submitter_when_token_exists(self) -> None:
        class FakeGitHubApiProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGhCliProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        captured: dict[str, object] = {}

        def fake_submit_pr(aiws_root: Path, proposal_id: str, submitter: object, **kwargs: object) -> dict[str, object]:
            captured["submitter"] = submitter
            return {
                "status": "submitted_for_review",
                "proposal_id": proposal_id,
                "branch_name": "aiws/skill-proposals/skillprop_123",
                "pr_url": "https://github.com/example/review/pull/1",
            }

        with (
            patch.dict(os.environ, {"AIWS_GITHUB_TOKEN": "token-for-test"}),
            patch.object(
                runtime_module.skill_manager,
                "load_proposal_record",
                return_value={"backend_kind": "github"},
            ),
            patch.object(
                runtime_module.skill_manager,
                "GitHubApiProposalSubmitter",
                FakeGitHubApiProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.skill_manager, "GhCliProposalSubmitter", FakeGhCliProposalSubmitter, create=True),
            patch.object(runtime_module.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(runtime_module.skill_manager, "submit_pr", side_effect=fake_submit_pr),
        ):
            result = self.runtime.submit_for_review(
                "skillprop_123",
                allowed_target_repos=["example/review"],
            )

        self.assertEqual(result["status"], "submitted_for_review")
        self.assertIsInstance(captured["submitter"], FakeGitHubApiProposalSubmitter)
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_submit_for_review_uses_handoff_submitter_when_gh_is_missing(self) -> None:
        class FakeGhCliProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGitHubApiProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGithubHandoffProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        captured: dict[str, object] = {}

        def fake_submit_pr(aiws_root: Path, proposal_id: str, submitter: object, **kwargs: object) -> dict[str, object]:
            captured["aiws_root"] = aiws_root
            captured["proposal_id"] = proposal_id
            captured["submitter"] = submitter
            captured["kwargs"] = kwargs
            return {
                "status": "submit_handoff_required",
                "reason_code": "github_cli_unavailable",
                "proposal_id": proposal_id,
                "target_repo": "example/review",
                "branch_name": "aiws/skill-proposals/skillprop_123",
                "terminal": False,
                "no_pr_created": True,
                "actions": [],
            }

        with (
            patch.dict(os.environ, {"AIWS_GITHUB_TOKEN": "", "GITHUB_TOKEN": "", "GH_TOKEN": ""}),
            patch.object(
                runtime_module.skill_manager,
                "load_proposal_record",
                return_value={"backend_kind": "github"},
            ),
            patch.object(
                runtime_module.skill_manager,
                "GitHubApiProposalSubmitter",
                FakeGitHubApiProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.skill_manager, "GhCliProposalSubmitter", FakeGhCliProposalSubmitter, create=True),
            patch.object(
                runtime_module.skill_manager,
                "GithubHandoffProposalSubmitter",
                FakeGithubHandoffProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.shutil, "which", return_value=None),
            patch.object(runtime_module.skill_manager, "submit_pr", side_effect=fake_submit_pr),
        ):
            result = self.runtime.submit_for_review(
                "skillprop_123",
                allowed_target_repos=["example/review"],
            )

        self.assertEqual(result["status"], "submit_handoff_required")
        self.assertEqual(captured["aiws_root"], self.root.resolve())
        self.assertEqual(captured["proposal_id"], "skillprop_123")
        self.assertIsInstance(captured["submitter"], FakeGithubHandoffProposalSubmitter)
        self.assertEqual(captured["kwargs"], {"allowed_target_repos": ["example/review"]})
        self.assertNotIn("required_review_roles", result)
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_submit_for_review_uses_google_drive_submitter_for_drive_proposal(self) -> None:
        class FakeGoogleDriveProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGitHubApiProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        class FakeGhCliProposalSubmitter:
            def __init__(self, *, aiws_root: Path) -> None:
                self.aiws_root = aiws_root

        captured: dict[str, object] = {}

        def fake_submit_pr(aiws_root: Path, proposal_id: str, submitter: object, **kwargs: object) -> dict[str, object]:
            captured["aiws_root"] = aiws_root
            captured["proposal_id"] = proposal_id
            captured["submitter"] = submitter
            captured["kwargs"] = kwargs
            return {
                "status": "submitted_for_review",
                "proposal_id": proposal_id,
                "proposal_folder_id": "folder-123",
                "proposal_folder_url": "https://drive.google.com/drive/folders/folder-123",
            }

        with (
            patch.object(
                runtime_module.skill_manager,
                "load_proposal_record",
                return_value={"backend_kind": "google_drive"},
            ),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveProposalSubmitter",
                FakeGoogleDriveProposalSubmitter,
                create=True,
            ),
            patch.object(
                runtime_module.skill_manager,
                "GitHubApiProposalSubmitter",
                FakeGitHubApiProposalSubmitter,
                create=True,
            ),
            patch.object(runtime_module.skill_manager, "GhCliProposalSubmitter", FakeGhCliProposalSubmitter, create=True),
            patch.object(runtime_module.shutil, "which", return_value="/usr/bin/gh"),
            patch.object(runtime_module.skill_manager, "submit_pr", side_effect=fake_submit_pr),
            patch.dict(os.environ, {"AIWS_GITHUB_TOKEN": "token-for-test"}),
        ):
            result = self.runtime.submit_for_review(
                "skillprop_123",
                allowed_target_repos=["example/review"],
            )

        self.assertEqual(result["status"], "submitted_for_review")
        self.assertEqual(captured["aiws_root"], self.root.resolve())
        self.assertEqual(captured["proposal_id"], "skillprop_123")
        self.assertIsInstance(captured["submitter"], FakeGoogleDriveProposalSubmitter)
        self.assertEqual(captured["kwargs"], {"allowed_target_repos": ["example/review"]})
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_refresh_proposal_state_delegates_to_skill_manager(self) -> None:
        with patch.object(
            runtime_module.skill_manager,
            "refresh_proposal_state",
            return_value={"status": "approved_pending_publish", "proposal_id": "skillprop_123"},
        ) as mocked:
            result = self.runtime.refresh_proposal_state("skillprop_123")

        self.assertEqual(result["status"], "approved_pending_publish")
        mocked.assert_called_once_with(self.root.resolve(), "skillprop_123")
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_publish_approved_proposal_delegates_to_skill_manager(self) -> None:
        with patch.object(
            runtime_module.skill_manager,
            "publish_approved_proposal",
            return_value={"status": "released", "proposal_id": "skillprop_123"},
        ) as mocked:
            result = self.runtime.publish_approved_proposal("skillprop_123")

        self.assertEqual(result["status"], "released")
        mocked.assert_called_once_with(self.root.resolve(), "skillprop_123")
        self.assert_no_memory_or_claude_writes()

    def test_materialize_skill_from_google_drive_published_package(self) -> None:
        package_buffer = io.BytesIO()
        with zipfile.ZipFile(package_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "skills/meeting-followup/SKILL.md",
                "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n",
            )
            package.writestr("skills/meeting-followup/references/notes.md", "Reference content.\n")
        registry_path = self.root / "state" / "marketplace-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "marketplaces": {
                        "checkout-main-real": {
                            "marketplace_id": "checkout-main-real",
                            "scope_id": "project:checkout",
                            "backend_kind": "google_drive",
                            "backend_ref": "drive-root-1",
                        }
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        with (
            patch.object(runtime_module.skill_manager, "google_drive_api_token", return_value="token"),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveApiClient",
                return_value=FakeRuntimeGoogleDriveClient(package_buffer.getvalue()),
            ),
        ):
            resolved = self.runtime.resolve_skill("meeting-followup", scope="project:checkout", host_kind="codex")
            self.assertEqual(resolved["status"], "ok")
            self.assertEqual(resolved["manifest"]["marketplace_id"], "checkout-main-real")
            self.assertEqual(resolved["manifest"]["plugin_id"], "example-plugin")
            resolved_by_marketplace = self.runtime.resolve_skill(
                "meeting-followup",
                marketplace_id="checkout-main-real",
                host_kind="codex",
            )
            self.assertEqual(resolved_by_marketplace["status"], "ok")

            result = self.runtime.materialize_skill(
                skill_id="meeting-followup",
                host_kind="codex",
                marketplace_id="checkout-main-real",
            )

        self.assertEqual(result["status"], "materialized")
        cache_path = Path(result["cache_path"])
        self.assertTrue((cache_path / "SKILL.md").is_file())
        self.assertTrue((cache_path / "references" / "notes.md").is_file())
        plugin_cache_path = Path(str(result["plugin_cache_path"]))
        self.assertTrue((plugin_cache_path / ".claude-plugin" / "plugin.json").is_file())
        plugin_manifest = json.loads((plugin_cache_path / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(plugin_manifest["name"], "example-plugin")
        self.assertEqual(plugin_manifest["version"], "1.0.1")
        self.assertEqual(result["manifest"]["marketplace_id"], "checkout-main-real")
        self.assertEqual(result["manifest"]["plugin_id"], "example-plugin")

        (self.cowork_home / "packages").mkdir(parents=True)
        cowork = self.runtime.materialize_skill(
            skill_id="meeting-followup",
            host_kind="cowork",
            marketplace_id="checkout-main-real",
        )
        cowork_adapter_plugin = Path(cowork["adapter_path"]) / "example-plugin"
        cowork_manifest = json.loads((cowork_adapter_plugin / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(cowork_manifest["name"], "example-plugin")
        self.assertEqual(cowork_manifest["version"], "1.0.1")
        self.assertTrue((cowork_adapter_plugin / "skills" / "meeting-followup" / "SKILL.md").is_file())

        install = self.runtime.install_host(host_kind="cowork")
        self.assertEqual(install["status"], "handoff_prepared")
        self.assertTrue(str(install["package_path"]).endswith("example-plugin.zip"))

        draft = self.runtime.create_or_open_draft(
            plugin_id="example-plugin",
            skill_id="meeting-followup",
            target_repo="checkout-main-real",
            origin_marketplace="checkout-main-real",
        )
        self.assertTrue(draft["record_id"].startswith("example-plugin--meeting-followup--"))
        self.assertEqual(draft["plugin_id"], "example-plugin")
        self.assertEqual(draft["origin_marketplace"], "checkout-main-real")
        with self.assertRaisesRegex(Exception, "expected plugin_id 'other-plugin'"):
            self.runtime.validate_draft(draft["record_id"], expected_plugin_id="other-plugin")

    def test_resolve_google_drive_marketplace_prefers_current_published_over_stale_cache(self) -> None:
        package_buffer = io.BytesIO()
        with zipfile.ZipFile(package_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "skills/meeting-followup/SKILL.md",
                "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n",
            )
        registry_path = self.root / "state" / "marketplace-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "marketplaces": {
                        "checkout-main-real": {
                            "marketplace_id": "checkout-main-real",
                            "scope_id": "project:checkout",
                            "backend_kind": "google_drive",
                            "backend_ref": "drive-root-1",
                        }
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        with (
            patch.object(runtime_module.skill_manager, "google_drive_api_token", return_value="token"),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveApiClient",
                return_value=FakeRuntimeGoogleDriveClient(
                    package_buffer.getvalue(),
                    current_version="1.0.1",
                    package_file_id="package-file-old",
                ),
            ),
        ):
            old = self.runtime.materialize_skill(
                skill_id="meeting-followup",
                host_kind="cowork",
                marketplace_id="checkout-main-real",
            )

        self.assertEqual(old["manifest"]["version"], "1.0.1")
        self.assertEqual(old["manifest"]["artifact_ref"], "google-drive:checkout-main-real:example-plugin:package-file-old")
        old_materialized = [
            record
            for record in self.runtime.materialized_records()
            if record.skill_id == "meeting-followup" and record.version == "1.0.1"
        ]
        self.assertEqual(old_materialized[0].scope, "project:checkout")

        with (
            patch.object(runtime_module.skill_manager, "google_drive_api_token", return_value="token"),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveApiClient",
                return_value=FakeRuntimeGoogleDriveClient(
                    package_buffer.getvalue(),
                    current_version="1.0.2",
                    package_file_id="package-file-new",
                ),
            ),
        ):
            resolved = self.runtime.resolve_skill(
                "meeting-followup",
                marketplace_id="checkout-main-real",
                host_kind="cowork",
            )
            materialized = self.runtime.materialize_skill(
                skill_id="meeting-followup",
                host_kind="cowork",
                marketplace_id="checkout-main-real",
            )
            searched = self.runtime.search_skills(
                query="meeting-followup",
                marketplace_id="checkout-main-real",
                host_kind="cowork",
            )
            workflow = self.runtime.drive_marketplace_workflow(
                marketplace_id="checkout-main-real",
                host_kind="cowork",
            )
            latest_workflow = self.runtime.drive_marketplace_workflow(
                marketplace_id="checkout-main-real",
                host_kind="cowork",
                latest_only=True,
            )

        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["manifest"]["version"], "1.0.2")
        self.assertEqual(
            resolved["manifest"]["artifact_ref"],
            "google-drive:checkout-main-real:example-plugin:package-file-new",
        )
        self.assertEqual(materialized["manifest"]["version"], "1.0.2")
        self.assertEqual(
            materialized["manifest"]["artifact_ref"],
            "google-drive:checkout-main-real:example-plugin:package-file-new",
        )
        self.assertTrue(str(materialized["plugin_cache_path"]).endswith("/checkout-main-real/example-plugin/1.0.2"))
        current_search_results = [
            result
            for result in searched["results"]
            if result["version"] == "1.0.2"
        ]
        self.assertEqual(len(current_search_results), 1)
        self.assertEqual(current_search_results[0]["scope"], "project:checkout")
        self.assertTrue(current_search_results[0]["materialized"])
        workflow_skills = workflow["marketplaces"][0]["plugins"][0]["skills"]
        current_workflow_skills = [
            skill
            for skill in workflow_skills
            if skill["version"] == "1.0.2"
        ]
        old_workflow_skills = [
            skill
            for skill in workflow_skills
            if skill["version"] == "1.0.1"
        ]
        self.assertEqual(len(old_workflow_skills), 1)
        self.assertEqual(len(current_workflow_skills), 1)
        self.assertEqual(current_workflow_skills[0]["scope"], "project:checkout")
        self.assertTrue(current_workflow_skills[0]["materialized"])
        old_actions = {action["id"]: action for action in old_workflow_skills[0]["actions"]}
        self.assertTrue(old_actions["delete_old_artifact_dry_run"]["enabled"])
        latest_skills = latest_workflow["marketplaces"][0]["plugins"][0]["skills"]
        self.assertEqual([skill["version"] for skill in latest_skills], ["1.0.2"])
        self.assertTrue(latest_skills[0]["materialized"])
        self.assertEqual(latest_skills[0]["status_label"], "Materialized")
        self.assertEqual(latest_skills[0]["next_action"], "open_draft")
        latest_actions = {action["id"]: action for action in latest_skills[0]["actions"]}
        self.assertTrue(latest_actions["open_draft"]["enabled"])
        self.assertEqual(
            latest_actions["open_draft"]["args"],
            {
                "marketplace_id": "checkout-main-real",
                "plugin_id": "example-plugin",
                "skill_id": "meeting-followup",
                "target_repo": "checkout-main-real",
                "origin_marketplace": "checkout-main-real",
            },
        )
        self.assertEqual(
            latest_actions["validate_draft"]["args_template"],
            {
                "draft_id": "example-plugin--meeting-followup--<hash>",
                "expected_plugin_id": "example-plugin",
                "expected_marketplace_id": "checkout-main-real",
            },
        )
        self.assertFalse(latest_actions["delete_old_artifact_dry_run"]["enabled"])
        self.assertEqual(
            latest_actions["delete_old_artifact_dry_run"]["disabled_reason"],
            "Current marketplace version cannot be deleted.",
        )
        self.assertTrue(latest_workflow["latest_only"])

    def test_materialize_skill_from_google_drive_skips_stale_marketplace_entries(self) -> None:
        package_buffer = io.BytesIO()
        with zipfile.ZipFile(package_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "skills/meeting-followup/SKILL.md",
                "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n",
            )
        registry_path = self.root / "state" / "marketplace-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(
            json.dumps(
                {
                    "marketplaces": {
                        "checkout-main": {
                            "marketplace_id": "checkout-main",
                            "scope_id": "project:checkout",
                            "backend_kind": "google_drive",
                            "backend_ref": "stale-drive-root",
                        },
                        "checkout-main-real": {
                            "marketplace_id": "checkout-main-real",
                            "scope_id": "project:checkout",
                            "backend_kind": "google_drive",
                            "backend_ref": "drive-root-1",
                        },
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        with (
            patch.object(runtime_module.skill_manager, "google_drive_api_token", return_value="token"),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveApiClient",
                return_value=MixedRuntimeGoogleDriveClient(package_buffer.getvalue()),
            ),
        ):
            resolved = self.runtime.resolve_skill("meeting-followup", scope="project:checkout", host_kind="codex")

        self.assertEqual(resolved["status"], "ok")
        self.assertEqual(resolved["manifest"]["marketplace_id"], "checkout-main-real")

    def test_cowork_runtime_start_google_drive_oauth_delegates_to_skill_manager(self) -> None:
        with patch.object(
            runtime_module.skill_manager,
            "start_google_drive_oauth",
            return_value={"status": "authorization_pending", "auth_session_id": "gdauth_123"},
        ) as mocked:
            result = self.runtime.start_google_drive_oauth(
                account="default",
                client_id="client-id",
                client_secret="client-secret",
            )

        self.assertEqual(result["status"], "authorization_pending")
        mocked.assert_called_once_with(
            self.root.resolve(),
            account="default",
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri=None,
            env=self.env,
        )
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_configure_google_drive_oauth_client_delegates_to_skill_manager(self) -> None:
        with patch.object(
            runtime_module.skill_manager,
            "configure_google_drive_oauth_client",
            return_value={"status": "oauth_client_configured", "oauth_client_path": "/tmp/default.oauth-client.json"},
        ) as mocked:
            result = self.runtime.configure_google_drive_oauth_client(
                account="default",
                client_id="client-id",
                client_secret="client-secret",
            )

        self.assertEqual(result["status"], "oauth_client_configured")
        mocked.assert_called_once_with(
            self.root.resolve(),
            account="default",
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri=None,
            token_uri=None,
            scopes=None,
        )
        self.assert_no_memory_or_claude_writes()

    def test_cowork_runtime_finish_google_drive_oauth_delegates_to_skill_manager(self) -> None:
        with patch.object(
            runtime_module.skill_manager,
            "finish_google_drive_oauth",
            return_value={"status": "connected", "auth_session_id": "gdauth_123"},
        ) as mocked:
            result = self.runtime.finish_google_drive_oauth(
                "gdauth_123",
                redirected_url="http://127.0.0.1/callback?code=abc&state=xyz",
            )

        self.assertEqual(result["status"], "connected")
        mocked.assert_called_once_with(
            self.root.resolve(),
            "gdauth_123",
            redirected_url="http://127.0.0.1/callback?code=abc&state=xyz",
            authorization_code=None,
        )
        self.assert_no_memory_or_claude_writes()

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

    def test_materialized_skill_replaces_builtin_fallback_identity(self) -> None:
        self.runtime.materialize_skill(skill_id="aiws-improve", host_kind="codex")

        local = self.runtime.list_local_skills()
        improve_records = [
            item for item in local["skills"] if item["skill_id"] == "aiws-improve"
        ]

        self.assertEqual(len(improve_records), 1)
        self.assertTrue(improve_records[0]["materialized"])

    def test_repeated_materialize_of_built_in_skill_is_idempotent(self) -> None:
        first = self.runtime.materialize_skill(skill_id="aiws-improve", host_kind="codex")
        cache_path = Path(first["cache_path"])
        before = self.read_tree(cache_path)

        second = self.runtime.materialize_skill(skill_id="aiws-improve", host_kind="codex")

        self.assertEqual(second["status"], "materialized")
        self.assertTrue(cache_path.exists())
        self.assertEqual(before, self.read_tree(cache_path))

    def test_old_materialized_cache_layout_is_ignored_without_crashing(self) -> None:
        old_root = (
            self.root
            / "hosts"
            / "codex-legacy"
            / "shared-cache"
            / "skills"
            / "personal"
            / "1.0.0"
            / "local-review"
        )
        old_root.mkdir(parents=True)
        (old_root / "SKILL.md").write_text(
            "---\nname: local-review\ndescription: Old cache layout.\n---\n\n# Local Review\n"
        )

        local = self.runtime.list_local_skills()

        self.assertNotIn(
            "local-review",
            {item["skill_id"] for item in local["skills"] if item["materialized"]},
        )

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
        self.assertIn("capabilities", payload)
        self.assertIn("evidence_surfaces", payload)
        surface_names = {surface["name"] for surface in payload["evidence_surfaces"]}
        self.assertIn("host_identity", surface_names)
        self.assertIn("observations", surface_names)

        loaded = self.runtime.ensure_host(host_id=host.host_id)
        self.assertEqual(loaded.host_kind, "claude-code")

        with self.assertRaises(ValueError):
            self.runtime.ensure_host(host_id=host.host_id, host_kind="codex")

        with self.assertRaises(ValueError):
            self.runtime.ensure_host(host_id="missing-host")

    def test_host_surfaces_are_provider_neutral_and_host_specific(self) -> None:
        codex = self.runtime.host_surfaces(host_kind="codex")
        self.assertEqual(codex["host_kind"], "codex")
        self.assertEqual(codex["capabilities"]["capability_exposure"], "skill")
        codex_surfaces = {surface["name"]: surface for surface in codex["evidence_surfaces"]}
        self.assertIn("session_history", codex_surfaces)
        self.assertIn("skill_catalog", codex_surfaces)
        self.assertFalse(codex_surfaces["installed_skills"]["writable"])
        self.assertNotIn("CLAUDE_PLUGIN_DATA", json.dumps(codex))

        claude = self.runtime.host_surfaces(host_kind="claude-code")
        claude_surfaces = {surface["name"]: surface for surface in claude["evidence_surfaces"]}
        self.assertIn("observations", claude_surfaces)
        self.assertIn("installed_contracts", claude_surfaces)

        cowork = self.runtime.host_surfaces(host_kind="cowork")
        cowork_surfaces = {surface["name"]: surface for surface in cowork["evidence_surfaces"]}
        self.assertIn("package_uploads", cowork_surfaces)
        self.assertTrue(cowork_surfaces["package_uploads"]["writable"])
        self.assertFalse(cowork_surfaces["package_uploads"]["exists"])
        self.assertFalse(cowork_surfaces["package_uploads"]["is_symlink"])
        self.assertFalse(cowork_surfaces["package_uploads"]["writable_effective"])

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
        self.assertEqual(cache_path.parts[-3:], ("personal", "local-review", "1.0.0"))
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

    def test_list_register_remove_marketplaces_round_trip(self) -> None:
        registered = self.runtime.register_marketplace(
            marketplace_id="checkout-main",
            scope_id="project:checkout",
            backend_kind="google_drive",
            backend_ref="drive-folder-123",
        )

        listed = self.runtime.list_marketplaces(scope_id="project:checkout", backend_kind="google_drive")
        removed = self.runtime.remove_marketplace(marketplace_id="checkout-main")
        missing = self.runtime.remove_marketplace(marketplace_id="checkout-main")

        self.assertEqual(registered["status"], "registered")
        self.assertEqual(registered["marketplace"]["marketplace_id"], "checkout-main")
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["marketplaces"][0]["backend_ref"], "drive-folder-123")
        self.assertEqual(removed["status"], "removed")
        self.assertEqual(missing["status"], "not_found")

    def test_drive_marketplace_workflow_browses_google_drive_plugins_and_skills(self) -> None:
        package_buffer = io.BytesIO()
        with zipfile.ZipFile(package_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "skills/meeting-followup/SKILL.md",
                "---\nname: meeting-followup\ndescription: Follow up after meetings.\n---\n\n# Meeting Follow-Up\n",
            )
        self.runtime.register_marketplace(
            marketplace_id="checkout-main-real",
            scope_id="project:checkout",
            backend_kind="google_drive",
            backend_ref="drive-root-1",
        )

        with (
            patch.object(runtime_module.skill_manager, "google_drive_api_token", return_value="token"),
            patch.object(
                runtime_module.skill_manager,
                "GoogleDriveApiClient",
                return_value=FakeRuntimeGoogleDriveClient(package_buffer.getvalue()),
            ),
        ):
            workflow = self.runtime.drive_marketplace_workflow(
                marketplace_id="checkout-main-real",
                host_kind="cowork",
            )

        self.assertEqual(workflow["status"], "ok")
        self.assertEqual(workflow["workflow_schema_version"], 1)
        self.assertFalse(workflow["latest_only"])
        self.assertTrue(workflow["include_history"])
        self.assertIn("do not appear in Cowork's native plugin sidebar yet", workflow["note"])
        self.assertEqual(workflow["marketplaces"][0]["marketplace_id"], "checkout-main-real")
        self.assertEqual(workflow["marketplaces"][0]["display_name"], "Checkout Main Real")
        self.assertFalse(workflow["marketplaces"][0]["cowork_native_visible"])
        self.assertEqual(workflow["marketplaces"][0]["plugins"][0]["plugin_id"], "example-plugin")
        skill = workflow["marketplaces"][0]["plugins"][0]["skills"][0]
        self.assertEqual(skill["skill_id"], "meeting-followup")
        self.assertEqual(skill["display_name"], "Meeting Follow-up")
        self.assertEqual(skill["status_label"], "Available")
        self.assertEqual(skill["next_action"], "materialize_skill")
        actions = {action["id"]: action for action in skill["actions"]}
        self.assertEqual(
            list(actions),
            [
                "materialize_skill",
                "open_draft",
                "validate_draft",
                "stage_proposal",
                "submit_for_review",
                "refresh_proposal_state",
                "publish_approved_proposal",
                "delete_old_artifact_dry_run",
                "check_core_update_status",
            ],
        )
        self.assertEqual(actions["materialize_skill"]["tool"], "aiws.skills.materialize")
        self.assertEqual(
            actions["materialize_skill"]["args"],
            {
                "marketplace_id": "checkout-main-real",
                "skill_id": "meeting-followup",
                "host_kind": "cowork",
                "version": "1.0.1",
            },
        )
        self.assertFalse(actions["open_draft"]["enabled"])
        self.assertEqual(actions["open_draft"]["requires"], ["materialize_skill"])
        self.assertEqual(actions["stage_proposal"]["tool"], "aiws.skills.stage_proposal")
        self.assertEqual(
            actions["stage_proposal"]["args_template"],
            {
                "draft_id": "example-plugin--meeting-followup--<hash>",
                "marketplace_id": "checkout-main-real",
            },
        )
        self.assertEqual(actions["delete_old_artifact_dry_run"]["tool"], "aiws.marketplaces.delete_artifact")
        self.assertFalse(actions["delete_old_artifact_dry_run"]["enabled"])
        self.assertEqual(
            actions["delete_old_artifact_dry_run"]["disabled_reason"],
            "Current marketplace version cannot be deleted.",
        )
        self.assertEqual(actions["check_core_update_status"]["tool"], "aiws.runtime.update_status")
        self.assertIn("aiws.skills.materialize", "\n".join(workflow["workflow"]))

    def test_install_host_cowork_prepares_package_handoff_from_materialized_adapter(self) -> None:
        self.write_personal_skill("local-review", "Review local work.")
        (self.cowork_home / "packages").mkdir(parents=True)

        materialized = self.runtime.materialize_skill(skill_id="local-review", host_kind="cowork")
        result = self.runtime.install_host(host_kind="cowork")

        package_path = Path(result["package_path"])
        copied_package_path = Path(result["copied_package_path"])
        adapter_plugin = Path(materialized["adapter_path"]) / "aiws-generated-plugin"

        self.assertEqual(result["status"], "handoff_prepared")
        self.assertTrue(result["requires_cowork_confirmation"])
        self.assertFalse(result["requires_manual_upload"])
        self.assertEqual(copied_package_path.parent.resolve(), (self.cowork_home / "packages").resolve())
        self.assertTrue(package_path.is_file())
        self.assertEqual(package_path.read_bytes(), copied_package_path.read_bytes())
        with zipfile.ZipFile(package_path) as package:
            self.assertIn(".claude-plugin/plugin.json", package.namelist())
            self.assertIn("skills/local-review/SKILL.md", package.namelist())
        self.assertTrue((adapter_plugin / ".claude-plugin" / "plugin.json").exists())

    def test_install_host_cowork_requires_verified_package_upload_directory(self) -> None:
        self.write_personal_skill("local-review", "Review local work.")
        self.cowork_home.mkdir(parents=True)
        (self.cowork_home / "packages").write_text("not a directory", encoding="utf-8")

        self.runtime.materialize_skill(skill_id="local-review", host_kind="cowork")
        result = self.runtime.install_host(host_kind="cowork")

        self.assertEqual(result["status"], "host_capability_missing")
        self.assertTrue(result["requires_manual_upload"])
        self.assertFalse(result["requires_cowork_confirmation"])
        self.assertIsNone(result["copied_package_path"])

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

    def test_install_host_backfills_legacy_host_json_for_explicit_host_id(self) -> None:
        host_id = "codex-legacy"
        host_root = self.root / "hosts" / host_id
        adapter_root = host_root / "adapter"
        skill_root = adapter_root / "skills" / "local-review"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: local-review\ndescription: Review local work.\n---\n\n# Local Review\n"
        )
        (adapter_root / "aiws-codex-export.json").write_text(
            json.dumps({"skills": [{"skill_id": "local-review", "path": "skills/local-review"}]})
        )
        legacy_payload = {
            "host_id": host_id,
            "host_kind": "codex",
            "config_root": str(self.codex_home.resolve()),
        }
        (host_root / "host.json").write_text(json.dumps(legacy_payload))

        result = self.runtime.install_host(host_kind="codex", host_id=host_id)

        payload = json.loads((host_root / "host.json").read_text())
        self.assertEqual(result["status"], "ok")
        self.assertIn("capabilities", payload)
        self.assertIn("evidence_surfaces", payload)

    def test_install_host_dry_run_does_not_backfill_legacy_host_json(self) -> None:
        host_id = "codex-legacy"
        host_root = self.root / "hosts" / host_id
        adapter_root = host_root / "adapter"
        skill_root = adapter_root / "skills" / "local-review"
        skill_root.mkdir(parents=True)
        (skill_root / "SKILL.md").write_text(
            "---\nname: local-review\ndescription: Review local work.\n---\n\n# Local Review\n"
        )
        (adapter_root / "aiws-codex-export.json").write_text(
            json.dumps({"skills": [{"skill_id": "local-review", "path": "skills/local-review"}]})
        )
        legacy_payload = {
            "host_id": host_id,
            "host_kind": "codex",
            "config_root": str(self.codex_home.resolve()),
        }
        host_json = host_root / "host.json"
        host_json.write_text(json.dumps(legacy_payload, sort_keys=True))
        before = host_json.read_text()

        result = self.runtime.install_host(host_kind="codex", host_id=host_id, dry_run=True)

        self.assertEqual(result["status"], "planned")
        self.assertEqual(host_json.read_text(), before)

    def test_install_host_rejects_host_id_path_traversal(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime.install_host(host_kind="codex", host_id="../outside-host")

    def test_install_host_no_skills_writes_nothing(self) -> None:
        result = self.runtime.install_host(host_kind="codex")

        self.assertEqual(result["status"], "no_skills")
        self.assertFalse((self.codex_home / "skills").exists())
        self.assertFalse((self.root / "hosts").exists())

    def test_install_host_no_skills_backfills_legacy_explicit_host_json(self) -> None:
        host_id = "codex-legacy"
        host_root = self.root / "hosts" / host_id
        host_root.mkdir(parents=True)
        host_json = host_root / "host.json"
        host_json.write_text(
            json.dumps(
                {
                    "host_id": host_id,
                    "host_kind": "codex",
                    "config_root": str(self.codex_home.resolve()),
                },
                sort_keys=True,
            )
        )

        result = self.runtime.install_host(host_kind="codex", host_id=host_id)

        payload = json.loads(host_json.read_text())
        self.assertEqual(result["status"], "no_skills")
        self.assertIn("capabilities", payload)
        self.assertIn("evidence_surfaces", payload)

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

        host_surfaces = subprocess.run(
            [
                sys.executable,
                "-m",
                "aiws_mcp",
                "--root",
                str(self.root),
                "host-surfaces",
                "--host-kind",
                "codex",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        surfaces_payload = json.loads(host_surfaces.stdout)
        self.assertEqual(surfaces_payload["host_kind"], "codex")
        self.assertIn("evidence_surfaces", surfaces_payload)

        cowork = subprocess.run(
            [
                sys.executable,
                "-m",
                "aiws_mcp",
                "--root",
                str(self.root),
                "install-host",
                "--host-kind",
                "cowork",
                "--config-root",
                str(self.cowork_home),
                "--dry-run",
            ],
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )
        cowork_payload = json.loads(cowork.stdout)
        self.assertEqual(cowork_payload["status"], "no_skills")

        failed = subprocess.run(
            [
                sys.executable,
                "-m",
                "aiws_mcp",
                "--root",
                str(self.root),
                "install-host",
                "--host-kind",
                "claude-code",
            ],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("supports only host_kind='codex' or host_kind='cowork'", failed.stderr)

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
