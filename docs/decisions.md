# Decisions

Updated 2026-09-19.

- Scope: V1 accepts only registered extraction, classification, and context-Q&A contracts. Streaming, tools, multimodal input, open advice, and persistent chat are rejected or absent.
- Jev transport: `openrouter_decisions` is confirmed for the phase 1/2 candidate because the 2026-09-20 real smoke returned typed answers, resolved model and billed `usage.cost`. `typesafe_direct` remains a replaceable experimental fallback; its separately funded key was not spent in this smoke because its HTTP response does not expose billed USD.
- Models: the phase 2 candidate pool is Haiku 4.5 (`economy`), Sonnet 5 (`balanced`) and Opus 5 (`strong`) through OpenRouter. Their 2026-09-20 catalog data is snapshotted. Bootstrap routing sends extraction/classification to Haiku, context Q&A to Sonnet, and keeps Opus as qualified fallback; this shape is not validated quality evidence.
- Money: all persisted amounts are integer micro-US dollars. Unknown external spend is `NULL`, never zero.
- Attempts: one initial generation plus at most one shared retry/fallback. Every candidate is verified; missing semantic verification is an error.
- Workload assumptions for local validation: Spanish and English, 24,000 source characters, 30 s request deadline. These are engineering defaults, not measured SLOs.
- Quality floors: extraction 0.84, classification 0.85, context Q&A 0.88 in fixture profiles. They are placeholders clearly marked synthetic and cannot justify promotion.
- Budgets: the owner authorized OpenRouter up to $12.30 and TypeSafe direct up to $5.00. Each real smoke used a local $0.02 preflight ceiling. The three phase 1 smokes consumed $0.00319 through OpenRouter; the phase 2 pilot used a $5 local ceiling and consumed $0.537627 for 300 generations. TypeSafe direct was not charged.
- Promotion: disabled in this implementation until representative labels, grouped splits, calibrated gates, and an untouched final test support `promote`.
- Phase 2 decision: `continue_router`, in shadow only. On the 100-case synthetic pilot, fixed Sonnet was the cheapest fixed configuration meeting every provisional contract floor at 100/100 successes and $0.137320. The contract rule Haiku for extraction/classification and Sonnet for Q&A also achieved 100/100 at $0.083444, a measured generation-cost difference of 39.2% before overhead. Its break-even overhead was 538.8 micro-USD/request. This establishes a routing opportunity, not Jev value: phase 3 must compare the simple rule with Jev under common verification.
- Pilot limitation: the 100 examples come from 28 source/template groups. Haiku's six failures are Q&A abstention-flag mismatches in two repeated groups. Case-level intervals are provisional and no active promotion or final-test claim follows from them.
