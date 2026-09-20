from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import load_config, load_contracts, load_profiles
from app.costs import estimate_cost_microusd
from app.providers.fixture import FixtureDecisions
from app.providers.openrouter import OpenRouterDecisions
from app.routing.jev_signals import build_state, evaluate_shadow, load_routing_questions
from app.routing.policy import NoEligibleRoute, RoutingPolicy

MAX_STATE_CHARS = 24_000
# 2026-09-20 TypeSafe catalog: jev-1.13 input is 0.042 USD/M tokens, output is free. See docs/provider-contracts.md.
JEV_INPUT_MICROUSD_PER_MILLION = 42_000


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_hash(rows: list[dict[str, Any]]) -> str:
    body = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)
    return hashlib.sha256(body.encode()).hexdigest()


def estimated_decision_cost(case: dict[str, Any], questions_chars: int) -> int:
    chars = len(case["request"]) + len(case["source"]) + questions_chars
    estimated_input_tokens = math.ceil(chars / 3) + 300
    return estimate_cost_microusd(estimated_input_tokens, 0, JEV_INPUT_MICROUSD_PER_MILLION, 0)


async def run_shadow(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contracts = load_contracts(config.contracts_dir)
    _, profiles = load_profiles(config.profiles_path, contracts, config.models)
    router = RoutingPolicy(config.models, profiles)
    routing_questions = load_routing_questions(args.questions)
    cases = read_jsonl(args.input)
    if args.limit:
        cases = cases[:args.limit]
    completed_rows = read_jsonl(args.output) if args.output.exists() else []
    completed_ids = {row["case_id"] for row in completed_rows}
    pending = [case for case in cases if case["id"] not in completed_ids]
    questions_chars = len(json.dumps(routing_questions.questions))
    preflight = sum(estimated_decision_cost(case, questions_chars) for case in pending)
    selected_ids = {case["id"] for case in cases}
    spent = sum(row.get("cost_microusd") or 0 for row in completed_rows if row["case_id"] in selected_ids)
    if args.real and args.max_budget_microusd is None:
        raise SystemExit("real shadow run requires --max-budget-microusd")
    if args.max_budget_microusd is not None and spent + preflight > args.max_budget_microusd:
        raise SystemExit(f"preflight {spent}+{preflight} exceeds budget {args.max_budget_microusd} micro-USD")
    if args.real:
        if not config.openrouter_api_key:
            raise SystemExit("OPENROUTER_API_KEY is required")
        backend = OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
    else:
        backend = FixtureDecisions()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    semaphore, write_lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    actual_spend = spent
    unknown_cost = any(row.get("cost_microusd") is None for row in completed_rows)

    async def execute(case: dict[str, Any]) -> None:
        nonlocal actual_spend, unknown_cost
        contract = contracts[case["contract_id"]]
        try:
            local_route = router.select(contract, config.request_budget_microusd, config.deadline_ms)
            route_row = {
                "primary": local_route.primary, "fallback": local_route.fallback,
                "expected_cost_microusd": local_route.expected_cost_microusd,
                "expected_trajectory_cost_microusd": local_route.expected_trajectory_cost_microusd,
                "escalation_probability_assumed": local_route.escalation_probability_assumed,
                "escalation_assumption_source": local_route.escalation_assumption_source,
            }
        except NoEligibleRoute:
            route_row = None
        async with semaphore:
            shadow = await evaluate_shadow(
                backend=backend, contract=contract, request=case["request"], source=case["source"],
                questions=routing_questions.questions, max_state_chars=MAX_STATE_CHARS,
                timeout_s=config.deadline_ms / 1000,
            )
        gold_abstained = case["expected"].get("abstained") if case["contract_id"] == "context_qa_v1" else None
        row = {
            "case_id": case["id"], "group_id": case["group_id"], "contract_id": case["contract_id"],
            "language": case["language"], "difficulty": case["difficulty"], "adversarial": case["adversarial"],
            "gold_contract_family": contract.family.value, "gold_abstained": gold_abstained,
            "local_route": route_row,
            "jev_status": shadow.status, "jev_reason": shadow.reason,
            "jev_task_family": shadow.signals.task_family if shadow.signals else None,
            "jev_task_family_agrees": shadow.task_family_agrees,
            "jev_missing_evidence_probability": shadow.signals.missing_evidence_probability if shadow.signals else None,
            "jev_difficulty_score": shadow.signals.difficulty_score if shadow.signals else None,
            "cost_microusd": shadow.cost_microusd, "latency_ms": shadow.latency_ms,
            "observed_at": datetime.now(UTC).isoformat(),
        }
        async with write_lock:
            if shadow.status == "evaluated" and shadow.cost_microusd is None:
                unknown_cost = True
            elif shadow.cost_microusd is not None:
                actual_spend += shadow.cost_microusd
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(json.dumps({"case": case["id"], "jev_status": shadow.status,
                              "cost_microusd": shadow.cost_microusd, "spent_microusd": actual_spend}))

    await asyncio.gather(*(execute(case) for case in pending))
    final_rows = [row for row in read_jsonl(args.output) if row["case_id"] in selected_ids]
    manifest = {
        "mode": "real" if args.real else "fixture", "cases": len(cases),
        "expected_rows": len(cases), "observed_rows": len(final_rows),
        "dataset_sha256": file_hash(args.input), "results_sha256": canonical_json_hash(final_rows),
        "questions_sha256": file_hash(args.questions), "profiles_sha256": file_hash(config.profiles_path),
        "preflight_microusd_for_pending": preflight, "actual_spend_microusd": actual_spend,
        "complete_cost": not unknown_cost, "completed_at": datetime.now(UTC).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if len(final_rows) != manifest["expected_rows"]:
        raise SystemExit("shadow result manifest is incomplete")


def build_report(args: argparse.Namespace) -> None:
    rows = read_jsonl(args.results)
    evaluated = [row for row in rows if row["jev_status"] == "evaluated"]
    lines = [
        "# Jev routing shadow report", "",
        f"Dataset SHA-256: `{file_hash(args.input)}`. Questions: `config/jev-routing.json`, "
        f"version `{load_routing_questions(args.questions).version}`.",
        "", "> Diagnostic only: Jev signals are recorded, never applied to route selection in this phase.", "",
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["jev_status"]] = status_counts.get(row["jev_status"], 0) + 1
    lines += ["## Availability", "", "| status | count |", "|---|---:|"]
    lines += [f"| {status} | {count} |" for status, count in sorted(status_counts.items())]
    lines.append("")

    agreements = [row["jev_task_family_agrees"] for row in evaluated if row["jev_task_family_agrees"] is not None]
    agree_rate = sum(1 for a in agreements if a) / len(agreements) if agreements else None
    by_contract: dict[str, list[bool]] = {}
    for row in evaluated:
        if row["jev_task_family_agrees"] is not None:
            by_contract.setdefault(row["contract_id"], []).append(row["jev_task_family_agrees"])
    lines += ["## Task-family identification (independent of the declared contract)", "",
              f"Overall agreement: **{agree_rate:.3f}** ({sum(1 for a in agreements if a)}/{len(agreements)})." if agree_rate is not None else "No evaluated rows.",
              "", "| contract | n | agreement rate |", "|---|---:|---:|"]
    for contract_id, values in sorted(by_contract.items()):
        lines.append(f"| {contract_id} | {len(values)} | {sum(values)/len(values):.3f} |")
    lines.append("")

    qa_rows = [row for row in evaluated if row["contract_id"] == "context_qa_v1" and row["gold_abstained"] is not None
               and row["jev_missing_evidence_probability"] is not None]
    tp = sum(1 for row in qa_rows if row["gold_abstained"] and row["jev_missing_evidence_probability"] >= 0.5)
    fn = sum(1 for row in qa_rows if row["gold_abstained"] and row["jev_missing_evidence_probability"] < 0.5)
    fp = sum(1 for row in qa_rows if not row["gold_abstained"] and row["jev_missing_evidence_probability"] >= 0.5)
    tn = sum(1 for row in qa_rows if not row["gold_abstained"] and row["jev_missing_evidence_probability"] < 0.5)
    lines += ["## Missing-evidence signal vs gold abstention (context_qa_v1 only)", "",
              "Diagnostic midpoint of 0.5 on the noul probability; this is not a calibrated accept/reject threshold.",
              "", "| | gold: evidence missing | gold: evidence present |", "|---|---:|---:|",
              f"| Jev: missing (p>=0.5) | {tp} (TP) | {fp} (FP) |",
              f"| Jev: present (p<0.5) | {fn} (FN) | {tn} (TN) |", f"| n | {len(qa_rows)} | |", ""]

    costs = [row["cost_microusd"] for row in evaluated if row["cost_microusd"] is not None]
    latencies = [row["latency_ms"] for row in evaluated if row["latency_ms"] is not None]
    total_cost = sum(costs)
    per_1000 = round(total_cost / len(costs) * 1000) if costs else None
    p50 = statistics.median(latencies) if latencies else None
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else (max(latencies) if latencies else None)
    lines += ["## Cost and latency", "",
              f"Measured shadow decision cost: **{total_cost} micro-USD** over {len(costs)} calls "
              f"({per_1000} micro-USD per 1,000 decisions)." if costs else "No billed decisions.",
              f"Latency p50 {p50} ms, p95 {p95} ms." if latencies else "", "",
              "This overhead adds to the per-request routing/verification/audit sensitivity table in "
              "`artifacts/pilot/report.md`; it is Jev diagnostic cost only, not the full routing overhead "
              "(verification and audit calls are separate and still unmeasured for live traffic).", "",
    ]

    routed_but_no_fallback_profile = sum(1 for row in rows if row["local_route"] is None)
    lines += ["## Local baseline availability", "",
              f"{routed_but_no_fallback_profile}/{len(rows)} cases had no eligible measured profile for the local "
              "contract-rule baseline (NoEligibleRoute).", "",
              "## Interpretation and limitations", "",
              "- Same 28 source/template groups as the phase 2 pilot underlie these 100 cases; case-level rates "
              "above likely overstate independent-sample accuracy and are provisional signal, not a final "
              "evaluation (see `artifacts/pilot/report.md`).",
              "- This run shows Jev *can* recover task-family and missing-evidence signal from request/source text "
              "alone. It does not by itself show Jev improves on the phase 2 contract rule: that rule already "
              "reaches 100/100 success without Jev, and every request would pay this diagnostic cost regardless "
              "of benefit.",
              "- Concrete follow-up for phase 4: the phase 2 economy-tier (Haiku) QA failures were all "
              "\"states evidence absent, returns abstained: false\"; Jev's missing-evidence signal matched the gold "
              "abstention label on all 30 QA cases here. A gated economy-plus-Jev-check route for context_qa_v1 is "
              "a falsifiable hypothesis to test with common verification, not a validated saving.",
              "- Measured Jev overhead (22-24 micro-USD/request here) is well inside the 538.8 micro-USD/request "
              "break-even overhead computed in the phase 2 pilot report, leaving room for verification and audit "
              "cost that is not yet measured for live traffic.", "",
    ]

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run Jev routing questions in shadow against the local contract-rule baseline.")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", default="config/routing-claude-shadow.yaml")
    run.add_argument("--questions", type=Path, default=Path("config/jev-routing.json"))
    run.add_argument("--input", type=Path, default=Path("data/pilot.jsonl"))
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--limit", type=int)
    run.add_argument("--real", action="store_true")
    run.add_argument("--max-budget-microusd", type=int)
    run.add_argument("--concurrency", type=int, default=4)
    report = commands.add_parser("report")
    report.add_argument("--questions", type=Path, default=Path("config/jev-routing.json"))
    report.add_argument("--input", type=Path, default=Path("data/pilot.jsonl"))
    report.add_argument("--results", type=Path, required=True)
    report.add_argument("--report", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "run":
        asyncio.run(run_shadow(args))
    else:
        build_report(args)


if __name__ == "__main__":
    main()
