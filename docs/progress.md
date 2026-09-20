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
| 6 | final experiment complete | The frozen 396-case test ran across four systems under identical common verification ($3.646015, 1,584 calls, no unknown costs): `fixed_balanced` 353/396 success/$0.857, `fixed_strong` 336/396/$1.521, `llm_judge_router` 353/396 correct of 357 delivered/$0.533 (4 false accepts), `jev_gated` 354/396/$0.735 (zero false accepts). The phase 3 missing-evidence-gate hypothesis is confirmed on context_qa_v1 (79/80 at $0.084 vs fixed balanced's 76/80 at $0.203); the Jev routing-decision call costs 24 micro-USD/call vs the traditional router's 369 micro-USD/call. `classify_code_request_v1` is the one family where the adaptive router beats our profile-based policy, an honest limitation of that family's small pilot, not the gate mechanism. See `artifacts/final/report.md`. Remaining: write the case-study narrative for publication and a promotion/scope decision for the case study itself (this remains a demo-scale case study, not the full PLAN section 10 promotion pipeline). |
| 7 | local packaging | Compose, read-only dashboard and fixture demo exist. Final case study depends on phase 6. |

Environment observed: Python 3.13.7, Node 22.18.0, Docker 28.5.2, SQLite 3.50.4. The app enables foreign keys, busy timeout and WAL migration mode.

Local verification: 68 tests pass, fixture smoke passes, Python byte-compilation passes, generated Pydantic configuration schema exists, and `docker compose config --quiet` accepts the Compose file. Phase 2 artifacts contain 300 unique case/model rows with complete billed cost. Migrations are now applied from a versioned directory (`migrations/001_initial.sql`, `migrations/002_audit_review.sql`) rather than a single fixed file.

Real smoke artifacts are `artifacts/smoke/haiku.json`, `sonnet.json`, and `opus.json`. The result only establishes connectivity, typed output, model/provider identity and cost reporting; it does not qualify routing quality.
