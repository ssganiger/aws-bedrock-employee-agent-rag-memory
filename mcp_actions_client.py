import asyncio
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def _create_next_task() -> dict:
    profile = os.environ.get("AWS_PROFILE")
    if not profile:
        raise RuntimeError("Set AWS_PROFILE before calling the MCP task tool.")

    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve().with_name("mcp_server.py"))],
        env=os.environ.copy(),
    )

    async with Client(server) as client:
        result = await client.call_tool("create_next_project_atlas_task", {})

    if result.is_error:
        raise RuntimeError(f"MCP task tool failed: {result.content}")

    payload = result.structured_content
    if not isinstance(payload, dict) or "task" not in payload:
        raise RuntimeError("MCP task tool returned no structured task.")

    return payload


def create_next_task_via_mcp() -> dict:
    return asyncio.run(_create_next_task())
