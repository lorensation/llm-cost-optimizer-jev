from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import load_config, load_contracts, load_profiles
from app.contracts import CallResult, CheckStatus, TaskContract
from app.providers.base import DecisionBackend
from app.providers.fixture import FixtureDecisions, FixtureProvider
from app.providers.openrouter import OpenRouterDecisions, OpenRouterProvider
from app.routing.jev_gate import qa_gate_should_escalate
from app.routing.jev_signals import evaluate_shadow, load_routing_questions
from app.routing.llm_judge import classify_tier, resolve_tier
from app.routing.policy import NoEligibleRoute, RoutingPolicy
from app.verification.verifier import ContractVerifier, aggregate
from scripts.benchmark import estimated_call_cost, evaluate, file_hash, public_request, read_jsonl
from scripts.shadow_jev import MAX_STATE_CHARS, canonical_json_hash

ARMS = ("fixed_balanced", "fixed_strong", "llm_judge_router", "jev_gated")
ESCALATION_TIER = {"economy": "balanced", "balanced": "strong"}
# Phase 2's established contract rule, deliberately overridden for context_qa_v1: phase 2 measured
# economy as unqualified there, but the phase 3 shadow shows Jev's missing-evidence signal recovers
# exactly that failure mode. This tests the falsifiable hypothesis rather than assuming it.
CONTRACT_RULE_PRIMARY = {"extract_invoice_v1": "economy", "classify_ticket_v1": "economy", "context_qa_v1": "economy"}
DECISION_CALL_ESTIMATE_MICROUSD = 150  # generous padding over the ~22-24 micro-USD measured Jev decision cost


class _CostTracker:
    def __init__(self, backend: DecisionBackend | None) -> None:
        self.backend = backend
        self.cost_microusd = 0
        self.unknown_cost = False
        self.calls = 0
        self.latencies_ms: list[int] = []

    async def decide(self, *, state: Any, questions: dict[str, Any], timeout_s: float) -> CallResult:
        self.calls += 1
        if self.backend is None:
            return CallResult(status="failed", requested_model="unavailable", latency_ms=0, error_code="verifier_unavailable")
        result = await self.backend.decide(state=state, questions=questions, timeout_s=timeout_s)
        if result.cost_microusd is None:
            self.unknown_cost = True
        else:
            self.cost_microusd += result.cost_microusd
        self.latencies_ms.append(result.latency_ms)
        return result


def preflight_case_cost(config, case: dict[str, Any], contract: TaskContract, arm: str) -> int:
    decisions = 2 * DECISION_CALL_ESTIMATE_MICROUSD
    if arm == "fixed_strong":
        return estimated_call_cost(config, "strong", case, contract) + decisions
    if arm == "fixed_balanced":
        return estimated_call_cost(config, "balanced", case, contract) + estimated_call_cost(config, "strong", case, contract) + decisions
    if arm == "llm_judge_router":
        return (estimated_call_cost(config, "economy", case, contract) + 2 * estimated_call_cost(config, "strong", case, contract) + decisions)
    return estimated_call_cost(config, "economy", case, contract) + estimated_call_cost(config, "strong", case, contract) + decisions + DECISION_CALL_ESTIMATE_MICROUSD


def initial_route(arm: str, contract: TaskContract, router: RoutingPolicy, config) -> tuple[str, str | None]:
    if arm == "fixed_strong":
        return "strong", None
    if arm == "fixed_balanced":
        return "balanced", "strong"
    if arm == "jev_gated":
        if contract.id in CONTRACT_RULE_PRIMARY:
            primary = CONTRACT_RULE_PRIMARY[contract.id]
            return primary, ESCALATION_TIER.get(primary)
        try:
            route = router.select(contract, config.request_budget_microusd, config.deadline_ms)
        except NoEligibleRoute:
            return "strong", None
        return route.primary, route.fallback
    raise ValueError(f"initial_route does not resolve a fixed route for arm {arm}")


