"""ADK Runner wrapper — the one code path for both serving and evaluation.

Before hardening, the live server (`main.py`) hand-rolled a google.genai
function-calling loop that diverged from the ADK `Agent` defined in
`care_router.py`, and dead-ended with "Agent reached maximum turns". This
wrapper routes every request through the ADK `Runner` so the demo, production,
and `adk eval` all exercise the identical agent, and a stalled run recovers
gracefully instead of returning a misleading message.
"""

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from .care_router import root_agent

APP_NAME = "soma_care_router"

_session_service = InMemorySessionService()
_runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=_session_service)


async def run_query(query: str, user_id: str = "anon", session_id: str | None = None) -> dict:
    """Run one routing turn through the ADK agent.

    Returns {"response": str, "trace": list, "stalled": bool}. The trace captures
    tool calls/results for the UI and demo. On a stall (no final response) the
    agent recovers with an explicit, non-fabricated message.
    """
    session = await _session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    content = types.Content(role="user", parts=[types.Part(text=query)])

    trace: list[dict] = []
    final_text = ""
    got_final = False

    async for event in _runner.run_async(
        user_id=user_id, session_id=session.id, new_message=content
    ):
        for call in (event.get_function_calls() or []):
            trace.append({"type": "tool_call", "tool": call.name, "args": dict(call.args or {})})
        for resp in (event.get_function_responses() or []):
            trace.append({"type": "tool_result", "tool": resp.name, "result": resp.response})
        if event.is_final_response() and event.content and event.content.parts:
            final_text = "".join(p.text for p in event.content.parts if getattr(p, "text", None))
            got_final = True

    if not got_final or not final_text.strip():
        final_text = (
            "I couldn't complete this routing request. No recommendation was made. "
            "Please retry, or broaden the city or specialty."
        )
        trace.append({"type": "recovery", "content": final_text})
        return {"response": final_text, "trace": trace, "stalled": True}

    trace.append({"type": "response", "content": final_text})
    return {"response": final_text, "trace": trace, "stalled": False}
