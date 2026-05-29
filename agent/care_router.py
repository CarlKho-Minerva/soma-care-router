"""Soma Care Router — ADK Agent definition."""

from google.adk.agents import Agent
from google.adk.models import Gemini

from .prompts import CARE_ROUTER_SYSTEM_PROMPT
from .tools import (
    search_providers_tool,
    check_drug_interactions_tool,
    get_provider_details_tool,
)

care_router_agent = Agent(
    model=Gemini(model="gemini-3.0-flash"),
    name="soma_care_router",
    description="Routes patients to appropriate specialists based on anonymized clinical data using MongoDB provider database.",
    instruction=CARE_ROUTER_SYSTEM_PROMPT,
    tools=[
        search_providers_tool,
        check_drug_interactions_tool,
        get_provider_details_tool,
    ],
)
