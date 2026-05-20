from __future__ import annotations

import base64
import hashlib
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
    create_update_candidate,
    create_or_open_draft,
    create_draft_record,
    draft_base_snapshot_path,
    deactivate_draft,
    delete_draft_file,
    discover_installed_plugins,
    draft_id,
    draft_record_path,
    draft_worktree_path,
    GhCliProposalSubmitter,
    GitHubApiProposalSubmitter,
    GithubHandoffProposalSubmitter,
    inspect_installed_skill,
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    load_draft_record,
    list_draft_files,
    read_draft_file,
    refresh_modified_status,
    prepare_update_candidate,
    resolve_update_conflict,
    revert_draft,
    review_update_conflict,
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
    finish_google_drive_oauth,
    GoogleDriveProposalSubmitter,
    google_drive_api_token,
    google_drive_auth_session_path,
    google_drive_credentials_path,
    google_drive_oauth_client_path,
    refresh_proposal_state,
    start_google_drive_oauth,
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


class FakeGitHubApiClient:
    def __init__(self, *, no_changes: bool = False, existing_pr: bool = False) -> None:
        self.no_changes = no_changes
        self.existing_pr = existing_pr
        self.calls: list[tuple[str, str, dict[str, object] | None, dict[str, object] | None]] = []
        self.blob_counter = 0

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
        query: dict[str, object] | None = None,
        allow_404: bool = False,
    ) -> dict[str, object] | list[object] | None:
        self.calls.append((method, path, payload, query))
        if method == "GET" and path == "/repos/example/review":
            return {"default_branch": "main", "permissions": {"push": True}}
        if method == "GET" and path == "/repos/example/review/git/refs/heads/main":
            return {"object": {"sha": "commit-base"}}
        if method == "GET" and path == "/repos/example/review/git/commits/commit-base":
            return {"tree": {"sha": "tree-base"}}
        if method == "GET" and path == "/repos/example/review/git/trees/tree-base":
            return {
                "tree": [
                    {
                        "path": "example-plugin/.claude-plugin/plugin.json",
                        "type": "blob",
                        "sha": "manifest-sha",
                    },
                    {
                        "path": "example-plugin/skills/meeting-followup/SKILL.md",
                        "type": "blob",
                        "sha": "old-skill-sha",
                    },
                    {"path": "README.md", "type": "blob", "sha": "readme-sha"},
                ]
            }
        if method == "GET" and path == "/repos/example/review/git/blobs/manifest-sha":
            return {
                "encoding": "base64",
                "content": base64.b64encode(
                    json.dumps({"name": "example-plugin", "version": "1.0.0"}).encode("utf-8")
                ).decode("ascii"),
            }
        if method == "POST" and path == "/repos/example/review/git/blobs":
            self.blob_counter += 1
            return {"sha": f"new-blob-{self.blob_counter}"}
        if method == "POST" and path == "/repos/example/review/git/trees":
            return {"sha": "tree-base" if self.no_changes else "tree-new"}
        if method == "POST" and path == "/repos/example/review/git/commits":
            return {"sha": "commit-new"}
        if method == "GET" and path.startswith("/repos/example/review/git/refs/heads/aiws/skill-proposals/"):
            return None if allow_404 else {"object": {"sha": "commit-old"}}
        if method == "POST" and path == "/repos/example/review/git/refs":
            return {"ref": payload["ref"] if payload else ""}
        if method == "PATCH" and path.startswith("/repos/example/review/git/refs/heads/aiws/skill-proposals/"):
            return {"ref": path.removeprefix("/repos/example/review/git/refs/")}
        if method == "GET" and path == "/repos/example/review/pulls":
            if self.existing_pr:
                return [{"number": 9, "html_url": "https://github.com/example/review/pull/9"}]
            return []
        if method == "PATCH" and path == "/repos/example/review/pulls/9":
            return {"html_url": "https://github.com/example/review/pull/9"}
        if method == "POST" and path == "/repos/example/review/pulls":
            return {"html_url": "https://github.com/example/review/pull/8"}
        raise AssertionError(f"Unexpected API call: {method} {path} {payload} {query}")


