# Decisions

Updated 2026-09-19.

- Scope: V1 accepts only registered extraction, classification, and context-Q&A contracts. Streaming, tools, multimodal input, open advice, and persistent chat are rejected or absent.
- Jev transport: `openrouter_decisions` is confirmed for the phase 1/2 candidate because the 2026-09-20 real smoke returned typed answers, resolved model and billed `usage.cost`. `typesafe_direct` remains a replaceable experimental fallback; its separately funded key was not spent in this smoke because its HTTP response does not expose billed USD.
- Models: the phase 2 candidate pool is Haiku 4.5 (`economy`), Sonnet 5 (`balanced`) and Opus 5 (`strong`) through OpenRouter. Their 2026-09-20 catalog data is snapshotted. Bootstrap routing sends extraction/classification to Haiku, context Q&A to Sonnet, and keeps Opus as qualified fallback; this shape is not validated quality evidence.
- Money: all persisted amounts are integer micro-US dollars. Unknown external spend is `NULL`, never zero.
- Attempts: one initial generation plus at most one shared retry/fallback. Every candidate is verified; missing semantic verification is an error.
- Workload assumptions for local validation: Spanish and English, 24,000 source characters, 30 s request deadline. These are engineering defaults, not measured SLOs.
- Quality floors: extraction 0.84, classification 0.85, context Q&A 0.88 in fixture profiles. They are placeholders clearly marked synthetic and cannot justify promotion.
- Budgets: the owner authorized OpenRouter up to $12.30 and TypeSafe direct up to $5.00. Each real smoke also used a local $0.02 preflight ceiling. The three phase 1 smokes consumed $0.00319 through OpenRouter in total; pilot/evaluation/operation sub-budgets remain to be declared before phase 2 calls.
- Promotion: disabled in this implementation until representative labels, grouped splits, calibrated gates, and an untouched final test support `promote`.
