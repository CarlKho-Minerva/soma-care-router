"""Native MongoDB access through the Model Context Protocol.

Wires the official MongoDB MCP server (`mongodb-mcp-server`, run over stdio via
npx) into the agent through ADK's `MCPToolset`. Selected at runtime by
`USE_MONGODB_MCP=1`. Launched with `--readOnly` so the agent can only read the
provider and drug-interaction collections, never mutate them.

Design note (Track 2): the MCP server exposes generic database tools
(find/aggregate/count), so in MCP mode the agent composes its own queries. That
is genuinely more agentic and is what the challenge rewards, but it trades away
the domain guardrails baked into the hardened FunctionTools in `tools.py`
(escaped regex, the structured ok/degraded envelope, grounding-by-construction).
For that reason the reliability scoreboard (`eval/`) runs on the deterministic
FunctionTool path, while this MCP path is the one demonstrated live. Both reach
the same MongoDB Atlas data.

Requires Node.js / npx on the host (Cloud Run image must include Node) and a
`MONGODB_URI`.
"""

import os

from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def build_mongodb_mcp_toolset() -> MCPToolset:
    """Return an ADK MCPToolset backed by the read-only MongoDB MCP server."""
    uri = os.environ.get("MONGODB_URI", "").strip()
    if not uri:
        raise RuntimeError(
            "MONGODB_URI is required to launch the MongoDB MCP server."
        )
    return MCPToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "mongodb-mcp-server@latest", "--readOnly"],
                # Pass the connection string via env (not argv) so it never
                # lands in a process list. Inherit PATH etc. so npx resolves.
                env={**os.environ, "MDB_MCP_CONNECTION_STRING": uri},
            ),
            # First run may download the npm package; allow headroom.
            timeout=120,
        ),
    )