class FakeGoogleDriveClient:
    def __init__(self) -> None:
        self.ensure_folder_calls: list[tuple[str, str]] = []
        self.upsert_text_file_calls: list[dict[str, str]] = []
        self._folder_counter = 0
        self._file_counter = 0
        self._time_counter = 0
        self.files_by_id: dict[str, dict[str, str | list[str]]] = {}
        self.children: dict[tuple[str, str], str] = {}

    def _next_timestamp(self) -> str:
        self._time_counter += 1
        return f"2026-05-20T00:00:{self._time_counter:02d}Z"

    def ensure_folder(self, parent_id: str, name: str) -> dict[str, str]:
        self.ensure_folder_calls.append((parent_id, name))
        existing_id = self.children.get((parent_id, name))
        if existing_id is not None:
            existing = self.files_by_id[existing_id]
            return {
                "id": str(existing["id"]),
                "name": str(existing["name"]),
                "mimeType": str(existing["mimeType"]),
                "webViewLink": str(existing["webViewLink"]),
            }
        self._folder_counter += 1
        folder_id = f"folder-{self._folder_counter}"
        metadata: dict[str, str | list[str]] = {
            "id": folder_id,
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "webViewLink": f"https://drive.google.com/drive/folders/{folder_id}",
            "parents": [parent_id],
        }
        self.files_by_id[folder_id] = metadata
        self.children[(parent_id, name)] = folder_id
        return {
            "id": folder_id,
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "webViewLink": f"https://drive.google.com/drive/folders/{folder_id}",
        }

    def upsert_text_file(self, parent_id: str, name: str, content: str, mime_type: str) -> dict[str, str]:
        existing_id = self.children.get((parent_id, name))
        if existing_id is None:
            self._file_counter += 1
            file_id = f"file-{self._file_counter}"
        else:
            file_id = existing_id
        modified_time = self._next_timestamp()
        metadata: dict[str, str | list[str]] = {
            "id": file_id,
            "name": name,
            "mimeType": mime_type,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "parents": [parent_id],
            "content": content,
            "md5Checksum": hashlib.md5(content.encode("utf-8")).hexdigest(),
            "modifiedTime": modified_time,
        }
        self.files_by_id[file_id] = metadata
        self.children[(parent_id, name)] = file_id
        self.upsert_text_file_calls.append(
            {
                "parent_id": parent_id,
                "name": name,
                "content": content,
                "mime_type": mime_type,
            }
        )
        return {
            "id": file_id,
            "name": name,
            "mimeType": mime_type,
            "webViewLink": f"https://drive.google.com/file/d/{file_id}/view",
            "md5Checksum": str(metadata["md5Checksum"]),
            "modifiedTime": modified_time,
        }

    def get_file(self, file_id: str) -> dict[str, str | list[str]]:
        return dict(self.files_by_id[file_id])

    def find_child(self, parent_id: str, name: str, *, mime_type: str | None = None) -> dict[str, str | list[str]] | None:
        file_id = self.children.get((parent_id, name))
        if file_id is None:
            return None
        metadata = self.files_by_id[file_id]
        if mime_type is not None and metadata.get("mimeType") != mime_type:
            return None
        return dict(metadata)

    def move_file(self, file_id: str, new_parent_id: str) -> None:
        metadata = self.files_by_id[file_id]
        old_parents = metadata.get("parents")
        if isinstance(old_parents, list) and old_parents:
            self.children.pop((str(old_parents[0]), str(metadata["name"])), None)
        metadata["parents"] = [new_parent_id]
        self.children[(new_parent_id, str(metadata["name"]))] = file_id
        return dict(metadata)

    def overwrite_text_file(self, file_id: str, content: str) -> None:
        metadata = self.files_by_id[file_id]
        metadata["content"] = content
        metadata["md5Checksum"] = hashlib.md5(content.encode("utf-8")).hexdigest()
        metadata["modifiedTime"] = self._next_timestamp()


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
            self.assertEqual(tree_digest(draft_base_snapshot_path(aiws_root, record_id)), record.base_tree_digest)

    def test_prepare_update_candidate_uses_base_snapshot_and_current_installed_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            original_base_digest = record.base_tree_digest
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            self.update_plugin_version_and_skill(plugin_root, version="1.1.0", edit="\nRemote marketplace update.\n")

            candidate = prepare_update_candidate(aiws_root, record_id, plugin_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])

            self.assertEqual(candidate["status"], "update_candidate_created")
            self.assertEqual(candidate["base_tree_digest"], original_base_digest)
            self.assertEqual(review["status"], "update_conflict")
            self.assertIn("Local draft edit", review["local_vs_base_diff"]["content"])
            self.assertIn("Remote marketplace update", review["remote_vs_base_diff"]["content"])

    def test_prepare_update_candidate_reports_no_update_for_same_installed_plugin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, _record = self.create_meeting_followup_draft(temp_root)

            candidate = prepare_update_candidate(aiws_root, record_id, plugin_root)

            self.assertEqual(candidate["status"], "no_update_available")
            self.assertIsNone(candidate["update_candidate_id"])

    def test_prepare_update_candidate_requires_base_snapshot_for_modified_legacy_draft(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            shutil.rmtree(draft_base_snapshot_path(aiws_root, record_id))
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            self.update_plugin_version_and_skill(plugin_root, version="1.1.0", edit="\nRemote marketplace update.\n")

            with self.assertRaisesRegex(SkillManagerError, "base snapshot is missing"):
                prepare_update_candidate(aiws_root, record_id, plugin_root)

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

    def test_review_update_conflict_reports_local_and_remote_diffs_and_stores_digest_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)

            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])
            review_path = aiws_root / "state" / "update-reviews" / f"{review['review_id']}.json"
            stored = json.loads(review_path.read_text())

            self.assertEqual(review["status"], "update_conflict")
            self.assertEqual(review["choices"], [
                "keep_local_draft_and_pending_package",
                "discard_local_changes_and_update",
                "submit_or_upload_first",
            ])
            self.assertEqual(review["local_changed_files"], ["skills/meeting-followup/SKILL.md"])
            self.assertEqual(
                review["remote_changed_files"],
                [".claude-plugin/plugin.json", "contracts/example-plugin.contract.json", "skills/meeting-followup/SKILL.md"],
            )
            self.assertEqual(
                review["remote_non_skill_changed_files"],
                [".claude-plugin/plugin.json", "contracts/example-plugin.contract.json"],
            )
            self.assertIn("Local draft edit", review["local_vs_base_diff"]["content"])
            self.assertIn("Remote update", review["remote_vs_base_diff"]["content"])
            self.assertFalse(review["pending_upload"]["present"])
            self.assertEqual(stored["draft_id"], record_id)
            self.assertEqual(stored["base_tree_digest"], record.base_tree_digest)
            self.assertEqual(stored["current_tree_digest"], review["current_tree_digest"])
            self.assertEqual(stored["remote_tree_digest"], review["remote_tree_digest"])

    def test_resolve_update_conflict_stale_review_blocks_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])
            self.edit_draft_skill(record, "\nSecond local edit after review.\n")

            result = resolve_update_conflict(
                aiws_root,
                review["review_id"],
                "discard_local_changes_and_update",
                allow_full_plugin_discard=True,
            )

            self.assertEqual(result["status"], "stale_review")
            self.assertEqual(result["reason"], "current_draft_digest_changed")
            self.assertIn("Second local edit after review", (Path(record.draft_path) / "skills/meeting-followup/SKILL.md").read_text())

    def test_review_update_conflict_allows_clean_update_without_resolution_choices(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, _record = self.create_meeting_followup_draft(temp_root)
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)

            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])

            self.assertEqual(review["status"], "update_allowed")
            self.assertEqual(review["reason"], "no_modified_draft_or_pending_upload")
            self.assertEqual(review["choices"], [])
            self.assertEqual(review["local_changed_files"], [])
            self.assertEqual(
                review["remote_changed_files"],
                [".claude-plugin/plugin.json", "contracts/example-plugin.contract.json", "skills/meeting-followup/SKILL.md"],
            )

    def test_resolve_update_conflict_keep_and_submit_first_are_no_ops(self) -> None:
        for choice, expected_status in (
            ("keep_local_draft_and_pending_package", "update_skipped"),
            ("submit_or_upload_first", "submit_or_upload_first"),
        ):
            with self.subTest(choice=choice):
                with tempfile.TemporaryDirectory() as temp:
                    temp_root = Path(temp)
                    aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
                    self.edit_draft_skill(record, "\nLocal draft edit.\n")
                    remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
                    candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
                    review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])
                    before = tree_digest(Path(record.draft_path))

                    result = resolve_update_conflict(aiws_root, review["review_id"], choice)

                    self.assertEqual(result["status"], expected_status)
                    self.assertEqual(tree_digest(Path(record.draft_path)), before)
                    self.assertTrue(load_draft_record(aiws_root, record_id).modified)

    def test_resolve_update_conflict_discard_adopts_remote_and_marks_draft_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])

            result = resolve_update_conflict(aiws_root, review["review_id"], "discard_local_changes_and_update")
            loaded = load_draft_record(aiws_root, record_id)
            skill_content = (Path(loaded.draft_path) / "skills" / "meeting-followup" / "SKILL.md").read_text()

            self.assertEqual(result["status"], "discarded_local_changes_and_updated")
            self.assertFalse(loaded.modified)
            self.assertEqual(loaded.base_tree_digest, loaded.current_tree_digest)
            self.assertEqual(loaded.base_tree_digest, result["current_tree_digest"])
            self.assertIn("Remote update", skill_content)
            self.assertNotIn("Local draft edit", skill_content)
            self.assertEqual(json.loads((Path(loaded.draft_path) / ".claude-plugin" / "plugin.json").read_text())["version"], "1.1.0")

    def test_resolve_update_conflict_pending_upload_requires_explicit_clear_and_only_clears_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            activated = activate_draft(aiws_root, record_id, "cowork", temp_root / "packages", host_id="cowork-test")
            package_path = Path(activated["package_path"])
            activation_record_path = Path(activated["activation_record_path"])
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])

            blocked = resolve_update_conflict(aiws_root, review["review_id"], "discard_local_changes_and_update")
            self.assertEqual(blocked["status"], "pending_upload_must_be_cleared")
            self.assertTrue(activation_record_path.exists())
            cleared = resolve_update_conflict(
                aiws_root,
                review["review_id"],
                "discard_local_changes_and_update",
                clear_pending_upload=True,
            )

            self.assertEqual(cleared["status"], "discarded_local_changes_and_updated")
            self.assertEqual(cleared["cleared_pending_uploads"], 1)
            self.assertFalse(activation_record_path.exists())
            self.assertTrue(package_path.exists())

    def test_resolve_update_conflict_rejects_pending_upload_state_created_after_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])
            activated = activate_draft(aiws_root, record_id, "cowork", temp_root / "packages", host_id="cowork-test")

            result = resolve_update_conflict(
                aiws_root,
                review["review_id"],
                "discard_local_changes_and_update",
                clear_pending_upload=True,
            )

            self.assertEqual(result["status"], "stale_review")
            self.assertEqual(result["reason"], "pending_upload_state_changed")
            self.assertTrue(Path(activated["activation_record_path"]).exists())
            self.assertIn("Local draft edit", (Path(record.draft_path) / "skills" / "meeting-followup" / "SKILL.md").read_text())

    def test_resolve_update_conflict_blocks_local_non_skill_discard_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, record = self.create_meeting_followup_draft(temp_root)
            self.edit_draft_skill(record, "\nLocal draft edit.\n")
            draft_manifest = Path(record.draft_path) / ".claude-plugin" / "plugin.json"
            manifest = json.loads(draft_manifest.read_text())
            manifest["description"] = "Local non-skill change."
            draft_manifest.write_text(json.dumps(manifest))
            remote_root = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "remote-plugin", "\nRemote update.\n")
            candidate = create_update_candidate(aiws_root, record_id, plugin_root, remote_root)
            review = review_update_conflict(aiws_root, record_id, candidate["update_candidate_id"])

            blocked = resolve_update_conflict(aiws_root, review["review_id"], "discard_local_changes_and_update")
            allowed = resolve_update_conflict(
                aiws_root,
                review["review_id"],
                "discard_local_changes_and_update",
                allow_full_plugin_discard=True,
            )

            self.assertEqual(blocked["status"], "full_plugin_discard_confirmation_required")
            self.assertEqual(blocked["local_non_skill_changed_files"], [".claude-plugin/plugin.json"])
            self.assertEqual(allowed["status"], "discarded_local_changes_and_updated")

    def test_update_candidate_validation_fails_closed_for_wrong_identity_missing_skill_and_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root, record_id, plugin_root, _record = self.create_meeting_followup_draft(temp_root)

            wrong = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "wrong-plugin", "\nRemote update.\n")
            wrong_manifest = json.loads((wrong / ".claude-plugin" / "plugin.json").read_text())
            wrong_manifest["name"] = "other-plugin"
            (wrong / ".claude-plugin" / "plugin.json").write_text(json.dumps(wrong_manifest))
            with self.assertRaisesRegex(SkillManagerError, "points to plugin"):
                create_update_candidate(aiws_root, record_id, plugin_root, wrong)

            missing = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "missing-skill-plugin", "\nRemote update.\n")
            shutil.rmtree(missing / "skills" / "meeting-followup")
            with self.assertRaisesRegex(SkillManagerError, "does not exist|public_skills missing"):
                create_update_candidate(aiws_root, record_id, plugin_root, missing)

            binary = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "binary-plugin", "\nRemote update.\n")
            (binary / "skills" / "meeting-followup" / "asset.bin").write_bytes(b"\x00\xff")
            with self.assertRaisesRegex(SkillManagerError, "binary"):
                create_update_candidate(aiws_root, record_id, plugin_root, binary)

            symlinked = self.copy_plugin_with_skill_edit(temp_root, plugin_root, "symlinked-plugin", "\nRemote update.\n")
            outside = temp_root / "outside.md"
            outside.write_text("outside\n")
            linked = symlinked / "skills" / "meeting-followup" / "linked.md"
            linked.symlink_to(outside)
            with self.assertRaisesRegex(SkillManagerError, "symlinks"):
                create_update_candidate(aiws_root, record_id, plugin_root, symlinked)

            root_symlink = temp_root / "root-symlink-plugin"
            root_symlink.symlink_to(plugin_root, target_is_directory=True)
            with self.assertRaisesRegex(SkillManagerError, "symlink"):
                create_update_candidate(aiws_root, record_id, plugin_root, root_symlink)

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

    def test_stage_proposal_github_records_backend_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")

            result = stage_proposal(
                aiws_root,
                record_id,
                "Cowork shared skill",
                "ai-workspace-skills-review",
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
            )

            proposal = json.loads(Path(result["proposal_path"]).read_text())
            self.assertEqual(proposal["scope_id"], "Cowork shared skill")
            self.assertEqual(proposal["backend_kind"], "github")
            self.assertEqual(proposal["backend_ref"], "ai-workspace-skills-review")
            self.assertEqual(proposal["target_repo"], "ai-workspace-skills-review")
            self.assertIsNone(proposal["marketplace_id"])

    def test_stage_proposal_google_drive_requires_marketplace_and_registers_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")

            result = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )

            proposal = json.loads(Path(result["proposal_path"]).read_text())
            self.assertEqual(proposal["scope_id"], "project:checkout")
            self.assertEqual(proposal["backend_kind"], "google_drive")
            self.assertEqual(proposal["backend_ref"], "drive-folder-123")
            self.assertEqual(proposal["marketplace_id"], "checkout-main")
            self.assertIsNone(proposal["target_repo"])

            registry_path = aiws_root / "state" / "marketplace-registry.json"
            self.assertTrue(registry_path.is_file())
            registry = json.loads(registry_path.read_text())
            self.assertEqual(
                registry["marketplaces"]["checkout-main"],
                {
                    "marketplace_id": "checkout-main",
                    "scope_id": "project:checkout",
                    "backend_kind": "google_drive",
                    "backend_ref": "drive-folder-123",
                },
            )

    def test_stage_proposal_google_drive_rejects_marketplace_identity_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            registry_path = aiws_root / "state" / "marketplace-registry.json"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                json.dumps(
                    {
                        "marketplaces": {
                            "checkout-main": {
                                "marketplace_id": "checkout-main",
                                "scope_id": "project:checkout",
                                "backend_kind": "google_drive",
                                "backend_ref": "drive-folder-123",
                            }
                        }
                    }
                )
            )

            with self.assertRaisesRegex(SkillManagerError, "already registered"):
                stage_proposal(
                    aiws_root,
                    record_id,
                    "unit:risk",
                    None,
                    "Improve meeting follow-up",
                    "The current instructions miss owner handoffs.",
                    backend_kind="google_drive",
                    backend_ref="drive-folder-other",
                    marketplace_id="checkout-main",
                )

            self.assert_no_proposals(aiws_root)

    def test_google_drive_api_token_prefers_env_over_credentials_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"
            credentials_path = google_drive_credentials_path(aiws_root, "default")
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            credentials_path.write_text(
                json.dumps({"access_token": "file-token", "expiry": "2099-01-01T00:00:00Z"}) + "\n"
            )

            token = google_drive_api_token(aiws_root, env={"AIWS_GOOGLE_DRIVE_TOKEN": "env-token"})

            self.assertEqual(token, "env-token")

    def test_google_drive_api_token_reads_default_credentials_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"
            credentials_path = google_drive_credentials_path(aiws_root, "default")
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            credentials_path.write_text(
                json.dumps({"access_token": "file-token", "expiry": "2099-01-01T00:00:00Z"}) + "\n"
            )

            token = google_drive_api_token(aiws_root, env={})

            self.assertEqual(token, "file-token")

    def test_google_drive_api_token_refreshes_expired_credentials_and_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"
            credentials_path = google_drive_credentials_path(aiws_root, "default")
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            credentials_path.write_text(
                json.dumps(
                    {
                        "access_token": "stale-token",
                        "expiry": "2000-01-01T00:00:00Z",
                        "refresh_token": "refresh-token",
                        "client_id": "client-id",
                        "client_secret": "client-secret",
                    }
                )
                + "\n"
            )
            captured: dict[str, str] = {}

            def fake_refresher(**kwargs: str) -> dict[str, object]:
                captured.update(kwargs)
                return {"access_token": "fresh-token", "expires_in": 1800}

            token = google_drive_api_token(aiws_root, env={}, token_refresher=fake_refresher)

            self.assertEqual(token, "fresh-token")
            self.assertEqual(captured["refresh_token"], "refresh-token")
            persisted = json.loads(credentials_path.read_text())
            self.assertEqual(persisted["access_token"], "fresh-token")
            self.assertIn("expiry", persisted)

    def test_google_drive_api_token_rejects_expired_credentials_without_refresh_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"
            credentials_path = google_drive_credentials_path(aiws_root, "default")
            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            credentials_path.write_text(
                json.dumps({"access_token": "stale-token", "expiry": "2000-01-01T00:00:00Z"}) + "\n"
            )

            with self.assertRaisesRegex(SkillManagerError, "expired and missing refresh_token"):
                google_drive_api_token(aiws_root, env={})

    def test_start_google_drive_oauth_persists_session_and_client_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"

            result = start_google_drive_oauth(
                aiws_root,
                client_id="client-id.apps.googleusercontent.com",
                client_secret="client-secret",
            )

            self.assertEqual(result["status"], "authorization_pending")
            self.assertEqual(result["account"], "default")
            self.assertEqual(result["next_action"], "finish_google_drive_oauth")
            self.assertIn("https://accounts.google.com/o/oauth2/v2/auth?", result["auth_url"])
            self.assertIn("client_id=client-id.apps.googleusercontent.com", result["auth_url"])
            self.assertIn("code_challenge=", result["auth_url"])

            client_payload = json.loads(google_drive_oauth_client_path(aiws_root, "default").read_text())
            self.assertEqual(client_payload["client_id"], "client-id.apps.googleusercontent.com")
            self.assertEqual(client_payload["client_secret"], "client-secret")

            session_path = google_drive_auth_session_path(aiws_root, result["auth_session_id"])
            session_payload = json.loads(session_path.read_text())
            self.assertEqual(session_payload["status"], "pending_browser_consent")
            self.assertEqual(session_payload["account"], "default")
            self.assertIn("code_verifier", session_payload)
            self.assertIn("state", session_payload)

    def test_finish_google_drive_oauth_exchanges_code_and_writes_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root = Path(temp) / ".aiws"
            started = start_google_drive_oauth(
                aiws_root,
                client_id="client-id.apps.googleusercontent.com",
                client_secret="client-secret",
            )
            session_path = google_drive_auth_session_path(aiws_root, started["auth_session_id"])
            session_payload = json.loads(session_path.read_text())
            redirected_url = (
                f"{started['redirect_uri']}?code=auth-code-123&state={session_payload['state']}"
            )
            captured: dict[str, str | None] = {}

            def fake_exchanger(**kwargs: str | None) -> dict[str, object]:
                captured.update(kwargs)
                return {
                    "access_token": "fresh-access-token",
                    "refresh_token": "fresh-refresh-token",
                    "expires_in": 3600,
                }

            result = finish_google_drive_oauth(
                aiws_root,
                started["auth_session_id"],
                redirected_url=redirected_url,
                code_exchanger=fake_exchanger,
            )

            self.assertEqual(result["status"], "connected")
            self.assertEqual(result["account"], "default")
            self.assertTrue(result["has_refresh_token"])
            self.assertEqual(captured["code"], "auth-code-123")
            self.assertEqual(captured["client_id"], "client-id.apps.googleusercontent.com")
            self.assertEqual(captured["client_secret"], "client-secret")
            credentials_payload = json.loads(google_drive_credentials_path(aiws_root, "default").read_text())
            self.assertEqual(credentials_payload["access_token"], "fresh-access-token")
            self.assertEqual(credentials_payload["refresh_token"], "fresh-refresh-token")
            completed_session = json.loads(session_path.read_text())
            self.assertEqual(completed_session["status"], "connected")
            self.assertIn("completed_at", completed_session)

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

    def test_discover_installed_plugins_includes_cowork_rpm_roots_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cowork_home = temp_root / ".cowork"
            rpm_root = cowork_home / "rpm"
            plugin_root = self.write_plugin(rpm_root / "plugin_123", public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            found = discover_installed_plugins(plugin_id="example-plugin", env={"COWORK_HOME": str(cowork_home)})

            self.assertEqual(found["status"], "ok")
            self.assertIn(str(rpm_root), found["searched_roots"])
            self.assertEqual(found["plugins"][0]["source_plugin_root"], str(plugin_root.resolve()))

    def test_discover_installed_plugins_includes_claude_local_agent_session_rpm_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            sessions_root = temp_root / "local-agent-mode-sessions"
            rpm_root = sessions_root / "session-1" / "workspace-1" / "local-1" / "rpm"
            plugin_root = self.write_plugin(rpm_root / "plugin_123", public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            found = discover_installed_plugins(
                plugin_id="example-plugin",
                env={"AIWS_CLAUDE_LOCAL_AGENT_SESSIONS_ROOT": str(sessions_root)},
            )

            self.assertEqual(found["status"], "ok")
            self.assertIn(str(rpm_root), found["searched_roots"])
            self.assertEqual(found["plugins"][0]["source_plugin_root"], str(plugin_root.resolve()))

    def test_inspect_installed_skill_reports_single_duplicate_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            first_root = temp_root / "uploads" / "one"
            plugin_root = self.write_plugin(first_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            single = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                search_roots=[first_root],
            )
            self.assertEqual(single["status"], "ok")
            self.assertEqual(single["instance_count"], 1)
            self.assertEqual(single["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))
            self.assertEqual(single["selected_instance"]["skill_id"], "meeting-followup")

            second_root = temp_root / "uploads" / "two"
            other_plugin = self.write_plugin(second_root, public_skills=["meeting-followup"])
            self.write_skill(other_plugin, "meeting-followup")

            duplicate = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                search_roots=[temp_root / "uploads"],
            )
            self.assertEqual(duplicate["status"], "duplicate_visible_identity")
            self.assertEqual(duplicate["instance_count"], 2)
            self.assertIsNone(duplicate["selected_instance"])

            missing = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="not-there",
                search_roots=[temp_root / "uploads"],
            )
            self.assertEqual(missing["status"], "installed_skill_not_found")
            self.assertEqual(missing["instance_count"], 0)

    def test_inspect_installed_skill_uses_default_cowork_rpm_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cowork_home = temp_root / ".cowork"
            rpm_root = cowork_home / "rpm"
            plugin_root = self.write_plugin(rpm_root / "plugin_123", public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            result = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                env={"COWORK_HOME": str(cowork_home)},
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["instance_count"], 1)
            self.assertEqual(result["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))

    def test_inspect_installed_skill_uses_claude_local_agent_session_rpm_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            sessions_root = temp_root / "local-agent-mode-sessions"
            rpm_root = sessions_root / "session-1" / "workspace-1" / "local-1" / "rpm"
            plugin_root = self.write_plugin(rpm_root / "plugin_123", public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            result = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                env={"AIWS_CLAUDE_LOCAL_AGENT_SESSIONS_ROOT": str(sessions_root)},
            )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["instance_count"], 1)
            self.assertEqual(result["selected_instance"]["source_plugin_root"], str(plugin_root.resolve()))

    def test_inspect_installed_skill_reports_duplicate_cowork_rpm_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            cowork_home = temp_root / ".cowork"
            first_plugin = self.write_plugin(cowork_home / "rpm" / "plugin_123", public_skills=["meeting-followup"])
            self.write_skill(first_plugin, "meeting-followup")
            second_plugin = self.write_plugin(cowork_home / "rpm" / "plugin_456", public_skills=["meeting-followup"])
            self.write_skill(second_plugin, "meeting-followup")

            result = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                env={"COWORK_HOME": str(cowork_home)},
            )

            self.assertEqual(result["status"], "duplicate_visible_identity")
            self.assertEqual(result["instance_count"], 2)
            self.assertIsNone(result["selected_instance"])

    def test_inspect_installed_skill_explicit_source_pins_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            first_root = temp_root / "uploads" / "one"
            first_plugin = self.write_plugin(first_root, public_skills=["meeting-followup"])
            self.write_skill(first_plugin, "meeting-followup")
            second_root = temp_root / "uploads" / "two"
            second_plugin = self.write_plugin(second_root, public_skills=["meeting-followup"])
            self.write_skill(second_plugin, "meeting-followup")

            pinned = inspect_installed_skill(
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                source_plugin_root=second_plugin,
            )

            self.assertEqual(pinned["status"], "ok")
            self.assertEqual(pinned["selection"], "explicit_source")
            self.assertEqual(pinned["instance_count"], 1)
            self.assertEqual(pinned["selected_instance"]["source_plugin_root"], str(second_plugin.resolve()))

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
            self.assertEqual(proposal["repository_review_policy"]["status"], "unknown")
            self.assertEqual(proposal["repository_review_policy"]["codeowners"], "unknown")
            self.assertFalse(proposal["repository_review_policy"]["normal_user_selects_reviewers"])
            self.assertNotIn("required_review_roles", proposal)
            self.assertIn("submitted_at", proposal)

            loaded = load_draft_record(aiws_root, record_id)
            self.assertIsNone(loaded.branch_name)
            self.assertIsNone(loaded.pr_url)

    def test_submit_pr_google_drive_creates_review_packet_and_persists_review_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            staged = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )
            drive_client = FakeGoogleDriveClient()

            result = submit_pr(
                aiws_root,
                staged["proposal_id"],
                GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=drive_client),
            )

            self.assertEqual(result["status"], "submitted_for_review")
            self.assertEqual(result["status_label"], "Submitted for review")
            self.assertEqual(result["proposal_id"], staged["proposal_id"])
            self.assertEqual(result["draft_id"], record_id)
            self.assertEqual(result["plugin_id"], "example-plugin")
            self.assertEqual(result["skill_id"], "meeting-followup")
            self.assertEqual(result["target_scope"], "project:checkout")
            self.assertEqual(result["backend_kind"], "google_drive")
            self.assertEqual(result["backend_ref"], "drive-folder-123")
            self.assertEqual(result["marketplace_id"], "checkout-main")
            self.assertEqual(result["proposal_folder_id"], "folder-5")
            self.assertEqual(result["proposal_folder_url"], "https://drive.google.com/drive/folders/folder-5")
            self.assertEqual(result["backend_review_state"], "in_review")

            self.assertEqual(
                drive_client.ensure_folder_calls,
                [
                    ("drive-folder-123", "plugins"),
                    ("folder-1", "example-plugin"),
                    ("folder-2", "proposals"),
                    ("folder-3", "in_review"),
                    ("folder-4", staged["proposal_id"]),
                    ("folder-3", "approved"),
                    ("folder-3", "rejected"),
                    ("folder-3", "released"),
                ],
            )
            self.assertEqual(
                [call["name"] for call in drive_client.upsert_text_file_calls],
                ["base.SKILL.md", "proposed.SKILL.md", "proposal.json"],
            )
            self.assertEqual(
                [call["mime_type"] for call in drive_client.upsert_text_file_calls],
                ["text/markdown", "text/markdown", "application/json"],
            )
            self.assertNotIn("Local proposal edit.", drive_client.upsert_text_file_calls[0]["content"])
            self.assertIn("Local proposal edit.", drive_client.upsert_text_file_calls[1]["content"])
            uploaded_proposal = json.loads(drive_client.upsert_text_file_calls[2]["content"])
            self.assertEqual(uploaded_proposal["proposal_id"], staged["proposal_id"])
            self.assertEqual(uploaded_proposal["status"], "submitted_for_review")
            self.assertEqual(uploaded_proposal["backend_kind"], "google_drive")
            self.assertEqual(uploaded_proposal["backend_review_state"], "in_review")
            self.assertEqual(uploaded_proposal["proposal_folder_id"], "folder-5")
            self.assertNotIn("draft_path", uploaded_proposal)

            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "submitted_for_review")
            self.assertEqual(proposal["proposal_folder_id"], "folder-5")
            self.assertEqual(proposal["proposal_folder_url"], "https://drive.google.com/drive/folders/folder-5")
            self.assertEqual(proposal["backend_review_state"], "in_review")
            self.assertIn("submitted_at", proposal)

    def test_submit_pr_google_drive_already_submitted_proposal_returns_existing_metadata_without_submitter_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            staged = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )
            first_client = FakeGoogleDriveClient()
            submitter = GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=first_client)

            first = submit_pr(aiws_root, staged["proposal_id"], submitter)

            second_client = FakeGoogleDriveClient()
            second = submit_pr(
                aiws_root,
                staged["proposal_id"],
                GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=second_client),
            )

            self.assertEqual(second["status"], "submitted_for_review")
            self.assertEqual(second["proposal_folder_id"], first["proposal_folder_id"])
            self.assertEqual(second["proposal_folder_url"], first["proposal_folder_url"])
            self.assertEqual(second_client.ensure_folder_calls, [])
            self.assertEqual(second_client.upsert_text_file_calls, [])

    def test_refresh_proposal_state_google_drive_marks_approved_pending_publish(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            staged = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )
            drive_client = FakeGoogleDriveClient()
            submit_pr(
                aiws_root,
                staged["proposal_id"],
                GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=drive_client),
            )
            proposal_before = self.proposal_payload(aiws_root, staged["proposal_id"])
            drive_client.move_file(
                str(proposal_before["proposal_folder_id"]),
                str(proposal_before["approved_folder_id"]),
            )

            result = refresh_proposal_state(
                aiws_root,
                staged["proposal_id"],
                drive_client=drive_client,
            )

            self.assertEqual(result["status"], "approved_pending_publish")
            self.assertEqual(result["backend_review_state"], "approved")
            self.assertEqual(result["proposal_id"], staged["proposal_id"])
            self.assertEqual(result["marketplace_id"], "checkout-main")
            self.assertIn("approved_at", result)
            self.assertEqual(result["approved_proposed_skill_file_id"], "file-2")
            self.assertEqual(
                result["approved_proposed_skill_md5"],
                hashlib.md5(drive_client.files_by_id["file-2"]["content"].encode("utf-8")).hexdigest(),
            )

            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "approved_pending_publish")
            self.assertEqual(proposal["backend_review_state"], "approved")
            self.assertEqual(proposal["approved_proposed_skill_file_id"], "file-2")
            self.assertIn("approved_at", proposal)

    def test_refresh_proposal_state_google_drive_marks_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            staged = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )
            drive_client = FakeGoogleDriveClient()
            submit_pr(
                aiws_root,
                staged["proposal_id"],
                GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=drive_client),
            )
            proposal_before = self.proposal_payload(aiws_root, staged["proposal_id"])
            drive_client.move_file(
                str(proposal_before["proposal_folder_id"]),
                str(proposal_before["rejected_folder_id"]),
            )

            result = refresh_proposal_state(
                aiws_root,
                staged["proposal_id"],
                drive_client=drive_client,
            )

            self.assertEqual(result["status"], "rejected")
            self.assertEqual(result["backend_review_state"], "rejected")
            self.assertIn("rejected_at", result)
            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "rejected")
            self.assertEqual(proposal["backend_review_state"], "rejected")

    def test_refresh_proposal_state_google_drive_marks_needs_reapproval_when_approved_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, record_id, _plugin_root, record = self.create_meeting_followup_draft(Path(temp))
            self.edit_draft_skill(record, "\nLocal proposal edit.\n")
            staged = stage_proposal(
                aiws_root,
                record_id,
                "project:checkout",
                None,
                "Improve meeting follow-up",
                "The current instructions miss owner handoffs.",
                backend_kind="google_drive",
                backend_ref="drive-folder-123",
                marketplace_id="checkout-main",
            )
            drive_client = FakeGoogleDriveClient()
            submit_pr(
                aiws_root,
                staged["proposal_id"],
                GoogleDriveProposalSubmitter(aiws_root=aiws_root, drive_client=drive_client),
            )
            proposal_before = self.proposal_payload(aiws_root, staged["proposal_id"])
            drive_client.move_file(
                str(proposal_before["proposal_folder_id"]),
                str(proposal_before["approved_folder_id"]),
            )
            refresh_proposal_state(aiws_root, staged["proposal_id"], drive_client=drive_client)

            drive_client.overwrite_text_file("file-2", "changed after approval")

            result = refresh_proposal_state(
                aiws_root,
                staged["proposal_id"],
                drive_client=drive_client,
            )

            self.assertEqual(result["status"], "needs_reapproval")
            self.assertEqual(result["backend_review_state"], "in_review")
            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["status"], "needs_reapproval")
            self.assertEqual(proposal["backend_review_state"], "in_review")
            self.assertEqual(drive_client.files_by_id[str(proposal["proposal_folder_id"])]["parents"], [proposal["in_review_folder_id"]])

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
            self.assertEqual(second["repository_review_policy"]["status"], "unknown")
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

    def test_submit_pr_returns_post_merge_marketplace_delivery_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )

            result = submit_pr(aiws_root, staged["proposal_id"], FakeProposalSubmitter())

            guidance = result["post_merge_delivery"]
            self.assertEqual(guidance["status"], "marketplace_update_required_after_merge")
            self.assertFalse(guidance["normal_user_manual_zip_upload_required"])
            self.assertEqual(guidance["local_activation"], "technical_pilot_fallback_only")
            self.assertIn("Wait for maintainer review", guidance["regular_user_next_step"])
            self.assertEqual(
                [path["marketplace_type"] for path in guidance["delivery_paths"]],
                ["github_synced", "manual"],
            )
            self.assertIn("review-repo", guidance["delivery_paths"][0]["maintainer_action"])

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
            self.assertEqual(result["post_merge_delivery"]["status"], "marketplace_update_required_after_merge")
            self.assertFalse(result["post_merge_delivery"]["normal_user_manual_zip_upload_required"])
            self.assertEqual(result["repository_review_policy"]["status"], "unknown")
            self.assertFalse(result["repository_review_policy"]["normal_user_selects_reviewers"])
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
            self.assertEqual(result["repository_review_policy"]["status"], "absent")
            self.assertEqual(result["repository_review_policy"]["codeowners"], "not_detected")
            self.assertFalse(result["repository_review_policy"]["normal_user_selects_reviewers"])
            proposal = self.proposal_payload(aiws_root, staged["proposal_id"])
            self.assertEqual(proposal["repository_review_policy"]["status"], "absent")
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
            self.assertIn("Post-merge Cowork delivery:", body)
            self.assertIn("GitHub-synced marketplace: trigger Cowork marketplace update/sync", body)
            self.assertIn("Manual marketplace: upload a new plugin ZIP with the same plugin name", body)
            self.assertIn("Regular users should not manually upload ZIP files for the normal path.", body)
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
            self.assertEqual(result["repository_review_policy"]["status"], "present")
            self.assertEqual(result["repository_review_policy"]["codeowners"], "detected")
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
            self.assertIn("Post-merge Cowork delivery:", body)
            self.assertNotIn("Required review role", body)
            self.assertNotIn("AI engineer", body)

    def test_github_api_submitter_creates_branch_commit_and_pr_without_gh(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            self.set_proposal_target_repo(aiws_root, staged["proposal_id"], "example/review")
            api_client = FakeGitHubApiClient()
            submitter = GitHubApiProposalSubmitter(aiws_root=aiws_root, api_client=api_client)

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(result["status"], "submitted_for_review")
            self.assertEqual(result["pr_url"], "https://github.com/example/review/pull/8")
            self.assertEqual(result["repository_review_policy"]["status"], "absent")
            self.assertEqual(result["repository_review_policy"]["codeowners"], "not_detected")
            self.assertFalse(result["repository_review_policy"]["normal_user_selects_reviewers"])
            calls = [(method, path) for method, path, _payload, _query in api_client.calls]
            self.assertIn(("POST", "/repos/example/review/git/blobs"), calls)
            self.assertIn(("POST", "/repos/example/review/git/trees"), calls)
            self.assertIn(("POST", "/repos/example/review/git/commits"), calls)
            self.assertIn(("POST", "/repos/example/review/git/refs"), calls)
            self.assertIn(("POST", "/repos/example/review/pulls"), calls)
            tree_payload = next(
                payload
                for method, path, payload, _query in api_client.calls
                if method == "POST" and path == "/repos/example/review/git/trees"
            )
            self.assertIn(
                {
                    "path": "example-plugin/skills/meeting-followup/SKILL.md",
                    "mode": "100644",
                    "type": "blob",
                    "sha": None,
                },
                tree_payload["tree"],
            )
            self.assertTrue(
                any(
                    entry["path"] == "example-plugin/skills/meeting-followup/SKILL.md"
                    and entry["sha"] == "new-blob-1"
                    for entry in tree_payload["tree"]
                )
            )
            pr_payload = next(
                payload
                for method, path, payload, _query in api_client.calls
                if method == "POST" and path == "/repos/example/review/pulls"
            )
            self.assertFalse(pr_payload["draft"])
            self.assertIn("CODEOWNERS: not_detected", pr_payload["body"])
            self.assertIn("Post-merge Cowork delivery:", pr_payload["body"])
            self.assertNotIn("AI engineer", pr_payload["body"])

    def test_github_api_submitter_no_changes_keeps_proposal_staged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            aiws_root, _record_id, _plugin_root, _record, staged = self.create_staged_meeting_followup_proposal(
                Path(temp)
            )
            self.set_proposal_target_repo(aiws_root, staged["proposal_id"], "example/review")
            submitter = GitHubApiProposalSubmitter(aiws_root=aiws_root, api_client=FakeGitHubApiClient(no_changes=True))

            result = submit_pr(aiws_root, staged["proposal_id"], submitter)

            self.assertEqual(result["status"], "no_changes_to_submit")
            self.assertEqual(self.proposal_payload(aiws_root, staged["proposal_id"])["status"], "staged")

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

    def test_create_or_open_draft_rejects_parallel_origin_when_active_draft_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            aiws_root = temp_root / ".aiws"
            plugin_root = self.write_plugin(temp_root, public_skills=["meeting-followup"])
            self.write_skill(plugin_root, "meeting-followup")

            first = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/first-review",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
            )
            first_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/first-review")
            write_draft_file(
                aiws_root,
                first_id,
                "skills/meeting-followup/SKILL.md",
                (Path(first.draft_path) / "skills" / "meeting-followup" / "SKILL.md").read_text()
                + "\nLocal draft edit.\n",
            )

            with self.assertRaisesRegex(SkillManagerError, "Existing active draft"):
                create_or_open_draft(
                    aiws_root,
                    source_plugin_root=plugin_root,
                    plugin_id="example-plugin",
                    skill_id="meeting-followup",
                    origin_marketplace="ai-workspace",
                    origin_repo="https://github.com/example/second-review",
                    origin_ref="master",
                    base_version="1.0.0",
                    base_commit="abc123",
                )

            second_id = draft_id("example-plugin", "meeting-followup", "https://github.com/example/second-review")
            self.assertFalse(draft_record_path(aiws_root, second_id).exists())

            second = create_or_open_draft(
                aiws_root,
                source_plugin_root=plugin_root,
                plugin_id="example-plugin",
                skill_id="meeting-followup",
                origin_marketplace="ai-workspace",
                origin_repo="https://github.com/example/second-review",
                origin_ref="master",
                base_version="1.0.0",
                base_commit="abc123",
                allow_parallel_draft=True,
            )

            self.assertTrue(draft_record_path(aiws_root, second_id).exists())
            self.assertNotEqual(Path(second.draft_path), Path(first.draft_path))

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

    def copy_plugin_with_skill_edit(self, temp_root: Path, plugin_root: Path, name: str, edit: str) -> Path:
        destination = temp_root / name
        shutil.copytree(plugin_root, destination)
        self.update_plugin_version_and_skill(destination, version="1.1.0", edit=edit)
        return destination

    def update_plugin_version_and_skill(self, plugin_root: Path, *, version: str, edit: str) -> None:
        manifest_path = plugin_root / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["version"] = version
        manifest_path.write_text(json.dumps(manifest))
        contract_path = plugin_root / "contracts" / "example-plugin.contract.json"
        contract = json.loads(contract_path.read_text())
        contract["version"] = version
        contract_path.write_text(json.dumps(contract))
        skill_file = plugin_root / "skills" / "meeting-followup" / "SKILL.md"
        skill_file.write_text(skill_file.read_text() + edit)

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