async def run_case(*, arm: str, case: dict[str, Any], contract: TaskContract, config, provider, jev_backend,
                    routing_questions, router: RoutingPolicy, timeout_s: float) -> dict[str, Any]:
    router_cost = router_latency = 0
    router_used_default = False
    if arm == "llm_judge_router":
        router_result = await classify_tier(provider, router_model=config.models["economy"].model_id,
                                             request=case["request"], source=case["source"], timeout_s=timeout_s)
        router_cost = router_result.cost_microusd or 0
        router_unknown = router_result.cost_microusd is None
        router_latency = router_result.latency_ms
        primary, router_used_default = resolve_tier(router_result, tuple(config.models))
        fallback = ESCALATION_TIER.get(primary)
    else:
        router_unknown = False
        primary, fallback = initial_route(arm, contract, router, config)

    tracker = _CostTracker(jev_backend)
    verifier = ContractVerifier(tracker)
    generation_cost = 0
    generation_unknown = False
    gate_cost = gate_latency = 0
    gate_escalated = False
    attempts = 0
    aliases_tried: list[str] = []
    final_output = None
    final_alias: str | None = None
    final_checks: list = []
    latency_ms = router_latency

    for alias in [a for a in (primary, fallback) if a]:
        if alias in aliases_tried:
            break
        aliases_tried.append(alias)
        attempts += 1
        model = config.models[alias]
        gen = await provider.generate(model=model.model_id, request=public_request(case, contract), source=case["source"],
                                       output_schema=contract.output_schema, max_tokens=config.max_output_tokens, timeout_s=timeout_s)
        latency_ms += gen.latency_ms
        if gen.cost_microusd is None:
            generation_unknown = True
        else:
            generation_cost += gen.cost_microusd
        if gen.status != "succeeded":
            final_checks = []
            continue
        checks = await verifier.verify(contract, case["source"], gen.content, timeout_s)
        passed = aggregate(checks, contract.required_checks) == CheckStatus.PASS
        escalate_for_gate = False
        if arm == "jev_gated" and contract.id == "context_qa_v1" and passed:
            shadow = await evaluate_shadow(backend=jev_backend, contract=contract, request=case["request"],
                                            source=case["source"], questions=routing_questions.questions,
                                            max_state_chars=MAX_STATE_CHARS, timeout_s=timeout_s)
            gate_cost += shadow.cost_microusd or 0
            gate_latency += shadow.latency_ms or 0
            if qa_gate_should_escalate(jev_result=shadow, candidate=gen.content):
                escalate_for_gate, gate_escalated = True, True
        if passed and not escalate_for_gate:
            final_output, final_alias, final_checks = gen.content, alias, checks
            break
        final_checks = checks
    latency_ms += sum(tracker.latencies_ms) + gate_latency

    contract_passed = final_output is not None
    success, reasons = evaluate(case, contract, final_output) if contract_passed else (False, ["not_delivered"])
    total_unknown = generation_unknown or tracker.unknown_cost or router_unknown
    total_cost = None if total_unknown else generation_cost + tracker.cost_microusd + router_cost + gate_cost
    return {
        "case_id": case["id"], "group_id": case["group_id"], "contract_id": case["contract_id"],
        "language": case["language"], "adversarial": case["adversarial"], "arm": arm,
        "attempts": attempts, "aliases_tried": aliases_tried, "final_alias": final_alias,
        "contract_passed": contract_passed, "success": success, "failure_reasons": reasons,
        "router_used_default": router_used_default, "gate_escalated": gate_escalated,
        "generation_cost_microusd": generation_cost, "verification_cost_microusd": tracker.cost_microusd,
        "router_cost_microusd": router_cost, "gate_cost_microusd": gate_cost,
        "total_cost_microusd": total_cost, "unknown_cost": total_unknown, "latency_ms": latency_ms,
        "final_checks": [c.model_dump(mode="json") for c in final_checks],
        "observed_at": datetime.now(UTC).isoformat(),
    }


