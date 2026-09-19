# Progress

Updated 2026-09-19.

| Phase | State | Evidence / remaining work |
|---|---|---|
| 0 | local complete | Skill and lock present; live contracts reviewed; decisions, provider contracts, environment and pending budgets documented. |
| 1 | local complete; real smoke pending | Executable API, strict config, migration, reservations, providers, fixture smoke, cost units and failure semantics. No paid call was made. |
| 2 | blocked on representative labels and budget | Benchmark reducer exists; no 100–200 case dataset or real model outputs are fabricated. |
| 3 | fixture implementation | Reproducible empirical routing and explicit fallback exist. Synthetic profiles cannot enable production active mode. Shadow comparison awaits pilot data. |
| 4 | local implementation | Mandatory gates, two-attempt state machine, deadline/budget checks, idempotency and API are covered by tests. Calibration remains phase 6 work. |
| 5 | partial local implementation | Durable jobs, leases, ownership checks, payload expiry and transactional enqueue exist. Heartbeats, bounded retry policy, independent judge and human sampling remain pending. |
| 6 | pending experiment | No final dataset, frozen test, paid baselines, savings claim, or promotion decision exists. |
| 7 | local packaging | Compose, read-only dashboard and fixture demo exist. Final case study depends on phase 6. |

Environment observed: Python 3.13.7, Node 22.18.0, Docker 28.5.2, SQLite 3.50.4. The app enables foreign keys, busy timeout and WAL migration mode.

Local verification: 16 tests pass, fixture smoke passes, Python byte-compilation passes, generated Pydantic configuration schema exists, and `docker compose config --quiet` accepts the Compose file.

No provider spend was authorized or incurred by this implementation.
