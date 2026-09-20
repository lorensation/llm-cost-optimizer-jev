# Claude pilot report

Dataset SHA-256: `372a55fae24adc71a05b28df1def9b429955ecb7d02e7ca0f80222a1299da1ac`.

> Real provider measurements on a synthetic pilot. This is not an untouched final test.

| contract | model | n | success | Wilson lower 95% | cost µUSD | cost/success | p95 ms | errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| classify_ticket_v1 | balanced | 7 | 1.000 | 0.646 | 8110 | 1158.6 | 3522 | 0 |
| classify_ticket_v1 | economy | 7 | 1.000 | 0.646 | 2704 | 386.3 | 1509 | 0 |
| classify_ticket_v1 | strong | 7 | 1.000 | 0.646 | 20725 | 2960.7 | 5641 | 0 |
| context_qa_v1 | balanced | 6 | 1.000 | 0.610 | 10640 | 1773.3 | 3708 | 0 |
| context_qa_v1 | economy | 6 | 0.833 | 0.436 | 3464 | 692.8 | 2478 | 0 |
| context_qa_v1 | strong | 6 | 1.000 | 0.610 | 29625 | 4937.5 | 3801 | 0 |
| extract_invoice_v1 | balanced | 7 | 1.000 | 0.646 | 7418 | 1059.7 | 2661 | 0 |
| extract_invoice_v1 | economy | 7 | 1.000 | 0.646 | 3022 | 431.7 | 1780 | 0 |
| extract_invoice_v1 | strong | 7 | 1.000 | 0.646 | 18970 | 2710.0 | 3572 | 0 |

Total measured generation cost: **104678 micro-USD ($0.104678)**.

Failure details remain in the JSONL manifest; gold labels were not sent to providers.
