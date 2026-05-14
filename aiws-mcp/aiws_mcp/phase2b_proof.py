from __future__ import annotations

import argparse
from typing import Any


PROOF_TOOL_NAMES = ("aiws.health.ping", "aiws.runtime.info")


def safety_flags() -> dict[str, bool]:
    return {
        "memory_tools_exposed": False,
        "managed_plugin_mutation": False,
        "skill_lifecycle_tools_exposed": False,
    }


def health_ping_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "aiws-phase2b-proof",
        "phase": "2B",
        **safety_flags(),
    }


def runtime_info_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "aiws-phase2b-proof",
        "phase": "2B",
        "purpose": "hosted FastMCP connector proof",
        "transport": "streamable-http",
        "declared_tools": list(PROOF_TOOL_NAMES),
        "production_runtime": False,
        **safety_flags(),
    }


def create_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - exercised only without optional runtime dependency
        raise RuntimeError("The MCP SDK is required to run the AIWS Phase 2B proof server.") from exc

    server = FastMCP("aiws-phase2b-proof", stateless_http=True, json_response=True)

    @server.tool(name="aiws.health.ping")
    def health_ping() -> dict[str, Any]:
        return health_ping_payload()

    @server.tool(name="aiws.runtime.info")
    def runtime_info() -> dict[str, Any]:
        return runtime_info_payload()

    return server


def run_server(*, server: Any | None = None, transport: str = "streamable-http") -> None:
    if server is None:
        server = create_server()
    server.run(transport=transport)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m aiws_mcp.phase2b_proof")
    parser.add_argument(
        "--transport",
        default="streamable-http",
        choices=("streamable-http", "stdio", "sse"),
        help="MCP transport to use. Defaults to streamable-http for hosted connector testing.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_server(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