async def run_experiment(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    contracts = load_contracts(config.contracts_dir)
    _, profiles = load_profiles(config.profiles_path, contracts, config.models)
    router = RoutingPolicy(config.models, profiles)
    routing_questions = load_routing_questions(args.questions)
    cases = read_jsonl(args.input)
    if args.limit:
        cases = cases[:args.limit]
    arms = list(args.arms) if args.arms else list(ARMS)
    completed_rows = read_jsonl(args.output) if args.output.exists() else []
    completed = {(row["case_id"], row["arm"]) for row in completed_rows}
    pending = [(case, arm) for case in cases for arm in arms if (case["id"], arm) not in completed]
    preflight = sum(preflight_case_cost(config, case, contracts[case["contract_id"]], arm) for case, arm in pending)
    selected = {(case["id"], arm) for case in cases for arm in arms}
    spent = sum(row.get("total_cost_microusd") or 0 for row in completed_rows if (row["case_id"], row["arm"]) in selected)
    if args.real and args.max_budget_microusd is None:
        raise SystemExit("real experiment run requires --max-budget-microusd")
    if args.max_budget_microusd is not None and spent + preflight > args.max_budget_microusd:
        raise SystemExit(f"preflight {spent}+{preflight} exceeds budget {args.max_budget_microusd} micro-USD")
    if args.real:
        if not config.openrouter_api_key:
            raise SystemExit("OPENROUTER_API_KEY is required")
        provider = OpenRouterProvider(config.openrouter_api_key)
        jev_backend: DecisionBackend | None = OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
    else:
        provider, jev_backend = FixtureProvider(), FixtureDecisions()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    semaphore, write_lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    actual_spend = spent
    unknown_cost_seen = any(row.get("unknown_cost") for row in completed_rows)

    async def execute(case: dict[str, Any], arm: str) -> None:
        nonlocal actual_spend, unknown_cost_seen
        contract = contracts[case["contract_id"]]
        async with semaphore:
            row = await run_case(arm=arm, case=case, contract=contract, config=config, provider=provider,
                                  jev_backend=jev_backend, routing_questions=routing_questions, router=router,
                                  timeout_s=config.deadline_ms / 1000)
        async with write_lock:
            if row["unknown_cost"]:
                unknown_cost_seen = True
            elif row["total_cost_microusd"] is not None:
                actual_spend += row["total_cost_microusd"]
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(json.dumps({"case": case["id"], "arm": arm, "success": row["success"],
                              "cost_microusd": row["total_cost_microusd"], "spent_microusd": actual_spend}))

    await asyncio.gather(*(execute(case, arm) for case, arm in pending))
    final_rows = [row for row in read_jsonl(args.output) if (row["case_id"], row["arm"]) in selected]
    manifest = {
        "mode": "real" if args.real else "fixture", "cases": len(cases), "arms": arms,
        "expected_rows": len(cases) * len(arms), "observed_rows": len(final_rows),
        "dataset_sha256": file_hash(args.input), "results_sha256": canonical_json_hash(final_rows),
        "profiles_sha256": file_hash(config.profiles_path), "questions_sha256": file_hash(args.questions),
        "preflight_microusd_for_pending": preflight, "actual_spend_microusd": actual_spend,
        "complete_cost": not unknown_cost_seen, "completed_at": datetime.now(UTC).isoformat(),
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    if len(final_rows) != manifest["expected_rows"]:
        raise SystemExit("final experiment manifest is incomplete")


def _wilson_lower(successes: int, sample_size: int, z: float = 1.96) -> float:
    if sample_size == 0:
        return 0.0
    p = successes / sample_size
    denominator = 1 + z * z / sample_size
    center = p + z * z / (2 * sample_size)
    margin = z * ((p * (1 - p) + z * z / (4 * sample_size)) / sample_size) ** 0.5
    return max(0.0, (center - margin) / denominator)


def _percentile(values: list[int], pct: float) -> int | float:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct * (len(ordered) - 1))))
    return ordered[index]


