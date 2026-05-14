from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path


from scripts.cowork_package_intake_probe import (
    PROBE_SKILL_ID,
    ProbeError,
    build_probe_package,
    copy_probe_to_upload_surface,
    load_cowork_package_upload_surface,
    prepare_probe_handoff,
    probe_plugin_id,
)


class CoworkPackageIntakeProbeTests(unittest.TestCase):
    def test_build_probe_package_uses_unique_throwaway_plugin_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_id = probe_plugin_id("20260514112233")
            package_path = build_probe_package(Path(temp), plugin_id=plugin_id)

            with zipfile.ZipFile(package_path) as package:
                names = set(package.namelist())
                manifest = json.loads(package.read(".claude-plugin/plugin.json"))
                contract = json.loads(package.read(f"contracts/{plugin_id}.contract.json"))
                skill = package.read(f"skills/{PROBE_SKILL_ID}/SKILL.md").decode("utf-8")

        self.assertEqual(package_path.name, f"{plugin_id}-0.1.0.zip")
        self.assertEqual(
            names,
            {
                ".claude-plugin/plugin.json",
                f"contracts/{plugin_id}.contract.json",
                f"skills/{PROBE_SKILL_ID}/SKILL.md",
            },
        )
        self.assertEqual(manifest["name"], plugin_id)
        self.assertEqual(contract["plugin_id"], plugin_id)
        self.assertEqual(contract["public_skills"], [PROBE_SKILL_ID])
        self.assertIn(f"AIWS_COWORK_PACKAGE_INTAKE_PROBE_LOADED {plugin_id}", skill)

    def test_prepare_probe_handoff_reads_existing_host_evidence_and_copies_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            aiws_root = root / ".aiws"
            upload_root = root / ".cowork" / "packages"
            output_dir = root / "dist"
            upload_root.mkdir(parents=True)
            self.write_cowork_host(aiws_root, "cowork-test", upload_root)

            result = prepare_probe_handoff(
                aiws_root=aiws_root,
                host_id="cowork-test",
                output_dir=output_dir,
                timestamp="20260514112233",
            )

            copied = Path(result["copied_package_path"])
            self.assertEqual(result["status"], "package_copied_to_upload_surface")
            self.assertEqual(result["plugin_id"], "aiws-cowork-package-intake-probe-20260514112233")
            self.assertEqual(result["skill_id"], PROBE_SKILL_ID)
            self.assertTrue(copied.is_file())
            self.assertEqual(copied.parent, upload_root.resolve())
            self.assertFalse((aiws_root / "hosts" / "cowork-other").exists())
            self.assertIn("remove or disable", result["cleanup_required_if_imported"])
            with self.assertRaisesRegex(ProbeError, "will not be overwritten"):
                prepare_probe_handoff(
                    aiws_root=aiws_root,
                    host_id="cowork-test",
                    output_dir=output_dir / "again",
                    timestamp="20260514112233",
                )

    def test_load_package_upload_surface_requires_existing_cowork_host_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ProbeError, "host record not found"):
                load_cowork_package_upload_surface(root / ".aiws", host_id="cowork-test")

            upload_root = root / ".cowork" / "packages"
            upload_root.mkdir(parents=True)
            self.write_cowork_host(root / ".aiws", "cowork-test", upload_root, host_kind="codex")
            with self.assertRaisesRegex(ProbeError, "not for host_kind='cowork'"):
                load_cowork_package_upload_surface(root / ".aiws", host_id="cowork-test")

    def test_copy_probe_to_upload_surface_rejects_symlink_root_and_missing_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package_path = build_probe_package(root / "dist", plugin_id=probe_plugin_id("20260514112233"))
            target = root / "target"
            symlink_root = root / "upload-link"
            target.mkdir()
            symlink_root.symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(ProbeError, "must not contain symlinks|must not be a symlink"):
                copy_probe_to_upload_surface(package_path, symlink_root)
            with self.assertRaisesRegex(ProbeError, "must already exist"):
                copy_probe_to_upload_surface(package_path, root / "missing")

    def test_copy_probe_to_upload_surface_rejects_symlink_package_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package_path = build_probe_package(root / "dist", plugin_id=probe_plugin_id("20260514112233"))
            upload_root = root / "upload"
            upload_root.mkdir()
            package_link = root / "probe-link.zip"
            package_link.symlink_to(package_path)

            with self.assertRaisesRegex(ProbeError, "must not be a symlink"):
                copy_probe_to_upload_surface(package_link, upload_root)

    def write_cowork_host(
        self,
        aiws_root: Path,
        host_id: str,
        upload_root: Path,
        *,
        host_kind: str = "cowork",
    ) -> None:
        host_root = aiws_root / "hosts" / host_id
        host_root.mkdir(parents=True)
        (host_root / "host.json").write_text(
            json.dumps(
                {
                    "host_id": host_id,
                    "host_kind": host_kind,
                    "evidence_surfaces": [
                        {
                            "name": "package_uploads",
                            "kind": "directory",
                            "path": str(upload_root),
                            "writable": True,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
