# Cowork Package Intake Probe: No Automatic Intake Observed - 2026-05-24

## Result

FAIL for automatic package intake.

This is not an AIWS handoff failure. AIWS prepared the package handoff correctly, but Cowork did not automatically consume the ZIP copied to its `package_uploads` surface in a fresh Cowork session.

## AIWS-Side Handoff Evidence

Fresh `aiws.host.surfaces` evidence for `host_kind=cowork` showed:

- `host_id`: `cowork-db8a0e250a1c`
- `capability_exposure`: `plugin-package`
- `direct_host_install_supported`: `false`
- `package_uploads`: `/Users/aleksanderkan/.cowork/packages`
- `package_uploads` exists: `true`
- `package_uploads` is a directory: `true`
- `package_uploads` writable: `true`
- `package_uploads` writable_effective: `true`

`aiws.host.install` then returned:

```text
status: handoff_prepared
copied_package_path: /Users/aleksanderkan/.cowork/packages/aiws-generated-plugin.zip
requires_cowork_confirmation: true
requires_manual_upload: false
activation_effective: false
```

This confirms only the AIWS handoff boundary.

## Disposable Probe Evidence

The disposable intake probe was prepared with:

```text
status: package_copied_to_upload_surface
plugin_id: aiws-cowork-package-intake-probe-20260524061508
skill_id: intake-probe
probe_marker: AIWS_COWORK_PACKAGE_INTAKE_PROBE_LOADED aiws-cowork-package-intake-probe-20260524061508
package_path: /Users/aleksanderkan/projects/ai-workspace/dist/cowork-package-intake-probe/aiws-cowork-package-intake-probe-20260524061508-0.1.0.zip
copied_package_path: /Users/aleksanderkan/.cowork/packages/aiws-cowork-package-intake-probe-20260524061508-0.1.0.zip
```

Focused probe tests passed:

```text
tests/test_cowork_package_intake_probe.py: 5 passed
```

## Cowork Confirmation

In a fresh Cowork session, without using Settings > Plugins > Upload a file and without any manual install/upload action, Cowork reported:

```text
probe plugin visible: no
intake-probe skill visible: no
intake-probe callable: no
marker returned: no
manual upload/install used: no
result: FAIL
```

The probe plugin `aiws-cowork-package-intake-probe-20260524061508` was not found among installed plugins, and skill lookup did not return `intake-probe` or the probe plugin identity.

## Interpretation

Cowork does not appear to automatically ingest packages copied into `/Users/aleksanderkan/.cowork/packages` in this tested environment.

Keep these states separate:

- AIWS `handoff_prepared`: PASS.
- Cowork automatic package intake from `package_uploads`: FAIL / not observed.
- Cowork activation of the copied package: not effective.

The user-facing normal path should not depend on Cowork automatically watching the `package_uploads` directory unless future Cowork evidence proves that behavior changed.
