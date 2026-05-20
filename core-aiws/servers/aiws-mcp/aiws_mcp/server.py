from __future__ import annotations

from pathlib import Path
from typing import Any

from .runtime import AiwsRuntime


def create_server(root: Path | None = None):
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without optional runtime dependency
        raise RuntimeError("The MCP SDK is required to run the aiws-mcp server.") from exc

    runtime = AiwsRuntime(root=root)
    server = FastMCP("aiws")

    @server.tool(name="aiws.skills.search")
    def search(query: str | None = None, scopes: list[str] | None = None, host_kind: str | None = None, limit: int | None = None) -> dict[str, Any]:
        return runtime.search_skills(query=query, scopes=scopes, host_kind=host_kind, limit=limit)

    @server.tool(name="aiws.skills.resolve")
    def resolve(skill_id: str, scope: str | None = None, version: str | None = None, host_kind: str | None = None) -> dict[str, Any]:
        return runtime.resolve_skill(skill_id, scope=scope, version=version, host_kind=host_kind)

    @server.tool(name="aiws.skills.materialize")
    def materialize(skill_id: str, host_kind: str | None = None, host_id: str | None = None, scope: str | None = None, version: str | None = None) -> dict[str, Any]:
        return runtime.materialize_skill(skill_id=skill_id, host_kind=host_kind, host_id=host_id, scope=scope, version=version)

    @server.tool(name="aiws.skills.list_local")
    def list_local(scope: str | None = None, host_kind: str | None = None) -> dict[str, Any]:
        return runtime.list_local_skills(scope=scope, host_kind=host_kind)

    @server.tool(name="aiws.skills.get")
    def get(skill_id: str, scope: str | None = None, version: str | None = None, include_content: bool = False) -> dict[str, Any]:
        return runtime.get_skill(skill_id, scope=scope, version=version, include_content=include_content)

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
    def validate_draft(draft_id: str) -> dict[str, Any]:
        return runtime.validate_draft(draft_id)

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
        target_scope: str,
        target_repo: str | None = None,
        summary: str,
        rationale: str,
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
