# Phase 6 final experiment: fixed baselines vs a traditional LLM-judge router vs Jev-gated routing

Dataset SHA-256: `44ef861512057a39172ee84e973d7d2bd21f41c0ad87535fdd083f9e176c4393`. 396 cases, 107 source/template groups, 4 task families: classify_code_request_v1, classify_ticket_v1, context_qa_v1, extract_invoice_v1.

> Real provider measurements on a frozen, pilot-disjoint test set. Independent success uses gold labels never sent to any provider; `contract_passed` is this system's own delivered/rejected verdict.

## Overall by system

| system | delivered | independent success | contract_passed | false accepts | cost µUSD | cost/success | p50 ms | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_balanced | 353/396 | 353/396 (0.857 Wilson lower) | 353/396 | 0 | 857229 | 2428.4 | 2252 | 8296 |
| fixed_strong | 336/396 | 336/396 (0.810 Wilson lower) | 336/396 | 0 | 1521401 | 4528.0 | 2698 | 4780 |
| jev_gated | 354/396 | 354/396 (0.860 Wilson lower) | 354/396 | 0 | 734819 | 2075.8 | 2187 | 5918 |
| llm_judge_router | 357/396 | 353/396 (0.857 Wilson lower) | 357/396 | 4 | 532566 | 1508.7 | 2628 | 6844 |

## By task family and system

| family | system | n | success | cost µUSD | cost/success |
|---|---|---:|---:|---:|---:|
| classify_code_request_v1 | fixed_balanced | 140 | 119/140 | 334406 | 2810.1 |
| classify_code_request_v1 | fixed_strong | 140 | 118/140 | 535900 | 4541.5 |
| classify_code_request_v1 | jev_gated | 140 | 119/140 | 534203 | 4489.1 |
| classify_code_request_v1 | llm_judge_router | 140 | 120/140 | 238444 | 1987.0 |
| classify_ticket_v1 | fixed_balanced | 80 | 62/80 | 210607 | 3396.9 |
| classify_ticket_v1 | fixed_strong | 80 | 57/80 | 267647 | 4695.6 |
| classify_ticket_v1 | jev_gated | 80 | 60/80 | 74918 | 1248.6 |
| classify_ticket_v1 | llm_judge_router | 80 | 61/80 | 119443 | 1958.1 |
| context_qa_v1 | fixed_balanced | 80 | 76/80 | 202534 | 2664.9 |
| context_qa_v1 | fixed_strong | 80 | 65/80 | 436849 | 6720.8 |
| context_qa_v1 | jev_gated | 80 | 79/80 | 83934 | 1062.5 |
| context_qa_v1 | llm_judge_router | 80 | 76/80 | 96308 | 1267.2 |
| extract_invoice_v1 | fixed_balanced | 96 | 96/96 | 109682 | 1142.5 |
| extract_invoice_v1 | fixed_strong | 96 | 96/96 | 281005 | 2927.1 |
| extract_invoice_v1 | jev_gated | 96 | 96/96 | 41764 | 435.0 |
| extract_invoice_v1 | llm_judge_router | 96 | 96/96 | 78371 | 816.4 |

## Routing-decision overhead only

Traditional LLM-judge router: 396 calls, 0 fell back to the conservative default tier (malformed/failed judge response). Mean router call cost 369 micro-USD.
Jev-gated diagnostic (context_qa_v1 only): 80 calls, 5 escalated to balanced on a missing-evidence disagreement. Mean Jev gate call cost 24 micro-USD.

## The phase 3 hypothesis: economy + Jev gate vs fixed balanced on context_qa_v1

jev_gated: 79/80 independent success, 83934 micro-USD total, 5 of 80 escalated.
fixed_balanced: 76/80 independent success, 202534 micro-USD total.

This is the frozen test of the hypothesis phase 3 flagged as unvalidated; the numbers above are the answer, not a re-derivation of the phase 2/3 pilot figures.

## A specific failure the common verifier alone did not catch

The traditional router falsely accepted 4 case(s) that common verification (shared by every system here) also passed but gold marks wrong -- all of them context_qa_v1 economy-tier abstention-flag mismatches, the exact phase 2 failure mode. The Jev gate independently caught and corrected 4/4 of those same cases by escalating to balanced, because it checks a signal (evidence presence) that generic claim-support/coverage verification does not ask for directly.

## Limitations

- 107 source/template groups underlie these cases; case-level Wilson intervals are provisional relative to independent-group evidence, consistent with the phase 2/3 pilots.
- `classify_code_request_v1` has no cheap qualified tier in the merged profile (only `strong` cleared its 0.85 floor on a 36-case pilot); `jev_gated` and `fixed_strong` therefore coincide in cost for that family, which is expected, not a routing failure.
- The independent judge check reuses the same Jev decision backend as generation-time verification for every system; it is common across arms so it cannot bias the comparison between them, but it is not an independent-model audit of the winning system in isolation.
