from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_PYTHONPATH = str(REPO_ROOT / "aiws-host-memory")
MANAGED_HOOK_EVENT = "SessionEnd"
MANAGED_HOOK_COMMAND = "aiws-host-memory refresh-shared"
INFRA_PLUGIN_IDS = ("core-aiws", "memory-aiws")
OPTIONAL_PLUGIN_IDS = ("data-analysis-aiws", "software-engineer-aiws")


class HostMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.installs_root = self.workspace / "installs"
        self.claude_home = self.workspace / "claude-home"
        self.cowork_home = self.workspace / "cowork-home"
        self.plugin_data_root = self.claude_home / "plugins" / "data"
        self.helper_home = self.claude_home / "aiws-host-memory"
        self.cowork_plugin_data_root = self.cowork_home / "plugins" / "data"
        self.cowork_helper_home = self.cowork_home / "aiws-host-memory"
        self.settings_path = self.claude_home / "settings.json"
        self.marketplaces = {"claude": {}, "cowork": {}}
        self.installs = self._copy_plugins()
        self.cowork_installs = {
            plugin_id: {
                "root": payload["root"],
                "data": self.cowork_plugin_data_root / f"{plugin_id}-ai-workspace",
            }
            for plugin_id, payload in self.installs.items()
        }

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _copy_plugins(self) -> dict[str, dict[str, Path]]:
        installs: dict[str, dict[str, Path]] = {}
        for plugin_id in INFRA_PLUGIN_IDS + OPTIONAL_PLUGIN_IDS:
            source = REPO_ROOT / plugin_id
            target = self.installs_root / plugin_id
            shutil.copytree(source, target)
            installs[plugin_id] = {
                "root": target,
                "data": self.plugin_data_root / f"{plugin_id}-ai-workspace",
            }
        return installs

    def helper_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = HELPER_PYTHONPATH
        return env

    def plugin_data_path(self, plugin_id: str, *, marketplace: str = "ai-workspace", host: str = "claude") -> Path:
        data_root = self.plugin_data_root if host == "claude" else self.cowork_plugin_data_root
        return data_root / f"{plugin_id}-{marketplace}"

    def current_plugin_data_path(self, plugin_id: str, *, host: str = "claude") -> Path:
        marketplace = self.marketplaces[host].get(plugin_id, "ai-workspace")
        return self.plugin_data_path(plugin_id, marketplace=marketplace, host=host)

    def write_installed_plugins(
        self,
        plugin_ids: tuple[str, ...] | list[str],
        *,
        host: str = "claude",
    ) -> None:
        install_map = self.installs if host == "claude" else self.cowork_installs
        host_root = self.claude_home if host == "claude" else self.cowork_home
        plugins: dict[str, list[dict[str, str]]] = {}
        for item in plugin_ids:
            if isinstance(item, tuple):
                plugin_id, marketplace = item
            else:
                plugin_id, marketplace = item, "ai-workspace"
            self.marketplaces[host][plugin_id] = marketplace
            plugins[f"{plugin_id}@{marketplace}"] = [
                {
                    "scope": "user",
                    "installPath": str(install_map[plugin_id]["root"]),
                    "version": "0.3.0",
                    "installedAt": "2026-04-16T00:00:00Z",
                    "lastUpdated": "2026-04-16T00:00:00Z",
                    "gitCommitSha": "test",
                }
            ]
        installed_path = host_root / "plugins" / "installed_plugins.json"
        installed_path.parent.mkdir(parents=True, exist_ok=True)
        installed_path.write_text(json.dumps({"plugins": plugins}))

    def run_helper(self, *args: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            "-m",
            "aiws_host_memory",
            "--helper-home",
            str(self.helper_home),
            "--settings-path",
            str(self.settings_path),
            "--claude-home",
            str(self.claude_home),
            *args,
        ]
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=self.helper_env(),
        )
        if expect_success and result.returncode != 0:
            self.fail(result.stdout + "\n" + result.stderr)
        return result

    def run_cowork_helper(self, *args: str, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            "-m",
            "aiws_host_memory",
            "--helper-home",
            str(self.cowork_helper_home),
            "--cowork-home",
            str(self.cowork_home),
            "--claude-home",
            str(self.claude_home),
            *args,
        ]
        result = subprocess.run(
            command,
            text=True,
            capture_output=True,
            env=self.helper_env(),
        )
        if expect_success and result.returncode != 0:
            self.fail(result.stdout + "\n" + result.stderr)
        return result

    def helper_json(self, *args: str, expect_success: bool = True) -> dict[str, object]:
        result = self.run_helper(*args, expect_success=expect_success)
        return json.loads(result.stdout)

    def cowork_helper_json(self, *args: str, expect_success: bool = True) -> dict[str, object]:
        result = self.run_cowork_helper(*args, expect_success=expect_success)
        return json.loads(result.stdout)

    def bootstrap_args(
        self,
        *,
        include_data_analysis: bool = True,
        extra_plugins: dict[str, dict[str, Path]] | None = None,
        trusted_marketplaces: tuple[str, ...] | list[str] | None = None,
    ) -> list[str]:
        args = [
            "bootstrap",
            "--core-plugin-root",
            str(self.installs["core-aiws"]["root"]),
            "--core-plugin-data",
            str(self.installs["core-aiws"]["data"]),
            "--memory-plugin-root",
            str(self.installs["memory-aiws"]["root"]),
            "--memory-plugin-data",
            str(self.installs["memory-aiws"]["data"]),
        ]
        if include_data_analysis:
            args.extend(
                [
                    "--data-analysis-plugin-root",
                    str(self.installs["data-analysis-aiws"]["root"]),
                    "--data-analysis-plugin-data",
                    str(self.installs["data-analysis-aiws"]["data"]),
                ]
            )
        if extra_plugins:
            for plugin_id, payload in extra_plugins.items():
                args.extend(["--plugin-root", f"{plugin_id}={payload['root']}"])
                args.extend(["--plugin-data", f"{plugin_id}={payload['data']}"])
        if trusted_marketplaces:
            for marketplace in trusted_marketplaces:
                args.extend(["--trusted-marketplace", marketplace])
        return args

    def run_stage_candidate(self, *extra: str) -> dict[str, object]:
        return self.run_stage_candidate_for_host("claude", *extra)

    def run_stage_candidate_for_host(self, host: str, *extra: str) -> dict[str, object]:
        marketplace = self.marketplaces[host].get("data-analysis-aiws", "ai-workspace")
        result = subprocess.run(
            [
                sys.executable,
                str(self.installs["data-analysis-aiws"]["root"] / "scripts" / "stage_shared_memory_candidate.py"),
                "--plugin-data",
                str(self.plugin_data_path("data-analysis-aiws", marketplace=marketplace, host=host)),
                *extra,
            ],
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(result.stdout)

    def load_settings(self) -> dict[str, object]:
        return json.loads(self.settings_path.read_text())

    def managed_hook_groups(self) -> list[dict[str, object]]:
        settings = self.load_settings()
        event_groups = settings.get("hooks", {}).get(MANAGED_HOOK_EVENT, [])
        return [
            group
            for group in event_groups
            if any(hook.get("command") == MANAGED_HOOK_COMMAND for hook in group.get("hooks", []))
        ]

    def test_bootstrap_preserves_existing_settings_and_is_idempotent(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(
                {
                    "theme": "dark",
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "echo unrelated",
                                    }
                                ]
                            }
                        ],
                        "PreToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "echo pre",
                                    }
                                ],
                            }
                        ],
                    },
                }
            )
        )

        first = self.helper_json(*self.bootstrap_args())
        self.assertEqual(first["status"], "ok")
        self.assertEqual(first["skipped_plugins"], {})
        registry = self.installs["core-aiws"]["data"] / "registry" / "plugins"
        self.assertTrue((registry / "core-aiws.json").exists())
        self.assertTrue((registry / "memory-aiws.json").exists())
        self.assertTrue((registry / "data-analysis-aiws.json").exists())
        self.assertTrue((self.installs["memory-aiws"]["data"] / "shared-memory").is_symlink())
        self.assertTrue((self.installs["core-aiws"]["data"] / "shared-memory").is_symlink())
        self.assertTrue((self.installs["data-analysis-aiws"]["data"] / "shared-memory").is_symlink())

        settings = self.load_settings()
        self.assertEqual(settings["theme"], "dark")
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 1)
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(len(settings["hooks"][MANAGED_HOOK_EVENT]), 1)
        self.assertEqual(len(self.managed_hook_groups()), 1)

        second = self.helper_json(*self.bootstrap_args())
        self.assertEqual(second["status"], "ok")
        settings = self.load_settings()
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(len(settings["hooks"][MANAGED_HOOK_EVENT]), 1)
        self.assertEqual(len(self.managed_hook_groups()), 1)

    def test_bootstrap_succeeds_with_infrastructure_only(self) -> None:
        payload = self.helper_json(*self.bootstrap_args(include_data_analysis=False))

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["registered_plugins"], ["core-aiws", "memory-aiws"])
        self.assertEqual(payload["skipped_plugins"], {})
        registry = self.installs["core-aiws"]["data"] / "registry" / "plugins"
        self.assertTrue((registry / "core-aiws.json").exists())
        self.assertTrue((registry / "memory-aiws.json").exists())
        self.assertFalse((registry / "data-analysis-aiws.json").exists())
        self.assertTrue((self.installs["core-aiws"]["data"] / "shared-memory").is_symlink())
        self.assertFalse(self.installs["data-analysis-aiws"]["data"].exists())

    def test_bootstrap_detects_optional_domain_plugins_from_installed_plugin_metadata(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws", "software-engineer-aiws"))

        payload = self.helper_json("bootstrap")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["registered_plugins"],
            ["core-aiws", "data-analysis-aiws", "memory-aiws", "software-engineer-aiws"],
        )
        self.assertEqual(payload["skipped_plugins"], {})
        registry = self.installs["core-aiws"]["data"] / "registry" / "plugins"
        self.assertTrue((registry / "data-analysis-aiws.json").exists())
        self.assertTrue((registry / "software-engineer-aiws.json").exists())
        self.assertTrue((self.installs["data-analysis-aiws"]["data"] / "shared-memory").is_symlink())
        self.assertFalse((self.installs["software-engineer-aiws"]["data"] / "shared-memory").exists())
        self.assertEqual(payload["trusted_marketplaces"], ["ai-workspace"])
        self.assertEqual(payload["plugins"]["data-analysis-aiws"]["marketplace_id"], "ai-workspace")

    def test_bootstrap_detects_plugins_from_multiple_trusted_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("data-analysis-aiws", "company-aiws"),
                ("software-engineer-aiws", "personal-aiws"),
            )
        )

        payload = self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "ai-workspace",
            "--trusted-marketplace",
            "company-aiws",
            "--trusted-marketplace",
            "personal-aiws",
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["registered_plugins"],
            ["core-aiws", "data-analysis-aiws", "memory-aiws", "software-engineer-aiws"],
        )
        self.assertEqual(payload["trusted_marketplaces"], ["ai-workspace", "company-aiws", "personal-aiws"])
        self.assertEqual(payload["plugins"]["data-analysis-aiws"]["marketplace_id"], "company-aiws")
        self.assertEqual(payload["plugins"]["software-engineer-aiws"]["marketplace_id"], "personal-aiws")
        self.assertEqual(
            payload["plugins"]["data-analysis-aiws"]["plugin_data"],
            str(self.plugin_data_path("data-analysis-aiws", marketplace="company-aiws")),
        )
        self.assertEqual(
            payload["plugins"]["software-engineer-aiws"]["plugin_data"],
            str(self.plugin_data_path("software-engineer-aiws", marketplace="personal-aiws")),
        )

    def test_bootstrap_ignores_untrusted_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("software-engineer-aiws", "company-aiws"),
            )
        )

        payload = self.helper_json("bootstrap")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["registered_plugins"], ["core-aiws", "memory-aiws"])
        self.assertFalse(self.plugin_data_path("software-engineer-aiws", marketplace="company-aiws").exists())

    def test_bootstrap_fails_for_duplicate_plugin_ids_across_trusted_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("data-analysis-aiws", "company-aiws"),
                ("data-analysis-aiws", "public-aiws"),
            )
        )

        failed = self.run_helper(
            "bootstrap",
            "--trusted-marketplace",
            "ai-workspace",
            "--trusted-marketplace",
            "company-aiws",
            "--trusted-marketplace",
            "public-aiws",
            expect_success=False,
        )

        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Duplicate plugin_id detected across trusted marketplaces", failed.stdout)

    def test_bootstrap_allows_plugin_lineage_to_move_between_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("data-analysis-aiws", "personal-aiws"),
            )
        )
        self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "ai-workspace",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )

        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("data-analysis-aiws", "company-aiws"),
            )
        )
        payload = self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "ai-workspace",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["plugins"]["data-analysis-aiws"]["marketplace_id"], "company-aiws")
        self.assertEqual(
            payload["plugins"]["data-analysis-aiws"]["plugin_data"],
            str(self.plugin_data_path("data-analysis-aiws", marketplace="company-aiws")),
        )
        config = json.loads((self.helper_home / "config.json").read_text())
        self.assertEqual(config["plugins"]["data-analysis-aiws"]["marketplace_id"], "company-aiws")
        self.assertEqual(
            config["plugins"]["data-analysis-aiws"]["plugin_data"],
            str(self.plugin_data_path("data-analysis-aiws", marketplace="company-aiws")),
        )

    def test_bootstrap_allows_duplicate_plugin_ids_when_explicit_override_disambiguates(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "ai-workspace"),
                ("memory-aiws", "ai-workspace"),
                ("data-analysis-aiws", "company-aiws"),
                ("data-analysis-aiws", "public-aiws"),
            )
        )

        payload = self.helper_json(
            *self.bootstrap_args(
                include_data_analysis=False,
                extra_plugins={"data-analysis-aiws": self.installs["data-analysis-aiws"]},
                trusted_marketplaces=("ai-workspace", "company-aiws", "public-aiws"),
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["registered_plugins"],
            ["core-aiws", "data-analysis-aiws", "memory-aiws"],
        )
        self.assertIsNone(payload["plugins"]["data-analysis-aiws"].get("marketplace_id"))
        self.assertIsNone(payload["plugins"]["data-analysis-aiws"].get("install_key"))

    def test_bootstrap_preserves_memory_runtime_when_memory_plugin_moves_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "personal-aiws"),
                ("memory-aiws", "personal-aiws"),
                ("data-analysis-aiws", "personal-aiws"),
            )
        )
        first = self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )
        self.run_stage_candidate(
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Memory lineage should survive marketplace moves.",
            "--evidence",
            "Seeded before moving memory-aiws.",
            "--confidence",
            "0.7",
        )
        self.helper_json("refresh-shared")

        self.write_installed_plugins(
            (
                ("core-aiws", "company-aiws"),
                ("memory-aiws", "company-aiws"),
                ("data-analysis-aiws", "company-aiws"),
            )
        )
        second = self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )

        self.assertNotEqual(first["plugins"]["memory-aiws"]["plugin_data"], second["plugins"]["memory-aiws"]["plugin_data"])
        entries = json.loads(
            (
                self.plugin_data_path("memory-aiws", marketplace="company-aiws")
                / "store"
                / "entries.json"
            ).read_text()
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["summary"], "Memory lineage should survive marketplace moves.")

    def test_bootstrap_preserves_pending_outbox_when_plugin_moves_marketplaces(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "personal-aiws"),
                ("memory-aiws", "personal-aiws"),
                ("data-analysis-aiws", "personal-aiws"),
            )
        )
        self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )
        stage = self.run_stage_candidate(
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Pending candidate should survive plugin moves.",
            "--evidence",
            "Staged before the marketplace switch.",
            "--confidence",
            "0.65",
        )
        outbox_file = Path(stage["outbox_file"])
        self.assertTrue(outbox_file.exists())

        self.write_installed_plugins(
            (
                ("core-aiws", "company-aiws"),
                ("memory-aiws", "company-aiws"),
                ("data-analysis-aiws", "company-aiws"),
            )
        )
        self.helper_json(
            "bootstrap",
            "--trusted-marketplace",
            "personal-aiws",
            "--trusted-marketplace",
            "company-aiws",
        )
        refresh = self.helper_json("refresh-shared")

        self.assertEqual(refresh["accepted_candidates"], 1)
        moved_outbox = self.plugin_data_path("data-analysis-aiws", marketplace="company-aiws") / "_shared_memory_outbox"
        self.assertFalse(outbox_file.exists())
        self.assertTrue(moved_outbox.exists())

    def test_bootstrap_skips_optional_domain_with_missing_dependency(self) -> None:
        ghost_root = self.installs_root / "ghost-domain-aiws"
        shutil.copytree(self.installs["data-analysis-aiws"]["root"], ghost_root)
        contract = json.loads((ghost_root / "contracts" / "data-analysis-aiws.contract.json").read_text())
        contract["plugin_id"] = "ghost-domain-aiws"
        contract["dependencies"] = ["core-aiws", "memory-aiws", "missing-domain-aiws"]
        contract_path = ghost_root / "contracts" / "ghost-domain-aiws.contract.json"
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")

        payload = self.helper_json(
            *self.bootstrap_args(
                include_data_analysis=False,
                extra_plugins={
                    "ghost-domain-aiws": {
                        "root": ghost_root,
                        "data": self.plugin_data_root / "ghost-domain-aiws-ai-workspace",
                    }
                },
            )
        )

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["registered_plugins"], ["core-aiws", "memory-aiws"])
        self.assertEqual(
            payload["skipped_plugins"],
            {"ghost-domain-aiws": "missing dependencies: missing-domain-aiws"},
        )

    def test_bootstrap_repairs_drifted_hook(self) -> None:
        self.helper_json(*self.bootstrap_args())
        settings = self.load_settings()
        for group in settings["hooks"][MANAGED_HOOK_EVENT]:
            for hook in group.get("hooks", []):
                if hook.get("command") == MANAGED_HOOK_COMMAND:
                    hook["timeout"] = 5
                    hook["async"] = False
        self.settings_path.write_text(json.dumps(settings))

        self.helper_json(*self.bootstrap_args())

        managed = self.managed_hook_groups()
        self.assertEqual(len(managed), 1)
        self.assertEqual(
            managed[0],
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": MANAGED_HOOK_COMMAND,
                        "async": True,
                        "timeout": 120,
                    }
                ]
            },
        )

    def test_bootstrap_migrates_managed_hook_from_stop_to_session_end(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Write",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": MANAGED_HOOK_COMMAND,
                                    }
                                ],
                            }
                        ],
                        "Stop": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": MANAGED_HOOK_COMMAND,
                                        "async": True,
                                        "timeout": 120,
                                    }
                                ]
                            },
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "echo unrelated",
                                    }
                                ]
                            },
                        ]
                    }
                }
            )
        )

        self.helper_json(*self.bootstrap_args())

        settings = self.load_settings()
        self.assertEqual(len(settings["hooks"]["Stop"]), 1)
        self.assertEqual(settings["hooks"]["Stop"][0]["hooks"][0]["command"], "echo unrelated")
        self.assertEqual(len(settings["hooks"]["PreToolUse"]), 1)
        self.assertEqual(settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"], MANAGED_HOOK_COMMAND)
        self.assertEqual(len(settings["hooks"][MANAGED_HOOK_EVENT]), 1)
        self.assertEqual(len(self.managed_hook_groups()), 1)

    def test_bootstrap_rejects_malformed_legacy_stop_hooks(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": MANAGED_HOOK_COMMAND,
                                }
                            ]
                        }
                    }
                }
            )
        )

        failed = self.run_helper(*self.bootstrap_args(), expect_success=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("`hooks.Stop` must be a JSON array", failed.stdout)

    def test_partial_bootstrap_reports_error_then_recovers(self) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text("{not-json")

        failed = self.run_helper(*self.bootstrap_args(), expect_success=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("invalid JSON", failed.stdout)
        backups = list(self.settings_path.parent.glob("settings.json.bak-*"))
        self.assertEqual(len(backups), 1)

        self.assertTrue(self.helper_home.joinpath("config.json").exists())
        self.assertTrue((self.installs["core-aiws"]["data"] / "registry" / "plugins" / "memory-aiws.json").exists())
        self.assertTrue((self.installs["memory-aiws"]["data"] / "exports" / "latest").exists())

        doctor = self.run_helper("doctor", expect_success=False)
        self.assertNotEqual(doctor.returncode, 0)
        doctor_payload = json.loads(doctor.stdout)
        self.assertEqual(doctor_payload["status"], "error")
        self.assertTrue(any("Managed SessionEnd hook" in issue or "Settings file is invalid JSON" in issue for issue in doctor_payload["issues"]))

        self.settings_path.write_text(json.dumps({"hooks": {}}))
        self.helper_json(*self.bootstrap_args())
        doctor_ok = self.helper_json("doctor")
        self.assertEqual(doctor_ok["status"], "ok")
        self.assertEqual(doctor_ok["skipped_plugins"], {})

    def test_runtime_flow_updates_canonical_and_consumer_snapshots(self) -> None:
        self.helper_json(*self.bootstrap_args())
        stage = self.run_stage_candidate(
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Validate denominator stability before comparing rates.",
            "--evidence",
            "Seen in two different analyst projects.",
            "--confidence",
            "0.5",
        )
        outbox_file = Path(stage["outbox_file"])
        self.assertTrue(outbox_file.exists())

        refresh = self.helper_json("refresh-shared")
        self.assertEqual(refresh["accepted_candidates"], 1)
        self.assertFalse(outbox_file.exists())

        entries = json.loads((self.installs["memory-aiws"]["data"] / "store" / "entries.json").read_text())
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["scope"], "domains.data-analyst")

        analyst_readme = (
            self.installs["data-analysis-aiws"]["data"]
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Validate denominator stability before comparing rates.", analyst_readme)
        self.assertFalse(
            (
                self.installs["core-aiws"]["data"]
                / "shared-memory"
                / "domains"
                / "data-analyst"
                / "README.md"
            ).exists()
        )

    def test_runtime_flow_works_for_non_public_marketplace_plugins(self) -> None:
        self.write_installed_plugins(
            (
                ("core-aiws", "company-aiws"),
                ("memory-aiws", "company-aiws"),
                ("data-analysis-aiws", "company-aiws"),
            )
        )
        self.helper_json("bootstrap", "--trusted-marketplace", "company-aiws")
        stage = self.run_stage_candidate(
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Private marketplace entry.",
            "--evidence",
            "Captured from a company marketplace install.",
            "--confidence",
            "0.55",
        )
        outbox_file = Path(stage["outbox_file"])

        refresh = self.helper_json("refresh-shared")
        self.assertEqual(refresh["accepted_candidates"], 1)
        self.assertFalse(outbox_file.exists())
        analyst_readme = (
            self.plugin_data_path("data-analysis-aiws", marketplace="company-aiws")
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Private marketplace entry.", analyst_readme)

    def test_doctor_reports_duplicate_managed_hook(self) -> None:
        self.helper_json(*self.bootstrap_args())
        settings = self.load_settings()
        settings["hooks"][MANAGED_HOOK_EVENT].append(
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": MANAGED_HOOK_COMMAND,
                        "async": True,
                        "timeout": 120,
                    }
                ]
            }
        )
        self.settings_path.write_text(json.dumps(settings))

        doctor = self.run_helper("doctor", expect_success=False)
        self.assertNotEqual(doctor.returncode, 0)
        payload = json.loads(doctor.stdout)
        self.assertEqual(payload["hook"]["status"], "duplicate")

    def test_bootstrap_cowork_requires_bootstrapped_claude_canonical_store(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        failed = self.run_cowork_helper("bootstrap-cowork", expect_success=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Run `aiws-host-memory bootstrap` first", failed.stdout)
        self.assertFalse((self.cowork_helper_home / "config.json").exists())

    def test_bootstrap_cowork_uses_separate_state_and_imports(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        payload = self.cowork_helper_json("bootstrap-cowork")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["registered_plugins"],
            ["core-aiws", "data-analysis-aiws", "memory-aiws"],
        )
        self.assertEqual(
            payload["canonical_owner"]["claude_home"],
            str(self.claude_home),
        )
        self.assertTrue((self.cowork_helper_home / "config.json").exists())
        self.assertTrue((self.cowork_helper_home / "state.json").exists())
        self.assertTrue((self.cowork_installs["data-analysis-aiws"]["data"] / "shared-memory").is_symlink())
        self.assertTrue((self.cowork_installs["core-aiws"]["data"] / "registry" / "plugins" / "memory-aiws.json").exists())
        self.assertEqual(len(self.managed_hook_groups()), 1)

    def test_bootstrap_cowork_supports_non_public_trusted_marketplaces(self) -> None:
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="claude",
        )
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="cowork",
        )

        self.helper_json("bootstrap", "--trusted-marketplace", "company-aiws")
        payload = self.cowork_helper_json("bootstrap-cowork", "--trusted-marketplace", "company-aiws")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["trusted_marketplaces"], ["company-aiws"])
        self.assertEqual(payload["plugins"]["data-analysis-aiws"]["marketplace_id"], "company-aiws")

    def test_bootstrap_cowork_inherits_claude_trusted_marketplaces(self) -> None:
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="claude",
        )
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="cowork",
        )

        self.helper_json("bootstrap", "--trusted-marketplace", "company-aiws")
        payload = self.cowork_helper_json("bootstrap-cowork")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["trusted_marketplaces"], ["company-aiws"])
        self.assertEqual(
            payload["plugins"]["memory-aiws"]["plugin_data"],
            str(self.plugin_data_path("memory-aiws", marketplace="company-aiws", host="cowork")),
        )

    def test_bootstrap_cowork_uses_claude_helper_config_when_install_metadata_is_missing(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        payload = self.cowork_helper_json("bootstrap-cowork")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["canonical_owner"]["memory_plugin_data"], str(self.installs["memory-aiws"]["data"]))

    def test_refresh_cowork_updates_cowork_imports_only(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        self.cowork_helper_json("bootstrap-cowork")

        stage = self.run_stage_candidate_for_host(
            "cowork",
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Cowork-specific entry.",
            "--evidence",
            "Captured from the Cowork host.",
            "--confidence",
            "0.4",
        )
        outbox_file = Path(stage["outbox_file"])
        self.assertTrue(outbox_file.exists())

        refresh = self.cowork_helper_json("refresh-cowork")
        self.assertEqual(refresh["accepted_candidates"], 1)
        self.assertFalse(outbox_file.exists())

        cowork_readme = (
            self.current_plugin_data_path("data-analysis-aiws", host="cowork")
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Cowork-specific entry.", cowork_readme)

        claude_readme = (
            self.installs["data-analysis-aiws"]["data"]
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertNotIn("Cowork-specific entry.", claude_readme)

        self.helper_json("refresh-shared")
        claude_readme = (
            self.installs["data-analysis-aiws"]["data"]
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Cowork-specific entry.", claude_readme)

    def test_refresh_cowork_updates_non_public_marketplace_imports(self) -> None:
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="claude",
        )
        self.write_installed_plugins(
            (("core-aiws", "company-aiws"), ("memory-aiws", "company-aiws"), ("data-analysis-aiws", "company-aiws")),
            host="cowork",
        )

        self.helper_json("bootstrap", "--trusted-marketplace", "company-aiws")
        self.cowork_helper_json("bootstrap-cowork")

        self.run_stage_candidate_for_host(
            "cowork",
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Private Cowork entry.",
            "--evidence",
            "Captured from a non-public marketplace install.",
            "--confidence",
            "0.45",
        )

        refresh = self.cowork_helper_json("refresh-cowork")
        self.assertEqual(refresh["accepted_candidates"], 1)
        cowork_readme = (
            self.current_plugin_data_path("data-analysis-aiws", host="cowork")
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Private Cowork entry.", cowork_readme)

    def test_refresh_cowork_imports_latest_claude_entries(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        self.cowork_helper_json("bootstrap-cowork")

        self.run_stage_candidate(
            "--category",
            "workflow-pattern",
            "--scope",
            "domains.data-analyst",
            "--summary",
            "Claude-origin entry.",
            "--evidence",
            "Captured from Claude.",
            "--confidence",
            "0.6",
        )
        self.helper_json("refresh-shared")

        self.cowork_helper_json("refresh-cowork")
        cowork_readme = (
            self.cowork_installs["data-analysis-aiws"]["data"]
            / "shared-memory"
            / "domains"
            / "data-analyst"
            / "README.md"
        ).read_text()
        self.assertIn("Claude-origin entry.", cowork_readme)

    def test_bootstrap_cowork_rejects_missing_snapshot_version(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        metadata_path = self.installs["memory-aiws"]["data"] / "exports" / "latest" / "metadata.json"
        metadata_path.write_text(json.dumps({"generated_ts": "2026-04-16T00:00:00Z"}))

        failed = self.run_cowork_helper("bootstrap-cowork", expect_success=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("snapshot_version", failed.stdout)

    def test_doctor_cowork_reports_stale_canonical_root(self) -> None:
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="claude")
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"), host="cowork")

        self.helper_json(*self.bootstrap_args())
        self.cowork_helper_json("bootstrap-cowork")
        shutil.rmtree(self.installs["memory-aiws"]["data"] / "shared-memory-versions")
        (self.installs["memory-aiws"]["data"] / "shared-memory").unlink()

        doctor = self.run_cowork_helper("doctor-cowork", expect_success=False)
        self.assertNotEqual(doctor.returncode, 0)
        payload = json.loads(doctor.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertTrue(any("Stored Claude canonical root is missing" in issue for issue in payload["issues"]))


if __name__ == "__main__":
    unittest.main()
