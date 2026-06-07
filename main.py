"""Somach - Care Router — FastAPI server.

The care-routing endpoint runs through the ADK agent (`agent/runner.py`) so the
demo, production, and `adk eval` all exercise the identical agent. Gemini is
used directly only for the one-shot PII anonymizer.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from google import genai

from agent.prompts import ANONYMIZER_PROMPT
from agent.runner import run_query


# --- Gemini client setup (anonymizer only) ---

def _get_gemini_client():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if api_key:
        return genai.Client(api_key=api_key)
    # Fall back to Vertex AI / ADC
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    return genai.Client(vertexai=True, project=project, location=location)


client = _get_gemini_client()
MODEL = os.environ.get("CARE_ROUTER_MODEL", "gemini-2.5-flash")


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


# --- FastAPI app ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🩺 Somach - Care Router starting...")
    print(f"   Model: {MODEL}")
    print(f"   Vault: {VAULT_DIR}")
    yield
    print("Shutting down.")


app = FastAPI(title="Somach - Care Router", lifespan=lifespan)
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
    """Main care routing endpoint — runs the ADK agent."""
    body = await request.json()
    query = body.get("query", "")
    anonymized_context = body.get("context", "")

    # The system prompt lives in the agent's instruction; the message carries
    # only the anonymized clinical context and the patient's request.
    vault = load_vault()
    vault_text = "\n\n".join(f"## {k}\n{v}" for k, v in vault.items())
    user_message = (
        f"## Anonymized patient context\n{anonymized_context}\n\n"
        f"## Health vault reference\n{vault_text}\n\n"
        f"## Patient request\n{query}"
    )

    result = await run_query(user_message)
    return JSONResponse(result)


if __name__ == "__main__":
    import uvicorn
    import os

    # Get the port from the environment, defaulting to 8080 for Cloud Run
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
