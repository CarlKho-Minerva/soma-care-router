"""ADK trajectory + response evaluation (Google's own eval tooling).

Runs the seeded evalset through the same `root_agent` the server uses, scoring
tool-trajectory and response match against the thresholds in test_config.json.
Requires a live Gemini key (GOOGLE_API_KEY) or a Vertex project, so it is
skipped automatically in credential-free CI; the deterministic gate there is
test_tools_reliability.py.

    pytest eval/test_agent_eval.py -q          # equivalently: adk eval agent eval/health_routing.evalset.json
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.adk.evaluation.agent_evaluator import AgentEvaluator

requires_live = pytest.mark.skipif(
    not (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_CLOUD_PROJECT")),
    reason="needs a live Gemini key (GOOGLE_API_KEY) or a Vertex project",
)


@requires_live
@pytest.mark.asyncio
async def test_health_routing_evalset():
    await AgentEvaluator.evaluate(
        agent_module="agent",
        eval_dataset_file_path_or_dir="eval/health_routing.evalset.json",
    )
