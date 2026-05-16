from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class AiwsReleaseWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name) / "repo"
        shutil.copytree(
            REPO_ROOT,
            self.repo,
            ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "dist", "build"),
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_prepare_plugin_release_bumps_plugin_contract_and_marketplace_entry(self) -> None:
        from scripts.aiws_release import choose_next_version, prepare_plugin_release

        current = _read_json(self.repo / "aiws-productivity" / ".claude-plugin" / "plugin.json")["version"]
        expected = choose_next_version(current, bump_type="patch")

        result = prepare_plugin_release(self.repo, "aiws-productivity", bump_type="patch")

        plugin = _read_json(self.repo / "aiws-productivity" / ".claude-plugin" / "plugin.json")
        contract = _read_json(self.repo / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json")
        marketplace = _read_json(self.repo / ".claude-plugin" / "marketplace.json")
        entry = next(item for item in marketplace["plugins"] if item["name"] == "aiws-productivity")

        self.assertEqual(result["old_version"], current)
        self.assertEqual(result["new_version"], expected)
        self.assertEqual(plugin["version"], expected)
        self.assertEqual(contract["version"], expected)
        self.assertEqual(entry["version"], expected)
        self.assertEqual(marketplace["metadata"]["version"], "0.3.21")

    def test_prepare_plugin_release_rejects_invalid_or_ambiguous_version_inputs(self) -> None:
        from scripts.aiws_release import ReleaseError, prepare_plugin_release

        cases = [
            {"bump_type": "patch", "explicit_version": "0.2.3"},
            {},
            {"bump_type": "banana"},
            {"explicit_version": "not-semver"},
            {"explicit_version": "0.2.2"},
            {"explicit_version": "0.2.1"},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ReleaseError):
                    prepare_plugin_release(self.repo, "aiws-productivity", **kwargs)

    def test_prepare_plugin_release_rejects_existing_metadata_drift(self) -> None:
        from scripts.aiws_release import ReleaseError, prepare_plugin_release

        contract_path = self.repo / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json"
        contract = _read_json(contract_path)
        contract["version"] = "9.9.9"
        _write_json(contract_path, contract)

        with self.assertRaisesRegex(ReleaseError, "version drift"):
            prepare_plugin_release(self.repo, "aiws-productivity", bump_type="patch")

    def test_validate_plugin_release_uses_contract_schema(self) -> None:
        from scripts.aiws_release import ReleaseError, validate_plugin_release

        contract_path = self.repo / "aiws-productivity" / "contracts" / "aiws-productivity.contract.json"
        contract = _read_json(contract_path)
        contract["unexpected"] = True
        _write_json(contract_path, contract)

        with self.assertRaisesRegex(ReleaseError, "additional property"):
            validate_plugin_release(self.repo, "aiws-productivity")

    def test_scaffold_install_check_idempotency_and_drift(self) -> None:
        from scripts.aiws_repo_scaffold import check_scaffold, install_scaffold

        shutil.rmtree(self.repo / ".github", ignore_errors=True)
        (self.repo / "docs" / "aiws-maintainer-release-runbook.md").unlink(missing_ok=True)

        result = install_scaffold(self.repo)
        self.assertEqual(result["status"], "installed")
        self.assertGreaterEqual(len(result["written"]), 2)
        self.assertEqual(check_scaffold(self.repo)["status"], "ok")
        self.assertEqual(install_scaffold(self.repo)["status"], "unchanged")

        workflow = self.repo / ".github" / "workflows" / "aiws-release-plugin.yml"
        workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# local edit\n", encoding="utf-8")

        drift = check_scaffold(self.repo)
        self.assertEqual(drift["status"], "drift")
        self.assertIn(".github/workflows/aiws-release-plugin.yml", drift["changed"])
        refused = install_scaffold(self.repo)
        self.assertEqual(refused["status"], "refused")
        self.assertIn(".github/workflows/aiws-release-plugin.yml", refused["changed"])

        forced = install_scaffold(self.repo, force=True)
        self.assertEqual(forced["status"], "installed")
        self.assertEqual(check_scaffold(self.repo)["status"], "ok")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
