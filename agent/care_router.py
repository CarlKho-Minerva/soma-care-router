"""Soma Care Router — ADK Agent definition.

This is the single source of truth for the agent. Both the live server
(`main.py` via `runner.py`) and the evaluation harness (`adk eval` /
`AgentEvaluator`) load this same `root_agent`, so we evaluate exactly what we
ship. Model is env-driven to keep the prototype and production in sync
(set CARE_ROUTER_MODEL=gemini-3.0-flash where available).
"""

import os

from google.adk.agents import Agent
from google.adk.models import Gemini

from .prompts import CARE_ROUTER_SYSTEM_PROMPT, CARE_ROUTER_MCP_PROMPT
from .tools import (
    search_providers_tool,
    check_drug_interactions_tool,
    get_provider_details_tool,
)

MODEL_NAME = os.environ.get("CARE_ROUTER_MODEL", "gemini-2.5-flash")

# Tool path is selectable. Default: the hardened FunctionTools (deterministic,
# what the eval scoreboard measures). USE_MONGODB_MCP=1: native MongoDB access
# through the MCP server (what the live demo shows). See agent/mcp_tools.py.
_USE_MCP = os.environ.get("USE_MONGODB_MCP", "").strip().lower() in ("1", "true", "yes")

if _USE_MCP:
    from .mcp_tools import build_mongodb_mcp_toolset

    _tools = [build_mongodb_mcp_toolset()]
    _instruction = CARE_ROUTER_MCP_PROMPT
else:
    _tools = [search_providers_tool, check_drug_interactions_tool, get_provider_details_tool]
    _instruction = CARE_ROUTER_SYSTEM_PROMPT

root_agent = Agent(
    model=Gemini(model=MODEL_NAME),
    name="soma_care_router",
    description="Routes patients to appropriate specialists based on anonymized clinical data using a MongoDB provider database.",
    instruction=_instruction,
    tools=_tools,
)

# Backwards-compatible alias.
care_router_agent = root_agent
