# Data

`pilot.jsonl` is a deterministic synthetic pilot dataset with 100 independently specified cases: 40 extraction, 30 classification, and 30 context-Q&A. It mixes Spanish and English, grouped templates, missing evidence, ambiguity, and embedded adversarial instructions.

Every row contains stable `id`, `group_id`, `contract_id`, language, request, source, requirements, and an `expected` label. The benchmark runner removes `expected` and all diagnostic metadata before constructing provider requests. Do not reuse the synthetic pilot as an untouched final test set.

Regenerate it with `python scripts/generate_pilot_data.py` and record the emitted SHA-256 in experiment manifests.
