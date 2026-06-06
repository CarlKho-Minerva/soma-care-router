# Somach - Care Router

> Your data stays local. Actions happen in the cloud.

**Somach - Care Router** is a privacy-preserving specialist routing agent built on [Health Passport](https://play.google.com/store/apps/details?id=com.carlkho.healthpassport) — a local-first health record vault. When a patient's labs flag something abnormal, the Care Router strips all PII, sends an anonymized clinical intent to a Google Cloud Agent (Gemini 3), and uses MongoDB Atlas via MCP to find matching specialists, check drug interactions, and return actionable next steps — all without patient identity ever touching the cloud.

## Architecture — The Privacy Bridge

<img width="2536" height="1751" alt="image" src="https://github.com/user-attachments/assets/aaae500e-d46d-4999-8f31-cfae3d51f624" />


## Demo

🎬 [Watch the 3-minute demo](TODO) | 🌐 [Live hosted project](https://care-router.somach.life)

## Tracks

- Built for: **MongoDB × Google Cloud Rapid Agent Hackathon**
- Hardened for: **Google for Startups AI Agents Challenge — Track 2 (Optimize)**. The reliability layer (`eval/`, the unified ADK Runner, the hardened tools and prompts) is the contribution unique to that submission.

## Tech Stack

| Layer | Technology |
|---|---|
| Agentic AI | Gemini via ADK (`Agent` + `Runner`); model set by `CARE_ROUTER_MODEL` |
| Tool Integration | Two selectable paths: hardened ADK `FunctionTool`s (default, deterministic) and the native read-only **MongoDB MCP server** via ADK `MCPToolset` (`USE_MONGODB_MCP=1`) |
| Database | MongoDB Atlas (Vector Search + Atlas Search) |
| Local Vault | Health Passport (Gemma 4 E2B + PaddleOCR) |
| Backend | Python (google-adk + FastAPI) |
| Frontend | Vanilla JS + HTML |
| Deployment | Google Cloud Run |
| Evaluation | ADK `adk eval` + a custom reliability scoreboard (`eval/`) |

## Quickstart

### Prerequisites

- Python 3.11+
- MongoDB Atlas account (free M0 cluster)
- Google Cloud project with Vertex AI enabled
- Node.js 18+ (for MongoDB MCP server)

### Setup

```bash
# Clone
git clone https://github.com/CarlKho-Minerva/soma-care-router.git
cd soma-care-router

# Python env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Fill in MONGODB_URI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION

# Seed the database
python data/seed_db.py

# Run the agent + web server
python main.py
```

Open `http://localhost:8000` to use the Care Router.

### Environment Variables

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB Atlas connection string |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | GCP region (e.g., `us-central1`) |
| `GOOGLE_API_KEY` | Gemini API key (alternative to Vertex AI) |
| `CARE_ROUTER_MODEL` | Gemini model id (default `gemini-2.5-flash`) |
| `USE_MONGODB_MCP` | `1` to route tools through the native MongoDB MCP server (needs Node.js / npx) |

Local dev only:

| Variable | Description |
|---|---|
| `PORT` | Local server port (Cloud Run injects this automatically) |
| `HOST` | Local bind host |

## Cloud Run Deploy (Known-Good)

Use a deploy env file that includes only app secrets/config, and excludes reserved runtime vars (`PORT`, `K_SERVICE`, etc.).

```bash
# 1) Create deploy env file (do NOT include PORT/HOST)
cat > .env.run <<'EOF'
MONGODB_URI=...
MONGODB_DB=soma_care_router
GOOGLE_API_KEY=...
GOOGLE_CLOUD_PROJECT=somach-care-router
GOOGLE_CLOUD_LOCATION=us-central1
CARE_ROUTER_MODEL=gemini-2.5-flash
EOF

# 2) Deploy
gcloud config set project somach-care-router
gcloud run deploy somach-care-router \
	--source . \
	--env-vars-file .env.run \
	--region us-central1 \
	--allow-unauthenticated
```

If deploy output says `Setting IAM policy failed`, run:

```bash
gcloud run services add-iam-policy-binding somach-care-router \
	--region us-central1 \
	--member=allUsers \
	--role=roles/run.invoker
```

Then verify:

```bash
SERVICE_URL="$(gcloud run services describe somach-care-router --region us-central1 --format='value(status.url)')"
echo "$SERVICE_URL"
curl -i "$SERVICE_URL/health"
```

If you still see `Error: Forbidden` at `/`, check IAM binding exists:

```bash
gcloud run services get-iam-policy somach-care-router \
	--region us-central1 \
	--format='json(bindings)'
```

Look for `roles/run.invoker` containing `allUsers`.

If adding `allUsers` fails with `FAILED_PRECONDITION` and `do not belong to a permitted customer`, your org policy is blocking public principals. In that case:

```bash
# Authenticated invoke works for permitted identities
SERVICE_URL="$(gcloud run services describe somach-care-router --region us-central1 --format='value(status.url)')"
curl -i -H "Authorization: Bearer $(gcloud auth print-identity-token)" "$SERVICE_URL/health"
```

For truly public access, you must either:

1. Ask your org admin to allow `allUsers`/`allAuthenticatedUsers` for this project/service.
2. Deploy in a project without that domain-restricted sharing policy.

## How It Works

1. **Patient triggers routing** — a lab result is flagged abnormal (e.g., A1C at 7.2%)
2. **PII stripping** — Health Passport removes name, DOB, insurance ID; keeps only clinical data
3. **Anonymized intent** — sent to Gemini agent: "elevated A1C, on SSRI + stimulant, SF location"
4. **Agent reasoning** — Gemini reasons through the clinical context, decides which tools to call
5. **MongoDB MCP** — agent queries providers collection via vector search for specialty match
6. **Drug conflict check** — agent cross-references provider prescribing patterns with patient meds
7. **Results returned** — top 3 providers with availability, distance, ratings, and a draft referral

## Project Structure

```
soma-care-router/
├── main.py                  # FastAPI server + agent orchestration
├── agent/
│   ├── care_router.py       # ADK agent definition
│   ├── tools.py             # MongoDB MCP tool definitions
│   └── prompts.py           # System prompts
├── data/
│   ├── seed_db.py           # MongoDB seeder
│   ├── providers.json       # Provider database (10K records)
│   └── health_vault/        # Sample local health vault
├── web/
│   ├── index.html           # Main web UI
│   └── styles.css           # Styles
├── deck/
│   └── index.html           # Presentation deck
├── DEMO_SCRIPT.md           # Demo recording script
└── requirements.txt
```

## Reliability & Evaluation

Serving, the demo, and evaluation all run the same ADK `root_agent` (`agent/runner.py`), so we test exactly what we ship. The agent's instruction forces every provider name and appointment slot to come from a tool result, tools return a structured `ok`/`degraded` envelope instead of silently degrading, and a stalled run recovers without fabricating an answer.

```bash
# deterministic, no credentials (CI gate):
pytest eval/test_tools_reliability.py -q

# live reliability scoreboard (needs Gemini key + seeded MongoDB):
python eval/run_eval.py --label baseline --out eval/baseline.json   # pre-hardening commit
python eval/run_eval.py --label final    --out eval/final.json      # HEAD

# Google's trajectory/response eval:
adk eval agent eval/health_routing.evalset.json --config_file_path eval/test_config.json
```

Before and after numbers and the full failure taxonomy live in [eval/RESULTS.md](eval/RESULTS.md).

## License

MIT — see [LICENSE](LICENSE)

## Author

**Carl Kho** — [Somach Inc.](https://somach.life) — [@CarlKho-Minerva](https://github.com/CarlKho-Minerva)
