# Progress

Updated 2026-09-20.

| Phase | State | Evidence / remaining work |
|---|---|---|
| 0 | local complete | Skill and lock present; live contracts reviewed; decisions, provider contracts, environment and pending budgets documented. |
| 1 | complete | Local invariants plus real Haiku/Sonnet/Opus generation and OpenRouter Decisions smokes passed. Six calls cost $0.00319 with complete billing metadata. |
| 2 | complete | 100 labeled synthetic cases and 300 paired Claude generations completed with no provider errors or unknown costs. Spend was $0.537627. The decision is `continue_router`; evidence and provisional profiles remain blocked from active use. |
| 3 | shadow signal captured | Reproducible empirical routing, explicit fallback, and a labeled trajectory-cost estimate exist. A real Jev shadow run over the 100 pilot cases ($0.002242) matched task family and missing-evidence gold labels on every case, diagnostic only and not yet applied to selection. Remaining: turn the diagnostic into a tested gate under fase 4's common verification and re-run the fixed/rule/Jev comparison with that gate in place. |
| 4 | local implementation | Mandatory gates, two-attempt state machine, deadline/budget checks, idempotency and API are covered by tests. Calibration remains phase 6 work. |
| 5 | local complete | Durable jobs, leases, ownership checks, payload expiry and transactional enqueue exist. Heartbeats (`Store.heartbeat_job`), a bounded retry policy that distinguishes recoverable/exhausted/skipped (`Store.fail_job`), an independent-judge worker pass that reuses `ContractVerifier` against the configured decision backend, and human-sampling routing (`audit_human_sample_probability`, `Store.record_human_review`) are implemented and tested with fixtures. The judge currently reuses the same decision backend as generation-time verification, not yet a different model family; that independence gap is explicit, not claimed. |
| 6 | dataset and live routing ready | Final test dataset built (396 cases, 107 groups, 4 task families incl. new `classify_code_request_v1`) and disjoint from the pilot. A dedicated 36-case pilot measured `classify_code_request_v1` ($0.211317) and its merged profile (`config/profiles-final.json`, via `scripts/merge_profiles.py`) now lets `RoutingPolicy` resolve a live route for all four families (`config/routing-claude-final.yaml`). Still missing: the traditional LLM-judge router baseline, the Jev-gated policy, the final experiment runner, the frozen test run itself, and the promotion/case-study decision. |
| 7 | local packaging | Compose, read-only dashboard and fixture demo exist. Final case study depends on phase 6. |

Environment observed: Python 3.13.7, Node 22.18.0, Docker 28.5.2, SQLite 3.50.4. The app enables foreign keys, busy timeout and WAL migration mode.

Local verification: 55 tests pass, fixture smoke passes, Python byte-compilation passes, generated Pydantic configuration schema exists, and `docker compose config --quiet` accepts the Compose file. Phase 2 artifacts contain 300 unique case/model rows with complete billed cost. Migrations are now applied from a versioned directory (`migrations/001_initial.sql`, `migrations/002_audit_review.sql`) rather than a single fixed file.

Real smoke artifacts are `artifacts/smoke/haiku.json`, `sonnet.json`, and `opus.json`. The result only establishes connectivity, typed output, model/provider identity and cost reporting; it does not qualify routing quality.
