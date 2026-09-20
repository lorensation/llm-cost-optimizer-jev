# Provider contracts

Consulted 2026-09-19 from the live TypeSafe and OpenRouter documentation.

## OpenRouter generation

`POST https://openrouter.ai/api/v1/chat/completions`, Bearer authentication. The adapter disables SDK retries by using one direct HTTP request, requests strict JSON Schema output, records requested/resolved model, provider, token usage, billed cost when returned, latency, and failures. A timeout is `unknown`, because external execution and cost may have occurred.

## OpenRouter Decisions (proposed Jev transport)

`POST https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.13`. Request fields are `model`, structured `state`, and a question map. Choice criteria are a map, Score criteria an ordered list, and Noul returns the probability of yes without separate confidence. Responses expose `answers`, resolved `model`, `provider`, and `usage.cost`. The documented example currently resolves to a dated Jev model; the implementation preserves that value. The API is alpha and must pass the real smoke before selection is final.

## TypeSafe direct (fallback)

`POST https://api.typesafe.ai/v1/systemone`, Bearer authentication. The current docs recommend `jev-latest`, while this project intentionally pins an experiment model rather than silently following the alias. Response usage documents tokens but not billed USD, so cost remains unknown until reconciled from authoritative billing. Direct-service model IDs must not be assumed interchangeable with OpenRouter IDs.

## Semantic composition

Known schema/taxonomy checks run in code. Semantic questions are narrow and evidence-grounded; independent questions share a request where possible. The application aggregates mandatory checks with an all-pass rule. Cookbook thresholds and example savings are not treated as project results.

## Real smoke observed 2026-09-20

All three generation requests and all three OpenRouter Decisions requests succeeded. Each model returned the expected structured invoice extraction (`F-104`, total `120`). This validates connectivity and the response contract only.

| Alias | Requested/resolved model | Provider observed | Generation cost | Jev cost | Total |
|---|---|---|---:|---:|---:|
| economy | `anthropic/claude-haiku-4.5` | Amazon Bedrock | 334 micro-USD | 14 micro-USD | 348 micro-USD |
| balanced | `anthropic/claude-sonnet-5` | Claude Platform on AWS | 804 micro-USD | 14 micro-USD | 818 micro-USD |
| strong | `anthropic/claude-opus-5` | Claude Platform on AWS | 2,010 micro-USD | 14 micro-USD | 2,024 micro-USD |

Jev resolved to `typesafe/jev-1.13-20260917` in all three calls. Complete billed cost was returned. Total observed spend was 3,190 micro-USD ($0.00319). These single synthetic cases are not latency, quality, calibration, or savings measurements.

Sources: <https://docs.typesafe.ai/api>, <https://docs.typesafe.ai/primitives/choice>, <https://docs.typesafe.ai/primitives/noul>, <https://docs.typesafe.ai/primitives/score>, <https://docs.typesafe.ai/confidence>, <https://docs.typesafe.ai/concepts/state>, <https://docs.typesafe.ai/models>, <https://docs.typesafe.ai/cookbooks/sde_cascade>, <https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-questions-and-answers-request>.
