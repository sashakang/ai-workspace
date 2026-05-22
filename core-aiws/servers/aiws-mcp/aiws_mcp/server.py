from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .runtime import AiwsRuntime


LOCAL_RUNTIME_KIND = "local-bundled-stdio"
LOCAL_RUNTIME_TRANSPORT = "stdio"
LOCAL_PROPOSAL_TOOL_NAMES = (
    "aiws.skills.stage_proposal",
    "aiws.skills.submit_for_review",
    "aiws.skills.refresh_proposal_state",
    "aiws.skills.publish_approved_proposal",
)
LOCAL_TOOL_NAMES = (
    "aiws.health.ping",
    "aiws.runtime.info",
    "aiws.runtime.update_status",
    "aiws.google_drive.start_oauth",
    "aiws.google_drive.configure_oauth_client",
    "aiws.google_drive.finish_oauth",
    "aiws.marketplaces.list",
    "aiws.marketplaces.drive_workflow",
    "aiws.marketplaces.register",
    "aiws.marketplaces.remove",
    "aiws.marketplaces.delete_artifact",
    "aiws.skills.search",
    "aiws.skills.resolve",
    "aiws.skills.materialize",
    "aiws.skills.list_local",
    "aiws.skills.get",
    "aiws.skills.discover_installed_plugins",
    "aiws.skills.inspect_installed_skill",
    "aiws.skills.create_or_open_draft",
    "aiws.skills.list_draft_files",
    "aiws.skills.read_draft_file",
    "aiws.skills.write_draft_file",
    "aiws.skills.delete_draft_file",
    "aiws.skills.refresh_draft",
    "aiws.skills.revert_draft",
    "aiws.skills.validate_draft",
    "aiws.skills.activate_draft",
    "aiws.skills.deactivate_draft",
    "aiws.skills.prepare_update_candidate",
    "aiws.skills.review_update_conflict",
    "aiws.skills.resolve_update_conflict",
    "aiws.skills.stage_proposal",
    "aiws.skills.submit_for_review",
    "aiws.skills.refresh_proposal_state",
    "aiws.skills.publish_approved_proposal",
    "aiws.skills.stage_change",
    "aiws.skills.list_staged_changes",
    "aiws.host.surfaces",
    "aiws.host.install",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _plugin_version(env: dict[str, str]) -> str | None:
    version = env.get("AIWS_MCP_PLUGIN_VERSION")
    if version:
        return version
    plugin_root = env.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return None
    manifest_path = Path(plugin_root).expanduser() / ".claude-plugin" / "plugin.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    raw_version = manifest.get("version")
    return raw_version if isinstance(raw_version, str) and raw_version else None


def _core_marketplace_latest_version(env: dict[str, str]) -> str | None:
    plugin_root = env.get("CLAUDE_PLUGIN_ROOT")
    if not plugin_root:
        return None
    root = Path(plugin_root).expanduser()
    candidate_paths = [
        root.parent / ".claude-plugin" / "marketplace.json",
        root.parent.parent / ".claude-plugin" / "marketplace.json",
    ]
    for marketplace_path in candidate_paths:
        if not marketplace_path.is_file():
            continue
        try:
            marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        plugins = marketplace.get("plugins")
        if not isinstance(plugins, list):
            continue
        for plugin in plugins:
            if not isinstance(plugin, dict) or plugin.get("name") != "core-aiws":
                continue
            version = plugin.get("version")
            return version if isinstance(version, str) and version else None
    return None


def runtime_info_payload(env: dict[str, str] | None = None) -> dict[str, Any]:
    resolved_env = dict(os.environ if env is None else env)
    plugin_root = resolved_env.get("CLAUDE_PLUGIN_ROOT")
    plugin_data = resolved_env.get("CLAUDE_PLUGIN_DATA")
    declared_tools = list(LOCAL_TOOL_NAMES)
    return {
        "status": "ok",
        "service": "aiws",
        "runtime_kind": LOCAL_RUNTIME_KIND,
        "transport": LOCAL_RUNTIME_TRANSPORT,
        "launch_mode": resolved_env.get("AIWS_MCP_LAUNCH_MODE", "unknown"),
        "plugin_version": _plugin_version(resolved_env),
        "declared_tools": declared_tools,
        "proposal_tools_declared": all(name in LOCAL_TOOL_NAMES for name in LOCAL_PROPOSAL_TOOL_NAMES),
        "diagnostics_enabled": bool(resolved_env.get("AIWS_MCP_STATUS_PATH") or resolved_env.get("AIWS_MCP_LOG_PATH")),
        "plugin_root_present": bool(plugin_root),
        "plugin_data_present": bool(plugin_data),
    }


def runtime_update_status_payload(env: dict[str, str] | None = None) -> dict[str, Any]:
    resolved_env = dict(os.environ if env is None else env)
    installed_version = _plugin_version(resolved_env)
    latest_version = _core_marketplace_latest_version(resolved_env)
    return {
        "status": "ok",
        "service": "aiws",
        "plugin_id": "core-aiws",
        "installed_version": installed_version,
        "marketplace_id": "ai-workspace",
        "marketplace_latest_version": latest_version,
        "latest_version_known": latest_version is not None,
        "update_available": (
            latest_version is not None
            and installed_version is not None
            and latest_version != installed_version
        ),
        "self_update_supported": False,
        "can_self_update": False,
        "update_method": "cowork_native_directory",
        "not_an_update_method": "aiws.host.install only packages generated adapter skills; it does not update core-aiws.",
        "required_action": "Update or reinstall core-aiws@ai-workspace in Cowork's native Directory, then start a new Cowork task/session.",
        "next_steps": [
            "Open Cowork native Directory.",
            "Find core-aiws@ai-workspace.",
            "Update or reinstall the native plugin.",
            "Start a new Cowork task/session so the MCP process reloads.",
            "Call aiws.runtime.info and confirm plugin_version.",
        ],
    }


def health_ping_payload(env: dict[str, str] | None = None) -> dict[str, Any]:
    payload = runtime_info_payload(env)
    return {
        "status": "ok",
        "service": "aiws",
        "runtime_kind": payload["runtime_kind"],
        "launch_mode": payload["launch_mode"],
    }


def record_server_started(env: dict[str, str] | None = None) -> bool:
    resolved_env = dict(os.environ if env is None else env)
    status_path = resolved_env.get("AIWS_MCP_STATUS_PATH")
    if not status_path:
        return False
    path = Path(status_path).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "server_started",
            "launch_id": resolved_env.get("AIWS_MCP_LAUNCH_ID"),
            "pid": os.getpid(),
            "timestamp": _utc_now_iso(),
            "launch_mode": resolved_env.get("AIWS_MCP_LAUNCH_MODE", "unknown"),
            "plugin_version": _plugin_version(resolved_env),
            "declared_tools": list(LOCAL_TOOL_NAMES),
        }
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False, encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            temp_name = handle.name
        os.replace(temp_name, path)
    except OSError:
        return False
    return True


