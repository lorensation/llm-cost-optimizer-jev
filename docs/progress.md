# Progress

Updated 2026-09-20.

| Phase | State | Evidence / remaining work |
|---|---|---|
| 0 | local complete | Skill and lock present; live contracts reviewed; decisions, provider contracts, environment and pending budgets documented. |
| 1 | complete | Local invariants plus real Haiku/Sonnet/Opus generation and OpenRouter Decisions smokes passed. Six calls cost $0.00319 with complete billing metadata. |
| 2 | complete | 100 labeled synthetic cases and 300 paired Claude generations completed with no provider errors or unknown costs. Spend was $0.537627. The decision is `continue_router`; evidence and provisional profiles remain blocked from active use. |
| 3 | ready for measured shadow | Reproducible empirical routing and explicit fallback exist. The next comparison is fixed Sonnet vs the contract rule vs Jev, with common verification and overhead accounting. |
| 4 | local implementation | Mandatory gates, two-attempt state machine, deadline/budget checks, idempotency and API are covered by tests. Calibration remains phase 6 work. |
| 5 | partial local implementation | Durable jobs, leases, ownership checks, payload expiry and transactional enqueue exist. Heartbeats, bounded retry policy, independent judge and human sampling remain pending. |
| 6 | pending experiment | No final dataset, frozen test, paid baselines, savings claim, or promotion decision exists. |
| 7 | local packaging | Compose, read-only dashboard and fixture demo exist. Final case study depends on phase 6. |

Environment observed: Python 3.13.7, Node 22.18.0, Docker 28.5.2, SQLite 3.50.4. The app enables foreign keys, busy timeout and WAL migration mode.

Local verification: 25 tests pass, fixture smoke passes, Python byte-compilation passes, generated Pydantic configuration schema exists, and `docker compose config --quiet` accepts the Compose file. Phase 2 artifacts contain 300 unique case/model rows with complete billed cost.

Real smoke artifacts are `artifacts/smoke/haiku.json`, `sonnet.json`, and `opus.json`. The result only establishes connectivity, typed output, model/provider identity and cost reporting; it does not qualify routing quality.
