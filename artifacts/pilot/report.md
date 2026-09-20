# Claude pilot report

Dataset SHA-256: `372a55fae24adc71a05b28df1def9b429955ecb7d02e7ca0f80222a1299da1ac`.

> Real provider measurements on a synthetic pilot. This is not an untouched final test.

| contract | model | n | success | Wilson lower 95% | cost µUSD | cost/success | p95 ms | errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| classify_ticket_v1 | balanced | 30 | 1.000 | 0.886 | 39980 | 1332.7 | 4636 | 0 |
| classify_ticket_v1 | economy | 30 | 1.000 | 0.886 | 11619 | 387.3 | 1508 | 0 |
| classify_ticket_v1 | strong | 30 | 1.000 | 0.886 | 91675 | 3055.8 | 4870 | 0 |
| context_qa_v1 | balanced | 30 | 1.000 | 0.886 | 54450 | 1815.0 | 4317 | 0 |
| context_qa_v1 | economy | 30 | 0.800 | 0.627 | 17013 | 708.9 | 2303 | 0 |
| context_qa_v1 | strong | 30 | 1.000 | 0.886 | 155000 | 5166.7 | 4460 | 0 |
| extract_invoice_v1 | balanced | 40 | 1.000 | 0.912 | 42890 | 1072.2 | 2864 | 0 |
| extract_invoice_v1 | economy | 40 | 1.000 | 0.912 | 17375 | 434.4 | 1725 | 0 |
| extract_invoice_v1 | strong | 40 | 1.000 | 0.912 | 107625 | 2690.6 | 2913 | 0 |

Total measured generation cost: **537627 micro-USD ($0.537627)**.

## Fixed baselines and routing opportunity

| policy | successes | generation cost µUSD | cost/success µUSD | meets every contract floor |
|---|---:|---:|---:|---:|
| fixed economy | 94/100 | 46007 | 489.4 | no |
| fixed balanced | 100/100 | 137320 | 1373.2 | yes |
| fixed strong | 100/100 | 354300 | 3543.0 | yes |
| proposed contract route | 100/100 | 83444 | 834.4 | yes |

The proposed route (economy extraction/classification + balanced Q&A) costs **39.2% less** than the cheapest acceptable fixed baseline (balanced) before routing, verification, and audit overhead.
Its break-even overhead is **538.8 micro-USD per request** on this 100-case mix.

| added overhead per request µUSD | net cost µUSD | saving vs fixed balanced |
|---:|---:|---:|
| 0 | 83444 | 39.2% |
| 100 | 93444 | 32.0% |
| 250 | 108444 | 21.0% |
| 500 | 133444 | 2.8% |

## Failure concentration and limitations

- 6 failures occurred across 2 source/template groups; all were economy Q&A abstention-flag mismatches. The answers stated that evidence was absent but returned `abstained: false`.
- The 100 synthetic cases contain 28 source/template groups. Case-level Wilson intervals therefore overstate independent evidence and are retained only as provisional profile inputs.
- Generation cost is measured billing. Routing, verification, and audit overhead above is sensitivity analysis, not billed savings. Gold labels were never sent to providers.

## Decision

**`continue_router`**, limited to shadow experimentation. The pilot shows a contract-level cost/quality difference that can beat fixed Sonnet within the measured overhead envelope. A simple contract rule already captures this opportunity, so phase 3 must measure whether Jev improves on that rule; this pilot does not justify active routing or a claim that Jev adds value.
