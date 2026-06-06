"""Soma Care Router agent package.

Exposes `root_agent` so ADK tooling (`adk web`, `adk eval`, AgentEvaluator)
can discover the agent by importing this package.
"""

from .care_router import root_agent, care_router_agent  # noqa: F401