def create_server(root: Path | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without optional runtime dependency
        raise RuntimeError("The MCP SDK is required to run the aiws-mcp server.") from exc

    runtime = AiwsRuntime(root=root)
    server = FastMCP("aiws")

    @server.tool(name="aiws.health.ping")
    def health_ping() -> dict[str, Any]:
        return health_ping_payload()

    @server.tool(name="aiws.runtime.info")
    def runtime_info() -> dict[str, Any]:
        return runtime_info_payload()

    @server.tool(name="aiws.runtime.update_status")
    def runtime_update_status() -> dict[str, Any]:
        return runtime_update_status_payload()

    @server.tool(name="aiws.google_drive.start_oauth")
    def start_google_drive_oauth(
        account: str = "default",
        client_id: str | None = None,
        client_secret: str | None = None,
        redirect_uri: str | None = None,
    ) -> dict[str, Any]:
        return runtime.start_google_drive_oauth(
            account=account,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )

    @server.tool(name="aiws.google_drive.configure_oauth_client")
    def configure_google_drive_oauth_client(
        account: str = "default",
        client_id: str = "",
        client_secret: str | None = None,
        redirect_uri: str | None = None,
        token_uri: str | None = None,
        scopes: list[str] | None = None,
    ) -> dict[str, Any]:
        return runtime.configure_google_drive_oauth_client(
            account=account,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            token_uri=token_uri,
            scopes=scopes,
        )

    @server.tool(name="aiws.google_drive.finish_oauth")
    def finish_google_drive_oauth(
        auth_session_id: str,
        redirected_url: str | None = None,
        authorization_code: str | None = None,
    ) -> dict[str, Any]:
        return runtime.finish_google_drive_oauth(
            auth_session_id,
            redirected_url=redirected_url,
            authorization_code=authorization_code,
        )

    @server.tool(name="aiws.marketplaces.list")
    def list_marketplaces(scope_id: str | None = None, backend_kind: str | None = None) -> dict[str, Any]:
        return runtime.list_marketplaces(scope_id=scope_id, backend_kind=backend_kind)

    @server.tool(name="aiws.marketplaces.drive_workflow")
    def drive_marketplace_workflow(
        marketplace_id: str | None = None,
        host_kind: str = "cowork",
        latest_only: bool = False,
        include_history: bool = True,
        include_debug: bool = False,
    ) -> dict[str, Any]:
        return runtime.drive_marketplace_workflow(
            marketplace_id=marketplace_id,
            host_kind=host_kind,
            latest_only=latest_only,
            include_history=include_history,
            include_debug=include_debug,
        )

    @server.tool(name="aiws.marketplaces.register")
    def register_marketplace(
        marketplace_id: str,
        scope_id: str,
        backend_kind: str,
        backend_ref: str,
        replace: bool = False,
    ) -> dict[str, Any]:
        return runtime.register_marketplace(
            marketplace_id=marketplace_id,
            scope_id=scope_id,
            backend_kind=backend_kind,
            backend_ref=backend_ref,
            replace=replace,
        )

    @server.tool(name="aiws.marketplaces.remove")
    def remove_marketplace(marketplace_id: str) -> dict[str, Any]:
        return runtime.remove_marketplace(marketplace_id=marketplace_id)

    @server.tool(name="aiws.marketplaces.delete_artifact")
    def delete_marketplace_artifact(
        marketplace_id: str,
        plugin_id: str,
        version: str,
        package_file_id: str | None = None,
        dry_run: bool = True,
        confirm: bool = False,
    ) -> dict[str, Any]:
        return runtime.delete_marketplace_artifact(
            marketplace_id=marketplace_id,
            plugin_id=plugin_id,
            version=version,
            package_file_id=package_file_id,
            dry_run=dry_run,
            confirm=confirm,
        )

    @server.tool(name="aiws.skills.search")
    def search(query: str | None = None, scopes: list[str] | None = None, marketplace_id: str | None = None, host_kind: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return runtime.search_skills(query=query, scopes=scopes, marketplace_id=marketplace_id, host_kind=host_kind, limit=limit)

    @server.tool(name="aiws.skills.resolve")
    def resolve(skill_id: str, scope: str | None = None, marketplace_id: str | None = None, version: str | None = None, host_kind: str | None = None) -> dict[str, Any]:
        return runtime.resolve_skill(skill_id, scope=scope, marketplace_id=marketplace_id, version=version, host_kind=host_kind)

    @server.tool(name="aiws.skills.materialize")
    def materialize(skill_id: str, host_kind: str | None = None, host_id: str | None = None, scope: str | None = None, marketplace_id: str | None = None, version: str | None = None) -> dict[str, Any]:
        return runtime.materialize_skill(skill_id=skill_id, host_kind=host_kind, host_id=host_id, scope=scope, marketplace_id=marketplace_id, version=version)

    @server.tool(name="aiws.skills.list_local")
    def list_local(scope: str | None = None, host_kind: str | None = None) -> dict[str, Any]:
        return runtime.list_local_skills(scope=scope, host_kind=host_kind)

    @server.tool(name="aiws.skills.get")
    def get(skill_id: str, scope: str | None = None, marketplace_id: str | None = None, version: str | None = None, include_content: bool = False) -> dict[str, Any]:
        return runtime.get_skill(skill_id, scope=scope, marketplace_id=marketplace_id, version=version, include_content=include_content)

    @server.tool(name="aiws.skills.discover_installed_plugins")
    def discover_installed_plugins(plugin_id: str | None = None, search_roots: list[str] | None = None) -> dict[str, Any]:
        return runtime.discover_installed_plugins(plugin_id=plugin_id, search_roots=search_roots)

    @server.tool(name="aiws.skills.inspect_installed_skill")
    def inspect_installed_skill(
        plugin_id: str,
        skill_id: str,
        search_roots: list[str] | None = None,
        source_plugin_root: str | None = None,
    ) -> dict[str, Any]:
        return runtime.inspect_installed_skill(
            plugin_id=plugin_id,
            skill_id=skill_id,
            search_roots=search_roots,
            source_plugin_root=source_plugin_root,
        )

    @server.tool(name="aiws.skills.create_or_open_draft")
    def create_or_open_draft(
        plugin_id: str,
        skill_id: str,
        target_repo: str,
        source_plugin_root: str | None = None,
        origin_repo: str | None = None,
        origin_marketplace: str | None = None,
        origin_ref: str | None = None,
        base_version: str | None = None,
        base_commit: str | None = None,
        search_roots: list[str] | None = None,
        allow_parallel_draft: bool = False,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        return runtime.create_or_open_draft(
            plugin_id=plugin_id,
            skill_id=skill_id,
            target_repo=target_repo,
            source_plugin_root=source_plugin_root,
            origin_repo=origin_repo,
            origin_marketplace=origin_marketplace,
            origin_ref=origin_ref,
            base_version=base_version,
            base_commit=base_commit,
            search_roots=search_roots,
            allow_parallel_draft=allow_parallel_draft,
            marketplace_id=marketplace_id,
        )

    @server.tool(name="aiws.skills.list_draft_files")
    def list_draft_files(draft_id: str) -> dict[str, Any]:
        return runtime.list_draft_files(draft_id)

    @server.tool(name="aiws.skills.read_draft_file")
    def read_draft_file(draft_id: str, relative_path: str) -> dict[str, Any]:
        return runtime.read_draft_file(draft_id, relative_path)

    @server.tool(name="aiws.skills.write_draft_file")
    def write_draft_file(draft_id: str, relative_path: str, content: str) -> dict[str, Any]:
        return runtime.write_draft_file(draft_id, relative_path, content)

    @server.tool(name="aiws.skills.delete_draft_file")
    def delete_draft_file(draft_id: str, relative_path: str) -> dict[str, Any]:
        return runtime.delete_draft_file(draft_id, relative_path)

    @server.tool(name="aiws.skills.refresh_draft")
    def refresh_draft(draft_id: str) -> dict[str, Any]:
        return runtime.refresh_draft(draft_id)

    @server.tool(name="aiws.skills.revert_draft")
    def revert_draft(draft_id: str) -> dict[str, Any]:
        return runtime.revert_draft(draft_id)

    @server.tool(name="aiws.skills.validate_draft")
    def validate_draft(
        draft_id: str,
        expected_plugin_id: str | None = None,
        expected_marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        return runtime.validate_draft(
            draft_id,
            expected_plugin_id=expected_plugin_id,
            expected_marketplace_id=expected_marketplace_id,
        )

    @server.tool(name="aiws.skills.activate_draft")
    def activate_draft(
        draft_id: str,
        host_kind: str,
        package_output_dir: str,
        host_id: str | None = None,
    ) -> dict[str, Any]:
        return runtime.activate_draft(
            draft_id,
            host_kind=host_kind,
            host_id=host_id,
            package_output_dir=package_output_dir,
        )

    @server.tool(name="aiws.skills.deactivate_draft")
    def deactivate_draft(draft_id: str, host_kind: str, host_id: str | None = None) -> dict[str, Any]:
        return runtime.deactivate_draft(draft_id, host_kind=host_kind, host_id=host_id)

    @server.tool(name="aiws.skills.prepare_update_candidate")
    def prepare_update_candidate(draft_id: str) -> dict[str, Any]:
        return runtime.prepare_update_candidate(draft_id)

    @server.tool(name="aiws.skills.review_update_conflict")
    def review_update_conflict(draft_id: str, update_candidate_id: str) -> dict[str, Any]:
        return runtime.review_update_conflict(draft_id, update_candidate_id)

    @server.tool(name="aiws.skills.resolve_update_conflict")
    def resolve_update_conflict(
        review_id: str,
        choice: str,
        clear_pending_upload: bool = False,
        allow_full_plugin_discard: bool = False,
    ) -> dict[str, Any]:
        return runtime.resolve_update_conflict(
            review_id,
            choice=choice,
            clear_pending_upload=clear_pending_upload,
            allow_full_plugin_discard=allow_full_plugin_discard,
        )

    @server.tool(name="aiws.skills.stage_proposal")
    def stage_proposal(
        draft_id: str,
        summary: str,
        rationale: str,
        target_scope: str | None = None,
        target_repo: str | None = None,
        backend_kind: str = "github",
        backend_ref: str | None = None,
        marketplace_id: str | None = None,
    ) -> dict[str, Any]:
        return runtime.stage_proposal(
            draft_id,
            target_scope=target_scope,
            target_repo=target_repo,
            summary=summary,
            rationale=rationale,
            backend_kind=backend_kind,
            backend_ref=backend_ref,
            marketplace_id=marketplace_id,
        )

    @server.tool(name="aiws.skills.submit_for_review")
    def submit_for_review(proposal_id: str, allowed_target_repos: list[str] | None = None) -> dict[str, Any]:
        return runtime.submit_for_review(proposal_id, allowed_target_repos=allowed_target_repos)

    @server.tool(name="aiws.skills.refresh_proposal_state")
    def refresh_proposal_state(proposal_id: str) -> dict[str, Any]:
        return runtime.refresh_proposal_state(proposal_id)

    @server.tool(name="aiws.skills.publish_approved_proposal")
    def publish_approved_proposal(proposal_id: str) -> dict[str, Any]:
        return runtime.publish_approved_proposal(proposal_id)

    @server.tool(name="aiws.skills.stage_change")
    def stage_change(
        skill_id: str,
        target_scope: str,
        summary: str,
        rationale: str,
        host_kind: str | None = None,
        host_id: str | None = None,
        base_version: str | None = None,
        diff: str | None = None,
        bundle_path: str | None = None,
        evidence: str | None = None,
    ) -> dict[str, Any]:
        """Legacy host-local staged write surface; not the Cowork skill proposal path."""
        return runtime.stage_change(
            skill_id=skill_id,
            target_scope=target_scope,
            summary=summary,
            rationale=rationale,
            host_kind=host_kind,
            host_id=host_id,
            base_version=base_version,
            diff=diff,
            bundle_path=bundle_path,
            evidence=evidence,
        )

    @server.tool(name="aiws.skills.list_staged_changes")
    def list_staged_changes(target_scope: str | None = None, skill_id: str | None = None) -> dict[str, Any]:
        return runtime.list_staged_changes(target_scope=target_scope, skill_id=skill_id)

    @server.tool(name="aiws.host.surfaces")
    def host_surfaces(host_kind: str | None = None, host_id: str | None = None) -> dict[str, Any]:
        return runtime.host_surfaces(host_kind=host_kind, host_id=host_id)

    @server.tool(name="aiws.host.install")
    def host_install(host_kind: str, host_id: str | None = None, dry_run: bool = False) -> dict[str, Any]:
        return runtime.install_host(host_kind=host_kind, host_id=host_id, dry_run=dry_run)

    @server.resource("aiws://protocols/sop")
    def sop_resource() -> str:
        return runtime.get_resource("aiws://protocols/sop")

    @server.resource("aiws://skills/aiws-improve")
    def improve_resource() -> str:
        return runtime.get_resource("aiws://skills/aiws-improve")

    @server.prompt(name="aiws.sop")
    def sop_prompt() -> str:
        return runtime.get_resource("aiws://protocols/sop")

    @server.prompt(name="aiws.improve")
    def improve_prompt() -> str:
        return runtime.get_resource("aiws://skills/aiws-improve")

    return server
