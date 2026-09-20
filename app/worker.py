from __future__ import annotations

import argparse
import asyncio
import json
import socket
import time
from datetime import UTC, datetime

from app.config import load_config, load_contracts
from app.contracts import TaskContract
from app.persistence import Store
from app.providers.base import DecisionBackend
from app.providers.fixture import FixtureDecisions
from app.providers.openrouter import OpenRouterDecisions
from app.providers.typesafe import TypeSafeDirect
from app.verification.verifier import ContractVerifier, aggregate


def run_once(store: Store, contracts: dict[str, TaskContract], judge_backend: DecisionBackend | None,
             owner: str, max_attempts: int, lease_seconds: int = 30, timeout_s: float = 30) -> bool:
    store.expire_payloads()
    job = store.claim_job(owner, lease_seconds=lease_seconds)
    if not job:
        return False
    payload = json.loads(job["payload_json"]) if job["payload_json"] else None
    if payload is None:
        if not store.complete_job(job["id"], owner, {"status": "skipped", "reason": "payload_expired"}):
            raise RuntimeError("lease lost before completion")
        return True
    if job["needs_human_review"]:
        # Human review is prioritized over an LLM judge (PLAN section 7). This worker only parks the job;
        # app.persistence.store.Store.record_human_review records the actual verdict once a reviewer acts.
        if not store.complete_job(job["id"], owner, {"status": "pending_human_review",
                                                       "observed_at": datetime.now(UTC).isoformat()}):
            raise RuntimeError("lease lost before completion")
        return True
    contract = contracts.get(payload.get("contract_id"))
    if contract is None:
        store.fail_job(job["id"], owner, max_attempts, "unknown_contract")
        return True
    # Extend the lease before the network call so a slow judge is not reclaimed by another worker mid-flight.
    store.heartbeat_job(job["id"], owner, lease_seconds=max(lease_seconds, int(timeout_s) + 5))
    verifier = ContractVerifier(judge_backend)
    try:
        checks = asyncio.run(verifier.verify(contract, payload["source"], payload["output"], timeout_s))
    except Exception as exc:  # defensive: a judge crash is a recoverable failure, never a silent pass
        store.fail_job(job["id"], owner, max_attempts, type(exc).__name__)
        return True
    status = aggregate(checks, contract.required_checks)
    result = {
        "status": "judge_reviewed", "judge_status": status.value,
        "checks": [check.model_dump(mode="json") for check in checks],
        "notice": "Independent judge reuses the configured decision backend; it is not yet a different model family.",
        "observed_at": datetime.now(UTC).isoformat(),
    }
    if not store.complete_job(job["id"], owner, result):
        raise RuntimeError("lease lost before completion")
    return True


def build_judge_backend(config) -> DecisionBackend | None:  # noqa: ANN001 - AppConfig, avoids import cycle noise
    if config.mode == "fixture":
        return FixtureDecisions()
    if config.decision_transport == "openrouter_decisions" and config.openrouter_api_key:
        return OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
    if config.decision_transport == "typesafe_direct" and config.typesafe_api_key:
        return TypeSafeDirect(config.typesafe_api_key, config.decision_model)
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = load_config()
    contracts = load_contracts(config.contracts_dir)
    store = Store(config.database_url)
    store.migrate()
    judge_backend = build_judge_backend(config)
    owner = f"{socket.gethostname()}-{time.time_ns()}"
    while True:
        worked = run_once(store, contracts, judge_backend, owner, config.audit_max_attempts)
        if args.once:
            return
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    main()
