# Soma Care Router

> Your data stays local. Actions happen in the cloud.

**Soma Care Router** is a privacy-preserving specialist routing agent built on [Health Passport](https://play.google.com/store/apps/details?id=com.carlkho.healthpassport) — a local-first health record vault. When a patient's labs flag something abnormal, the Care Router strips all PII, sends an anonymized clinical intent to a Google Cloud Agent (Gemini 3), and uses MongoDB Atlas via MCP to find matching specialists, check drug interactions, and return actionable next steps — all without patient identity ever touching the cloud.

## Architecture — The Privacy Bridge

<img width="2536" height="1751" alt="image" src="https://github.com/user-attachments/assets/aaae500e-d46d-4999-8f31-cfae3d51f624" />


## Demo

🎬 [Watch the 3-minute demo](TODO) | 🌐 [Live hosted project](https://care-router.somach.life)

## Track

**MongoDB** — Google Cloud Rapid Agent Hackathon

## Tech Stack

| Layer | Technology |
|---|---|
| Agentic AI | Gemini 3 via Google Cloud Agent Builder (ADK) |
| Tool Integration | MongoDB MCP Server |
| Database | MongoDB Atlas (Vector Search + Atlas Search) |
| Local Vault | Health Passport (Gemma 4 E2B + PaddleOCR) |
| Backend | Python (google-adk + FastAPI) |
| Frontend | Vanilla JS + HTML |
| Deployment | Google Cloud Run |

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

## License

MIT — see [LICENSE](LICENSE)

## Author

**Carl Kho** — [Somach Inc.](https://somach.life) — [@CarlKho-Minerva](https://github.com/CarlKho-Minerva)