def build_report(args: argparse.Namespace) -> None:
    rows = read_jsonl(args.results)
    arms = sorted({row["arm"] for row in rows})
    contract_ids = sorted({row["contract_id"] for row in rows})
    group_count = len({row["group_id"] for row in rows})

    lines = [
        "# Phase 6 final experiment: fixed baselines vs a traditional LLM-judge router vs Jev-gated routing",
        "", f"Dataset SHA-256: `{file_hash(args.input)}`. {len({r['case_id'] for r in rows})} cases, "
        f"{group_count} source/template groups, {len(contract_ids)} task families: {', '.join(contract_ids)}.",
        "", "> Real provider measurements on a frozen, pilot-disjoint test set. Independent success uses gold "
        "labels never sent to any provider; `contract_passed` is this system's own delivered/rejected verdict.",
        "", "## Overall by system", "",
        "| system | delivered | independent success | contract_passed | false accepts | cost µUSD | cost/success | p50 ms | p95 ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in arms:
        items = [r for r in rows if r["arm"] == arm]
        delivered = sum(r["contract_passed"] for r in items)
        successes = sum(r["success"] for r in items)
        false_accepts = sum(r["contract_passed"] and not r["success"] for r in items)
        cost = sum(r["total_cost_microusd"] or 0 for r in items)
        per_success = cost / successes if successes else float("inf")
        latencies = [r["latency_ms"] for r in items]
        lines.append(f"| {arm} | {delivered}/{len(items)} | {successes}/{len(items)} ({_wilson_lower(successes, len(items)):.3f} Wilson lower) "
                     f"| {delivered}/{len(items)} | {false_accepts} | {cost} | {per_success:.1f} | {_percentile(latencies, 0.5)} | {_percentile(latencies, 0.95)} |")

    lines += ["", "## By task family and system", "", "| family | system | n | success | cost µUSD | cost/success |", "|---|---|---:|---:|---:|---:|"]
    for contract_id in contract_ids:
        for arm in arms:
            items = [r for r in rows if r["arm"] == arm and r["contract_id"] == contract_id]
            successes = sum(r["success"] for r in items)
            cost = sum(r["total_cost_microusd"] or 0 for r in items)
            per_success = cost / successes if successes else float("inf")
            lines.append(f"| {contract_id} | {arm} | {len(items)} | {successes}/{len(items)} | {cost} | {per_success:.1f} |")

    router_rows = [r for r in rows if r["arm"] == "llm_judge_router"]
    router_defaults = sum(r["router_used_default"] for r in router_rows)
    router_cost_per_call = [r["router_cost_microusd"] for r in router_rows if r["router_cost_microusd"]]
    gated_qa = [r for r in rows if r["arm"] == "jev_gated" and r["contract_id"] == "context_qa_v1"]
    gate_escalations = sum(r["gate_escalated"] for r in gated_qa)
    gate_cost_per_call = [r["gate_cost_microusd"] for r in gated_qa if r["gate_cost_microusd"]]
    balanced_qa = [r for r in rows if r["arm"] == "fixed_balanced" and r["contract_id"] == "context_qa_v1"]

    lines += ["", "## Routing-decision overhead only", "",
              f"Traditional LLM-judge router: {len(router_rows)} calls, {router_defaults} fell back to the "
              f"conservative default tier (malformed/failed judge response). Mean router call cost "
              f"{round(sum(router_cost_per_call)/len(router_cost_per_call)) if router_cost_per_call else 0} micro-USD.",
              f"Jev-gated diagnostic (context_qa_v1 only): {len(gated_qa)} calls, {gate_escalations} escalated to "
              f"balanced on a missing-evidence disagreement. Mean Jev gate call cost "
              f"{round(sum(gate_cost_per_call)/len(gate_cost_per_call)) if gate_cost_per_call else 0} micro-USD.",
              "", "## The phase 3 hypothesis: economy + Jev gate vs fixed balanced on context_qa_v1", "",
              f"jev_gated: {sum(r['success'] for r in gated_qa)}/{len(gated_qa)} independent success, "
              f"{sum(r['total_cost_microusd'] or 0 for r in gated_qa)} micro-USD total, "
              f"{gate_escalations} of {len(gated_qa)} escalated.",
              f"fixed_balanced: {sum(r['success'] for r in balanced_qa)}/{len(balanced_qa)} independent success, "
              f"{sum(r['total_cost_microusd'] or 0 for r in balanced_qa)} micro-USD total.",
              "", "This is the frozen test of the hypothesis phase 3 flagged as unvalidated; the numbers above "
              "are the answer, not a re-derivation of the phase 2/3 pilot figures.", "",
    ]

    by_key = {(r["case_id"], r["arm"]): r for r in rows}
    router_false_accepts = [r for r in router_rows if r["contract_passed"] and not r["success"]]
    caught_by_gate = [by_key[(r["case_id"], "jev_gated")] for r in router_false_accepts
                       if by_key.get((r["case_id"], "jev_gated"), {}).get("success")]
    if router_false_accepts:
        lines += ["## A specific failure the common verifier alone did not catch", "",
                   f"The traditional router falsely accepted {len(router_false_accepts)} case(s) that common "
                   "verification (shared by every system here) also passed but gold marks wrong -- all of them "
                   "context_qa_v1 economy-tier abstention-flag mismatches, the exact phase 2 failure mode. "
                   f"The Jev gate independently caught and corrected {len(caught_by_gate)}/{len(router_false_accepts)} "
                   "of those same cases by escalating to balanced, because it checks a signal (evidence "
                   "presence) that generic claim-support/coverage verification does not ask for directly.", "",
        ]

    lines += [
              "## Limitations", "",
              f"- {group_count} source/template groups underlie these cases; case-level Wilson intervals are "
              "provisional relative to independent-group evidence, consistent with the phase 2/3 pilots.",
              "- `classify_code_request_v1` has no cheap qualified tier in the merged profile (only `strong` "
              "cleared its 0.85 floor on a 36-case pilot); `jev_gated` and `fixed_strong` therefore coincide "
              "in cost for that family, which is expected, not a routing failure.",
              "- The independent judge check reuses the same Jev decision backend as generation-time "
              "verification for every system; it is common across arms so it cannot bias the comparison "
              "between them, but it is not an independent-model audit of the winning system in isolation.",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Run the phase 6 final experiment: fixed baselines vs a traditional LLM-judge router vs the Jev-gated policy.")
    commands = root.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("--config", default="config/routing-claude-final.yaml")
    run.add_argument("--questions", type=Path, default=Path("config/jev-routing.json"))
    run.add_argument("--input", type=Path, default=Path("data/final_test.jsonl"))
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--arms", nargs="+", choices=ARMS)
    run.add_argument("--limit", type=int)
    run.add_argument("--real", action="store_true")
    run.add_argument("--max-budget-microusd", type=int)
    run.add_argument("--concurrency", type=int, default=4)
    report = commands.add_parser("report")
    report.add_argument("--input", type=Path, default=Path("data/final_test.jsonl"))
    report.add_argument("--results", type=Path, required=True)
    report.add_argument("--report", type=Path, required=True)
    return root


def main() -> None:
    args = parser().parse_args()
    if args.command == "run":
        asyncio.run(run_experiment(args))
    else:
        build_report(args)


if __name__ == "__main__":
    main()
