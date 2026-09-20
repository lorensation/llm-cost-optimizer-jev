# Jev routing shadow report

Dataset SHA-256: `372a55fae24adc71a05b28df1def9b429955ecb7d02e7ca0f80222a1299da1ac`. Questions: `config/jev-routing.json`, version `jev-routing-v1`.

> Diagnostic only: Jev signals are recorded, never applied to route selection in this phase.

## Availability

| status | count |
|---|---:|
| evaluated | 100 |

## Task-family identification (independent of the declared contract)

Overall agreement: **1.000** (100/100).

| contract | n | agreement rate |
|---|---:|---:|
| classify_ticket_v1 | 30 | 1.000 |
| context_qa_v1 | 30 | 1.000 |
| extract_invoice_v1 | 40 | 1.000 |

## Missing-evidence signal vs gold abstention (context_qa_v1 only)

Diagnostic midpoint of 0.5 on the noul probability; this is not a calibrated accept/reject threshold.

| | gold: evidence missing | gold: evidence present |
|---|---:|---:|
| Jev: missing (p>=0.5) | 6 (TP) | 0 (FP) |
| Jev: present (p<0.5) | 0 (FN) | 24 (TN) |
| n | 30 | |

## Cost and latency

Measured shadow decision cost: **2242 micro-USD** over 100 calls (22420 micro-USD per 1,000 decisions).
Latency p50 295.0 ms, p95 482.75 ms.

This overhead adds to the per-request routing/verification/audit sensitivity table in `artifacts/pilot/report.md`; it is Jev diagnostic cost only, not the full routing overhead (verification and audit calls are separate and still unmeasured for live traffic).

## Local baseline availability

0/100 cases had no eligible measured profile for the local contract-rule baseline (NoEligibleRoute).

## Interpretation and limitations

- Same 28 source/template groups as the phase 2 pilot underlie these 100 cases; case-level rates above likely overstate independent-sample accuracy and are provisional signal, not a final evaluation (see `artifacts/pilot/report.md`).
- This run shows Jev *can* recover task-family and missing-evidence signal from request/source text alone. It does not by itself show Jev improves on the phase 2 contract rule: that rule already reaches 100/100 success without Jev, and every request would pay this diagnostic cost regardless of benefit.
- Concrete follow-up for phase 4: the phase 2 economy-tier (Haiku) QA failures were all "states evidence absent, returns abstained: false"; Jev's missing-evidence signal matched the gold abstention label on all 30 QA cases here. A gated economy-plus-Jev-check route for context_qa_v1 is a falsifiable hypothesis to test with common verification, not a validated saving.
- Measured Jev overhead (22-24 micro-USD/request here) is well inside the 538.8 micro-USD/request break-even overhead computed in the phase 2 pilot report, leaving room for verification and audit cost that is not yet measured for live traffic.

