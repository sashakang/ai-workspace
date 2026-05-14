from __future__ import annotations

import argparse
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROBE_PREFIX = "aiws-cowork-package-intake-probe"
PROBE_SKILL_ID = "intake-probe"
PROBE_VERSION = "0.1.0"
PROBE_ID_RE = re.compile(r"^aiws-cowork-package-intake-probe-[0-9]{14}$")


class ProbeError(ValueError):
    pass


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def probe_plugin_id(timestamp: str | None = None) -> str:
    value = timestamp or utc_timestamp()
    if not re.fullmatch(r"[0-9]{14}", value):
        raise ProbeError("timestamp must be in yyyymmddhhmmss format.")
    return f"{PROBE_PREFIX}-{value}"


def validate_probe_id(plugin_id: str) -> str:
    if not PROBE_ID_RE.fullmatch(plugin_id):
        raise ProbeError(f"Invalid probe plugin id: {plugin_id!r}")
    return plugin_id


def build_probe_package(output_dir: Path, *, plugin_id: str) -> Path:
    plugin_id = validate_probe_id(plugin_id)
    output_dir = output_dir.expanduser().resolve()
    reject_existing_symlink_components(output_dir.parent, label="Probe output parent")
    if output_dir.is_symlink():
        raise ProbeError(f"Probe output directory must not be a symlink: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise ProbeError(f"Probe output path is not a directory: {output_dir}")

    package_path = output_dir / f"{plugin_id}-{PROBE_VERSION}.zip"
    if package_path.exists():
        raise ProbeError(f"Probe package already exists and will not be overwritten: {package_path}")

    manifest = {
        "name": plugin_id,
        "version": PROBE_VERSION,
        "description": "Disposable AIWS probe for Cowork package intake detection.",
    }
    contract = {
        "plugin_id": plugin_id,
        "version": PROBE_VERSION,
        "public_skills": [PROBE_SKILL_ID],
    }
    skill = (
        "---\n"
        f"name: {PROBE_SKILL_ID}\n"
        "description: Report whether a disposable Cowork package intake probe loaded.\n"
        "---\n\n"
        "# Intake Probe\n\n"
        "When invoked, respond with this exact marker and no extra diagnosis unless asked:\n\n"
        f"`AIWS_COWORK_PACKAGE_INTAKE_PROBE_LOADED {plugin_id}`\n"
    )

    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as package:
        write_zip_json(package, ".claude-plugin/plugin.json", manifest)
        write_zip_json(package, f"contracts/{plugin_id}.contract.json", contract)
        write_zip_text(package, f"skills/{PROBE_SKILL_ID}/SKILL.md", skill)
    return package_path


def write_zip_json(package: zipfile.ZipFile, archive_name: str, payload: dict[str, Any]) -> None:
    write_zip_text(package, archive_name, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_zip_text(package: zipfile.ZipFile, archive_name: str, content: str) -> None:
    if archive_name.startswith("/") or ".." in Path(archive_name).parts:
        raise ProbeError(f"Unsafe archive path: {archive_name}")
    info = zipfile.ZipInfo(archive_name)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    package.writestr(info, content.encode("utf-8"))


def load_cowork_package_upload_surface(aiws_root: Path, *, host_id: str) -> Path:
    validate_host_id(host_id)
    host_json = aiws_root.expanduser() / "hosts" / host_id / "host.json"
    reject_existing_symlink_components(host_json.parent, label="Host record parent")
    if host_json.is_symlink():
        raise ProbeError(f"Host record must not be a symlink: {host_json}")
    if not host_json.is_file():
        raise ProbeError(f"Existing Cowork host record not found: {host_json}")
    payload = json.loads(host_json.read_text(encoding="utf-8"))
    if payload.get("host_id") != host_id:
        raise ProbeError("Host record host_id does not match the requested host_id.")
    if payload.get("host_kind") != "cowork":
        raise ProbeError("Host record is not for host_kind='cowork'.")
    surfaces = payload.get("evidence_surfaces")
    if not isinstance(surfaces, list):
        raise ProbeError("Host record does not contain evidence_surfaces.")
    for surface in surfaces:
        if not isinstance(surface, dict):
            continue
        if (
            surface.get("name") == "package_uploads"
            and surface.get("kind") == "directory"
            and surface.get("writable") is True
        ):
            path = surface.get("path")
            if not isinstance(path, str) or not path:
                raise ProbeError("package_uploads surface has no path.")
            return Path(path).expanduser()
    raise ProbeError("Writable Cowork package_uploads surface not found in existing host evidence.")


def copy_probe_to_upload_surface(package_path: Path, upload_root: Path) -> Path:
    package_path = package_path.expanduser()
    reject_existing_symlink_components(package_path.parent, label="Probe package parent")
    if package_path.is_symlink():
        raise ProbeError(f"Probe package must not be a symlink: {package_path}")
    if not package_path.is_file():
        raise ProbeError(f"Probe package must be a regular file: {package_path}")
    package_path = package_path.resolve()
    upload_root = upload_root.expanduser()
    reject_existing_symlink_components(upload_root, label="Cowork package upload root")
    if upload_root.is_symlink():
        raise ProbeError(f"Cowork package upload root must not be a symlink: {upload_root}")
    if not upload_root.is_dir():
        raise ProbeError(f"Cowork package upload root must already exist: {upload_root}")
    resolved_upload_root = upload_root.resolve()
    destination = resolved_upload_root / package_path.name
    reject_existing_symlink_components(destination.parent, label="Cowork package destination parent")
    if destination.exists():
        raise ProbeError(f"Cowork package destination already exists and will not be overwritten: {destination}")
    destination.relative_to(resolved_upload_root)
    with destination.open("xb") as handle:
        handle.write(package_path.read_bytes())
    return destination


def prepare_probe_handoff(
    *,
    aiws_root: Path,
    host_id: str,
    output_dir: Path,
    timestamp: str | None = None,
) -> dict[str, Any]:
    plugin_id = probe_plugin_id(timestamp)
    package_path = build_probe_package(output_dir, plugin_id=plugin_id)
    upload_root = load_cowork_package_upload_surface(aiws_root, host_id=host_id)
    copied_path = copy_probe_to_upload_surface(package_path, upload_root)
    return {
        "status": "package_copied_to_upload_surface",
        "plugin_id": plugin_id,
        "skill_id": PROBE_SKILL_ID,
        "probe_marker": f"AIWS_COWORK_PACKAGE_INTAKE_PROBE_LOADED {plugin_id}",
        "package_path": str(package_path),
        "copied_package_path": str(copied_path),
        "cowork_install_confirmation": "unavailable_until_new_cowork_chat_checks_visibility",
        "success_criteria": (
            "Start a new Cowork chat without using Settings > Plugins > Upload a file. "
            f"The probe succeeds only if {plugin_id}:{PROBE_SKILL_ID} is visible and callable."
        ),
        "cleanup_required_if_imported": (
            "If Cowork shows the probe plugin or intake-probe skill, remove or disable that probe plugin "
            "through Cowork plugin settings. If cleanup is unavailable, record the plugin id and copied path."
        ),
        "reuse_allowed": False,
    }


def validate_host_id(host_id: str) -> None:
    if (
        not host_id
        or host_id in {".", ".."}
        or host_id.startswith(".")
        or "/" in host_id
        or "\\" in host_id
        or Path(host_id).is_absolute()
        or Path(host_id).name != host_id
    ):
        raise ProbeError(f"Invalid host_id: {host_id!r}")


def reject_existing_symlink_components(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor) if absolute.anchor else Path()
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for part in parts:
        current = current / part
        if current.parent == Path(current.anchor):
            continue
        if current.is_symlink():
            raise ProbeError(f"{label} must not contain symlinks: {path}")
        if not current.exists():
            break


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a disposable Cowork package intake probe.")
    parser.add_argument("--aiws-root", type=Path, default=Path("~/.aiws"))
    parser.add_argument("--host-id", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("dist/cowork-package-intake-probe"))
    parser.add_argument("--timestamp", help="Optional yyyymmddhhmmss probe suffix for deterministic tests.")
    args = parser.parse_args()
    result = prepare_probe_handoff(
        aiws_root=args.aiws_root,
        host_id=args.host_id,
        output_dir=args.output_dir,
        timestamp=args.timestamp,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
