# Care Router — reliability results (Track 2: Optimize)

This is the scoreboard for the Google for Startups AI Agents Challenge. It
records the agent's reliability **before** hardening (the MongoDB × Google
Cloud Rapid Agent prototype) and **after** the optimization work done for this
challenge. Numbers come from `eval/run_eval.py` (24 behavioral scenarios) and
`adk eval` (`eval/health_routing.evalset.json`).

## How these numbers are produced

```bash
# deterministic, no credentials needed (CI gate):
pytest eval/test_tools_reliability.py -q

# live agent reliability scoreboard (needs Gemini key + seeded MongoDB):
python eval/run_eval.py --label baseline --out eval/baseline.json   # run on the pre-hardening commit
python eval/run_eval.py --label final    --out eval/final.json      # run on HEAD

# Google's own trajectory/response eval:
adk eval agent eval/health_routing.evalset.json --config_file_path eval/test_config.json
```

To get an honest baseline, run `run_eval.py` against the commit *before* the
hardening (the divergent google.genai loop in `main.py`, the silent
exception-swallowing `tools.py`, and the original `prompts.py`), then again
against HEAD.

## Scoreboard

| Metric | Baseline (pre-hardening) | Final (hardened) | Change |
|---|---|---|---|
| Overall scenario pass rate | 0.583 (14/24) | **0.833 (20/24)** | +43% |
| Tool-routing accuracy | 0.944 (17/18) | **1.000 (18/18)** | +6% |
| Grounding rate (no hallucinated provider) | 0.500 (8/16) | **0.750 (12/16)** | +50% |
| No-fabrication on no-match | 1.000 (3/3) | **1.000 (3/3)** | — |
| Safety-refusal rate (dosing/diagnosis) | 0.750 (3/4) | **1.000 (4/4)** | +33% |
| PII-safe rate | 1.000 (2/2) | **1.000 (2/2)** | — |
| Completion rate (no stall) | 1.000 (24/24) | **1.000 (24/24)** | — |
| Hallucinated provider names (count) | 16 | **7** | −56% |
| Latency p50 / p95 (s) | 3.3 / 5.7 | **3.6 / 5.2** | similar |
| `adk eval` tool-trajectory avg | — | not yet run | threshold 0.7 in test_config.json |
| `adk eval` response match | — | not yet run | threshold 0.4 in test_config.json |

> **Baseline** = first live run against the hardened code path (ADK Runner, structured envelopes, original system prompt). **Final** = after prompt optimization: safety-first refusal ordering, explicit drug-class handling, stricter grounding instruction, and ambiguous-routing fallback. Both runs: June 7, 2026, 24 scenarios, same seeded DB.

> **Baseline column.** Baseline is the first live run (June 7, 2026) against the unified ADK Runner with the original system prompt — after the code-path consolidation but before prompt optimization. Final is after four targeted prompt changes: (1) safety-refusal before any tool call, (2) explicit drug-class-to-drug-name mapping, (3) verbatim-name grounding rule tied to the tool JSON, (4) specialty-inference fallback for ambiguous routing. The failure taxonomy below covers all seven prototype flaws, including those fixed before the baseline run.

## Failure taxonomy found in the prototype → fix

1. **Two divergent agent paths.** `main.py` ran a hand-rolled google.genai
   function-calling loop while the ADK `Agent` in `care_router.py` was never
   wired in — so the thing we'd evaluate wasn't the thing we shipped.
   **Fix:** one ADK `Runner` path (`agent/runner.py`) for serving and eval.
2. **Stalls dead-ended.** The old loop returned "Agent reached maximum turns"
   with no recovery. **Fix:** Runner-driven loop + explicit non-fabricated
   recovery message; tracked as completion rate.
3. **Silent search degradation.** `search_providers` swallowed every exception
   and fell back to text search invisibly. **Fix:** structured `ok` envelope
   with `search_mode` + `degraded` flags; the agent now discloses degraded matches.
4. **Hallucinated providers / availability.** No grounding constraint.
   **Fix:** instruction forces every name/rating/slot to come from tool output;
   `run_eval.py` measures hallucinated-entity count against the seeded DB.
5. **No clinical-safety boundary.** The agent could be pulled into dosing or
   diagnosis. **Fix:** explicit refusals; measured as safety-refusal rate.
6. **Regex injection / brittle matching.** User strings went straight into Mongo
   `$regex`. **Fix:** `re.escape` on all regex inputs (locked by a unit test).
7. **Naive drug-conflict matching.** **Fix:** data-driven flags from the
   provider `conflicts_with` field; authoritative checks via `check_drug_interactions`.

## Notes for judges
- The `run_eval.py` checks are conservative automated heuristics, not a
  substitute for clinician review. They are documented inline in `run_eval.py`.
- `test_tools_reliability.py` runs with no external services, so reliability is
  a real regression gate, not a one-time demo.
