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


class HostMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.tempdir.name)
        self.installs_root = self.workspace / "installs"
        self.claude_home = self.workspace / "claude-home"
        self.plugin_data_root = self.claude_home / "plugins" / "data"
        self.helper_home = self.claude_home / "aiws-host-memory"
        self.settings_path = self.claude_home / "settings.json"
        self.installs = self._copy_plugins()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _copy_plugins(self) -> dict[str, dict[str, Path]]:
        installs: dict[str, dict[str, Path]] = {}
        for plugin_id in ("core-aiws", "memory-aiws", "data-analysis-aiws"):
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

    def write_installed_plugins(self, plugin_ids: tuple[str, ...] | list[str]) -> None:
        plugins: dict[str, list[dict[str, str]]] = {}
        for plugin_id in plugin_ids:
            plugins[f"{plugin_id}@ai-workspace"] = [
                {
                    "scope": "user",
                    "installPath": str(self.installs[plugin_id]["root"]),
                    "version": "0.3.0",
                    "installedAt": "2026-04-16T00:00:00Z",
                    "lastUpdated": "2026-04-16T00:00:00Z",
                    "gitCommitSha": "test",
                }
            ]
        installed_path = self.claude_home / "plugins" / "installed_plugins.json"
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

    def helper_json(self, *args: str, expect_success: bool = True) -> dict[str, object]:
        result = self.run_helper(*args, expect_success=expect_success)
        return json.loads(result.stdout)

    def bootstrap_args(
        self,
        *,
        include_data_analysis: bool = True,
        extra_plugins: dict[str, dict[str, Path]] | None = None,
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
        return args

    def run_stage_candidate(self, *extra: str) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(self.installs["data-analysis-aiws"]["root"] / "scripts" / "stage_shared_memory_candidate.py"),
                "--plugin-data",
                str(self.installs["data-analysis-aiws"]["data"]),
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
        self.write_installed_plugins(("core-aiws", "memory-aiws", "data-analysis-aiws"))

        payload = self.helper_json("bootstrap")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(
            payload["registered_plugins"],
            ["core-aiws", "data-analysis-aiws", "memory-aiws"],
        )
        self.assertEqual(payload["skipped_plugins"], {})
        registry = self.installs["core-aiws"]["data"] / "registry" / "plugins"
        self.assertTrue((registry / "data-analysis-aiws.json").exists())
        self.assertTrue((self.installs["data-analysis-aiws"]["data"] / "shared-memory").is_symlink())

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


if __name__ == "__main__":
    unittest.main()
