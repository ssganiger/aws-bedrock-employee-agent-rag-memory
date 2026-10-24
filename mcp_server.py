from typing import TypedDict
from mcp.server import MCPServer

from action_workflow import (
    create_next_open_action_task,
    list_open_actions,
)


class TaskToolResult(TypedDict):
    created: bool
    task: dict[str, str]


mcp = MCPServer("Project Atlas Employee Assistant")


@mcp.tool()
def list_project_atlas_actions() -> list[dict]:
    """List open Project Atlas actions from the latest dated status update."""
    return list_open_actions()


@mcp.tool()
def create_next_project_atlas_task() -> TaskToolResult:
    """Create or return the internal task for the earliest due open action."""
    task, created = create_next_open_action_task()
    return {"created": created, "task": task}


if __name__ == "__main__":
    mcp.run()
