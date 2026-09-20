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

This is a bootstrap shape, not a quality result. `config/profiles-claude-bootstrap.json` is explicitly blocked from active mode. Phase 2 must replace its placeholder quality, cost, and latency fields with measurements.

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

## Enter phase 2

1. Freeze the three model IDs, generation settings, contracts, rubrics, language mix, and pilot budget.
2. Build 100–200 reviewed cases in `data/pilot.jsonl`, grouped by source/template. Include missing values, ambiguity, Spanish and English, and adversarial instructions embedded in source data.
3. Keep gold labels outside all production prompts and verifier state.
4. Add a resumable pilot runner. The current `scripts/benchmark.py` only reduces an existing result manifest; it does not call providers.
5. Run Haiku, Sonnet, and Opus on the same eligible cases. Persist every output, error, latency, resolved model/provider, tokens, and billed/unknown cost.
6. Evaluate deterministic format separately from semantic correctness and source support.
7. Produce measured profiles per contract/model with sample size, success interval, p95 latency, expected route cost, data/rubric hashes, and experiment conditions.
8. Compare fixed Haiku, fixed Sonnet, fixed Opus, and the proposed routing opportunity with estimated verification/audit overhead clearly separated.
9. Decide `continue_router`, `simplify_fixed_model`, or `insufficient_evidence`.

Do not set `mode: active` in phase 2. The next operational mode is a true fixed-baseline shadow implementation, which must be completed before serving routed recommendations.
