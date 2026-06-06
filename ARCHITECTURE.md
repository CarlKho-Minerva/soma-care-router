# Architecture — Soma Care Router

Two views: the **Privacy Bridge** (how a request flows without PII reaching the cloud) and the **Optimization & Evaluation loop** (the Track 2 reliability work). For the Devpost upload, export either panel to PNG at [mermaid.live](https://mermaid.live), or screenshot `deck/architecture.html`.

## Panel 1 — The Privacy Bridge

Your data stays local. Actions happen in the cloud. Only a de-identified clinical intent ever leaves the device; the returned plan has identity re-attached on-device.

```mermaid
flowchart LR
  subgraph device["On-device · Health Passport"]
    V["Local vault<br/>labs · meds · conditions"]
    S["PII strip"]
    R["Re-attach identity<br/>on-device"]
  end
  subgraph cloud["Google Cloud Run"]
    A["Care Router agent<br/>Gemini + ADK Runner"]
  end
  subgraph data["MongoDB Atlas"]
    P["providers"]
    D["drug_interactions"]
  end
  V --> S
  S -->|"anonymized clinical intent"| A
  A -->|"FunctionTools or MongoDB MCP"| P
  A --> D
  P -->|"results"| A
  D -->|"results"| A
  A -->|"action plan · no PII"| R
  R --> V
```

## Panel 2 — Optimization & Evaluation loop (Track 2)

One agent definition (`root_agent`) is served and evaluated through the same ADK `Runner`, so we test exactly what we ship. Evaluation drives hardening; a credential-free test gate blocks regressions.

```mermaid
flowchart TD
  AG["root_agent<br/>one ADK Runner: serve + eval"]
  subgraph evalsuite["Evaluation"]
    RE["run_eval.py<br/>24 behavioral scenarios"]
    AE["adk eval<br/>health_routing.evalset.json"]
  end
  M["Metrics scoreboard<br/>routing · grounding · safety · PII · completion · latency"]
  H["Harden<br/>prompts.py + tools.py"]
  CI["test_tools_reliability.py<br/>credential-free CI gate"]
  AG --> RE
  AG --> AE
  RE --> M
  AE --> M
  M -->|"failure taxonomy"| H
  H -->|"re-run"| RE
  H -->|"updates"| AG
  M --> CI
  CI -->|"blocks regressions"| AG
```

## Legend
- **FunctionTools path** (default): hardened, deterministic tools in `agent/tools.py`. This is the path the scoreboard measures.
- **MongoDB MCP path** (`USE_MONGODB_MCP=1`): the read-only MongoDB MCP server via ADK `MCPToolset` in `agent/mcp_tools.py`. Same Atlas data, native MCP.
- The before/after numbers and the full failure taxonomy live in [eval/RESULTS.md](eval/RESULTS.md).
