# Decisions

Updated 2026-09-19.

- Scope: V1 accepts only registered extraction, classification, and context-Q&A contracts. Streaming, tools, multimodal input, open advice, and persistent chat are rejected or absent.
- Jev transport: `openrouter_decisions` is the proposed default because it shares OpenRouter credentials and returns billed `usage.cost`. The final choice remains pending a budget-authorized real smoke. `typesafe_direct` is implemented as a replaceable fallback but does not invent a cost when the response lacks one.
- Models: repository defaults are fixture aliases only. They cannot be activated as real traffic. Real model IDs, endpoint snapshots, and prices require an authorized catalog snapshot and pilot.
- Money: all persisted amounts are integer micro-US dollars. Unknown external spend is `NULL`, never zero.
- Attempts: one initial generation plus at most one shared retry/fallback. Every candidate is verified; missing semantic verification is an error.
- Workload assumptions for local validation: Spanish and English, 24,000 source characters, 30 s request deadline. These are engineering defaults, not measured SLOs.
- Quality floors: extraction 0.84, classification 0.85, context Q&A 0.88 in fixture profiles. They are placeholders clearly marked synthetic and cannot justify promotion.
- Budgets: fixture mode costs no provider money. Smoke, pilot, evaluation, and operations budgets are pending owner authorization. Real smoke requires an explicit `--max-budget-microusd` argument.
- Promotion: disabled in this implementation until representative labels, grouped splits, calibrated gates, and an untouched final test support `promote`.

