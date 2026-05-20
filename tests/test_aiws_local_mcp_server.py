from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
AIWS_MCP_PYTHONPATH = str(REPO_ROOT / "aiws-mcp")
if AIWS_MCP_PYTHONPATH not in sys.path:
    sys.path.insert(0, AIWS_MCP_PYTHONPATH)

from aiws_mcp import server as aiws_server  # noqa: E402


class FakeFastMCP:
    instances: list["FakeFastMCP"] = []

    def __init__(self, name: str, **kwargs: Any) -> None:
        self.name = name
        self.kwargs = kwargs
        self.tools: dict[str, Callable[..., Any]] = {}
        self.run_calls: list[dict[str, Any]] = []
        self.instances.append(self)

    def tool(self, *, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.tools[name] = func
            return func

        return decorator

    def resource(self, _uri: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator

    def prompt(self, *, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            return func

        return decorator

    def run(self, **kwargs: Any) -> None:
        self.run_calls.append(kwargs)


class FakeMcpSdk:
    def __enter__(self) -> type[FakeFastMCP]:
        FakeFastMCP.instances = []
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


class AiwsLocalMcpServerTests(unittest.TestCase):
    def test_create_server_registers_declared_local_toolset(self) -> None:
        with FakeMcpSdk():
            server = aiws_server.create_server()

        self.assertEqual(server.name, "aiws")
        self.assertEqual(tuple(server.tools), aiws_server.LOCAL_TOOL_NAMES)

    def test_runtime_info_identifies_local_bundled_stdio_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            plugin_root = Path(temp) / "core-aiws"
            manifest_dir = plugin_root / ".claude-plugin"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "plugin.json").write_text(
                json.dumps({"name": "core-aiws", "version": "9.9.9"}, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            env = {
                "CLAUDE_PLUGIN_ROOT": str(plugin_root),
                "CLAUDE_PLUGIN_DATA": str(Path(temp) / "plugin-data"),
                "AIWS_MCP_LAUNCH_MODE": "uvx-bundled-source",
                "AIWS_MCP_STATUS_PATH": str(Path(temp) / "plugin-data" / "runtime" / "aiws-mcp-status.json"),
                "AIWS_MCP_LOG_PATH": str(Path(temp) / "plugin-data" / "logs" / "aiws-mcp-launcher.log"),
            }
            with FakeMcpSdk(), mock.patch.dict(os.environ, env, clear=False):
                server = aiws_server.create_server()
                payload = server.tools["aiws.runtime.info"]()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "aiws")
        self.assertEqual(payload["runtime_kind"], aiws_server.LOCAL_RUNTIME_KIND)
        self.assertEqual(payload["transport"], aiws_server.LOCAL_RUNTIME_TRANSPORT)
        self.assertEqual(payload["launch_mode"], "uvx-bundled-source")
        self.assertEqual(payload["plugin_version"], "9.9.9")
        self.assertEqual(tuple(payload["declared_tools"]), aiws_server.LOCAL_TOOL_NAMES)
        self.assertTrue(payload["proposal_tools_declared"])
        self.assertTrue(payload["diagnostics_enabled"])
        self.assertTrue(payload["plugin_root_present"])
        self.assertTrue(payload["plugin_data_present"])

    def test_record_server_started_writes_status_when_configured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            status_path = Path(temp) / "runtime" / "aiws-mcp-status.json"
            env = {
                "AIWS_MCP_STATUS_PATH": str(status_path),
                "AIWS_MCP_LAUNCH_ID": "launch-123",
                "AIWS_MCP_LAUNCH_MODE": "uvx-bundled-source",
                "AIWS_MCP_PLUGIN_VERSION": "1.2.3",
            }

            wrote = aiws_server.record_server_started(env)
            payload = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertTrue(wrote)
        self.assertEqual(payload["status"], "server_started")
        self.assertEqual(payload["launch_id"], "launch-123")
        self.assertEqual(payload["launch_mode"], "uvx-bundled-source")
        self.assertEqual(payload["plugin_version"], "1.2.3")
        self.assertEqual(tuple(payload["declared_tools"]), aiws_server.LOCAL_TOOL_NAMES)
        self.assertIsInstance(payload["pid"], int)
        self.assertIsInstance(payload["timestamp"], str)


if __name__ == "__main__":
    unittest.main()
