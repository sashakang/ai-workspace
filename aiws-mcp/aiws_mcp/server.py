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
