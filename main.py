"""Soma Care Router — FastAPI server with ADK agent."""

import json
import os
import traceback

from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from google import genai

from agent.prompts import CARE_ROUTER_SYSTEM_PROMPT, ANONYMIZER_PROMPT
from agent.tools import search_providers, check_drug_interactions, get_provider_details


# --- Gemini client setup ---

def _get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    # Fall back to Vertex AI / ADC
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    return genai.Client(vertexai=True, project=project, location=location)


client = _get_gemini_client()
MODEL = "gemini-2.5-flash"  # Use latest available; swap to gemini-3.0-flash when GA


# --- Health vault loader ---

VAULT_DIR = os.path.join(os.path.dirname(__file__), "data", "health_vault")


def load_vault() -> dict[str, str]:
    vault = {}
    if not os.path.isdir(VAULT_DIR):
        return vault
    for fname in os.listdir(VAULT_DIR):
        if fname.endswith(".md"):
            with open(os.path.join(VAULT_DIR, fname)) as f:
                vault[fname] = f.read()
    return vault


# --- Tool dispatch for function-calling ---

TOOL_FUNCTIONS = {
    "search_providers": search_providers,
    "check_drug_interactions": check_drug_interactions,
    "get_provider_details": get_provider_details,
}

TOOL_DECLARATIONS = [
    {
        "name": "search_providers",
        "description": "Search the provider database for specialists matching clinical criteria.",
        "parameters": {
            "type": "object",
            "properties": {
                "specialty": {"type": "string", "description": "Medical specialty needed"},
                "location_city": {"type": "string", "description": "City for proximity search"},
                "conditions": {"type": "string", "description": "Comma-separated relevant conditions"},
                "current_medications": {"type": "string", "description": "Comma-separated current medications"},
                "max_results": {"type": "integer", "description": "Max providers to return"},
            },
            "required": ["specialty", "location_city"],
        },
    },
    {
        "name": "check_drug_interactions",
        "description": "Check for known drug interactions between current and proposed medications.",
        "parameters": {
            "type": "object",
            "properties": {
                "current_medications": {"type": "string", "description": "Comma-separated current medications"},
                "proposed_medication": {"type": "string", "description": "Medication being considered"},
            },
            "required": ["current_medications", "proposed_medication"],
        },
    },
    {
        "name": "get_provider_details",
        "description": "Get full details for a specific provider.",
        "parameters": {
            "type": "object",
            "properties": {
                "provider_name": {"type": "string", "description": "Name of the provider"},
            },
            "required": ["provider_name"],
        },
    },
]


# --- FastAPI app ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🩺 Soma Care Router starting...")
    print(f"   Model: {MODEL}")
    print(f"   Vault: {VAULT_DIR}")
    yield
    print("Shutting down.")


app = FastAPI(title="Soma Care Router", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="web"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("web/index.html") as f:
        return f.read()


@app.get("/deck", response_class=HTMLResponse)
async def deck():
    with open("deck/index.html") as f:
        return f.read()


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL}


@app.get("/api/vault")
async def get_vault():
    """Return the local health vault contents (for UI display)."""
    vault = load_vault()
    return JSONResponse(vault)


@app.post("/api/anonymize")
async def anonymize(request: Request):
    """Strip PII from raw health context using Gemini."""
    body = await request.json()
    raw_context = body.get("context", "")

    response = client.models.generate_content(
        model=MODEL,
        contents=[
            {"role": "user", "parts": [{"text": f"{ANONYMIZER_PROMPT}\n\n---\n\nPatient context:\n{raw_context}"}]},
        ],
    )
    return JSONResponse({"anonymized": response.text})


@app.post("/api/route")
async def route_care(request: Request):
    """Main care routing endpoint — runs the agent loop."""
    body = await request.json()
    query = body.get("query", "")
    anonymized_context = body.get("context", "")

    # Build the full prompt with vault context
    vault = load_vault()
    vault_text = "\n\n".join(f"## {k}\n{v}" for k, v in vault.items())

    messages = [
        {
            "role": "user",
            "parts": [{"text": (
                f"{CARE_ROUTER_SYSTEM_PROMPT}\n\n"
                f"## Anonymized Patient Context\n{anonymized_context}\n\n"
                f"## Health Vault Reference\n{vault_text}\n\n"
                f"## Patient Request\n{query}"
            )}],
        }
    ]

    # Agent loop with function calling
    trace = []
    max_turns = 5

    for turn in range(max_turns):
        response = client.models.generate_content(
            model=MODEL,
            contents=messages,
            config={
                "tools": [{"function_declarations": TOOL_DECLARATIONS}],
            },
        )

        candidate = response.candidates[0]
        parts = candidate.content.parts

        # Check for function calls
        fn_calls = [p for p in parts if hasattr(p, "function_call") and p.function_call]
        if not fn_calls:
            # Final text response
            final_text = "".join(p.text for p in parts if hasattr(p, "text") and p.text)
            trace.append({"type": "response", "content": final_text})
            return JSONResponse({"response": final_text, "trace": trace})

        # Execute function calls
        messages.append({"role": "model", "parts": parts})
        fn_response_parts = []

        for part in fn_calls:
            fc = part.function_call
            fn_name = fc.name
            fn_args = dict(fc.args) if fc.args else {}

            trace.append({"type": "tool_call", "tool": fn_name, "args": fn_args})

            # Execute the tool
            tool_fn = TOOL_FUNCTIONS.get(fn_name)
            if tool_fn:
                try:
                    result = tool_fn(**fn_args)
                except Exception as e:
                    result = json.dumps({"error": str(e)})
            else:
                result = json.dumps({"error": f"Unknown tool: {fn_name}"})

            trace.append({"type": "tool_result", "tool": fn_name, "result": result})

            fn_response_parts.append({
                "function_response": {
                    "name": fn_name,
                    "response": {"result": result},
                }
            })

        messages.append({"role": "user", "parts": fn_response_parts})

    return JSONResponse({"response": "Agent reached maximum turns.", "trace": trace})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
