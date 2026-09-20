# Real provider setup and phase 2 hand-off

Updated 2026-09-20. This guide assumes the Python environment is already activated.

## What the Autopilot API key is

`AUTOPILOT_API_KEY` protects this project's own FastAPI endpoints when clients call them. It is not a provider credential and there is nowhere to download it. Generate a random secret yourself and give the same value to authorized API clients as `Authorization: Bearer <secret>`. It may remain empty while the service is bound only to localhost. Never reuse the OpenRouter or TypeSafe key for it.

## Configured provider pool

The catalog snapshot in `config/model-snapshots/openrouter-claude-2026-09-20.json` configures:

| Alias | Model | Bootstrap role |
|---|---|---|
| `economy` | `anthropic/claude-haiku-4.5` | Extraction and classification primary |
| `balanced` | `anthropic/claude-sonnet-5` | Context Q&A primary |
| `strong` | `anthropic/claude-opus-5` | Qualified fallback |

The bootstrap shape has now been measured in phase 2. `config/profiles-claude-pilot.json` contains the provisional success bounds, latency, cost, experiment settings, and data/config/evaluator/result hashes. It remains explicitly blocked from active mode because this synthetic pilot is not an untouched final test.

Jev uses `openrouter_decisions` for the first smoke because the OpenRouter response includes billed cost. The TypeSafe direct key remains available for a later paired transport experiment; direct and gateway model identifiers must not be treated as interchangeable.

## Run local checks

```powershell
pytest -q
python scripts/smoke_providers.py --model-alias economy
```

## Run the three bounded real smokes

The `.env` file points to `config/real-smoke.yaml`. Load it for each subprocess with `python-dotenv`:

```powershell
python -m dotenv run -- python scripts/smoke_providers.py --real --model-alias economy --max-budget-microusd 20000 --output artifacts/smoke/haiku.json
python -m dotenv run -- python scripts/smoke_providers.py --real --model-alias balanced --max-budget-microusd 20000 --output artifacts/smoke/sonnet.json
python -m dotenv run -- python scripts/smoke_providers.py --real --model-alias strong --max-budget-microusd 20000 --output artifacts/smoke/opus.json
```

The per-call limit is $0.02; the provider key's own spending limit is the authoritative hard ceiling. Stop if a report is incomplete, a requested/resolved model differs unexpectedly, or an error/unknown cost appears.

## Inspect and record the smoke

For each report confirm:

- both calls succeeded;
- requested and resolved models are present;
- the provider is present;
- tokens, latency, and billed micro-USD are present;
- `complete_cost` is true;
- the returned extraction is supported by the source.

Then record the observed model/provider IDs, costs, latency, date, transport, and any mismatch in `docs/provider-contracts.md`, `docs/decisions.md`, and `docs/progress.md`. A smoke validates connectivity and response contracts only; it does not qualify a model.

## Phase 2 result

The canary covered 20 cases and 60 generations for $0.104678. The resumed full run covered all 100 cases and 300 case/model pairs for $0.537627, with complete billing and no provider errors. The detailed evidence is in `artifacts/pilot/report.md`.

The decision is `continue_router` in shadow only. Fixed Sonnet was the cheapest acceptable fixed baseline. Haiku for extraction/classification plus Sonnet for Q&A matched its observed 100/100 successes while reducing measured generation cost by 39.2% before overhead. The six Haiku failures were all Q&A abstention-flag errors.

## Enter phase 3

1. Treat `config/profiles-claude-pilot.json` as provisional input and keep `validated_for_active: false`.
2. Freeze three shadow policies: fixed Sonnet, the simple contract rule, and Jev using the same Claude pool.
3. Replay the pilot through common deterministic and semantic verification; do not expose gold labels to routing or verification.
4. Record Jev decision cost/latency separately from generation, verification, fallback, and audit cost.
5. Compare Jev with the contract rule, not only with fixed models. Jev must add measurable value beyond the rule to justify its operational complexity.
6. Calibrate confidence/abstention and fallback thresholds on development data, preserving grouped source/template splits. Do not enable active mode.
7. Produce a shadow report with route agreement, success, false accepts/rejects, escalation rate, full cost, latency, and the overhead sensitivity boundary from phase 2.

Do not set `mode: active`. The next operational mode is a true fixed-baseline shadow implementation, which must be completed before serving routed recommendations.
