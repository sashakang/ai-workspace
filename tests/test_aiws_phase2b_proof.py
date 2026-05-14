from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp import phase2b_proof  # noqa: E402


FORBIDDEN_TOOL_PARTS = (
    "memory",
    "skills",
    "draft",
    "proposal",
    "stage",
    "submit",
    "review",
    "github",
    "git",
)


class FakeFastMCP:
    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, Callable[..., Any]] = {}
        self.run_calls: list[dict[str, Any]] = []

    def tool(self, *, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = func
            return func

        return decorator

    def run(self, **kwargs: Any) -> None:
        self.run_calls.append(kwargs)


class FakeMcpSdk:
    def __enter__(self) -> type[FakeFastMCP]:
        self.previous = {
            name: sys.modules.get(name)
            for name in ("mcp", "mcp.server", "mcp.server.fastmcp")
        }

        mcp_module = types.ModuleType("mcp")
        server_module = types.ModuleType("mcp.server")
        fastmcp_module = types.ModuleType("mcp.server.fastmcp")
        fastmcp_module.FastMCP = FakeFastMCP
        server_module.fastmcp = fastmcp_module
        mcp_module.server = server_module

        sys.modules["mcp"] = mcp_module
        sys.modules["mcp.server"] = server_module
        sys.modules["mcp.server.fastmcp"] = fastmcp_module
        return FakeFastMCP

    def __exit__(self, *exc_info: object) -> None:
        for name, previous_module in self.previous.items():
            if previous_module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous_module


class AiwsPhase2BProofTests(unittest.TestCase):
    def test_declares_only_harmless_phase2b_proof_tools(self) -> None:
        self.assertEqual(
            phase2b_proof.PROOF_TOOL_NAMES,
            ("aiws.health.ping", "aiws.runtime.info"),
        )
        self.assert_no_forbidden_tool_parts(phase2b_proof.PROOF_TOOL_NAMES)

    def test_create_server_registers_only_phase2b_proof_tools_without_live_sdk(self) -> None:
        with FakeMcpSdk():
            server = phase2b_proof.create_server()

        self.assertEqual(server.name, "aiws-phase2b-proof")
        self.assertTrue(server.kwargs["stateless_http"])
        self.assertTrue(server.kwargs["json_response"])
        self.assertEqual(tuple(server.tools), phase2b_proof.PROOF_TOOL_NAMES)
        self.assert_no_forbidden_tool_parts(server.tools)

    def test_payloads_include_explicit_safety_flags(self) -> None:
        payloads = [
            phase2b_proof.health_ping_payload(),
            phase2b_proof.runtime_info_payload(),
        ]

        for payload in payloads:
            self.assertIs(payload["memory_tools_exposed"], False)
            self.assertIs(payload["managed_plugin_mutation"], False)
            self.assertIs(payload["skill_lifecycle_tools_exposed"], False)

        self.assertEqual(
            tuple(payloads[1]["declared_tools"]),
            phase2b_proof.PROOF_TOOL_NAMES,
        )
        self.assert_no_forbidden_tool_parts(payloads[1]["declared_tools"])

    def test_run_uses_streamable_http_transport_by_default(self) -> None:
        with FakeMcpSdk():
            server = phase2b_proof.create_server()
            phase2b_proof.run_server(server=server)

        self.assertEqual(server.run_calls, [{"transport": "streamable-http"}])

    def test_phase2b_docs_capture_run_and_cowork_test_instructions(self) -> None:
        phase_plan = (REPO_ROOT / "docs" / "aiws-cowork-phase2b-runtime-plan.md").read_text(encoding="utf-8")

        self.assertIn("python -m aiws_mcp.phase2b_proof --transport streamable-http", phase_plan)
        self.assertIn("http://localhost:8000/mcp", phase_plan)
        self.assertIn("aiws.health.ping", phase_plan)
        self.assertIn("aiws.runtime.info", phase_plan)
        self.assertIn("memory_tools_exposed: false", phase_plan)
        self.assertIn("managed_plugin_mutation: false", phase_plan)
        self.assertIn("Cowork connector test:", phase_plan)

    def assert_no_forbidden_tool_parts(self, tool_names: object) -> None:
        for tool_name in tool_names:
            lowered = str(tool_name).lower()
            for forbidden in FORBIDDEN_TOOL_PARTS:
                self.assertNotIn(forbidden, lowered, tool_name)


if __name__ == "__main__":
    unittest.main()
