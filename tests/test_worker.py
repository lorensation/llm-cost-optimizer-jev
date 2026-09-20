from pathlib import Path

from app.config import load_contracts
from app.contracts import CallResult
from app.persistence import Store
from app.providers.fixture import FixtureDecisions
from app.worker import run_once

CONTRACTS = load_contracts(Path("contracts"))


class RaisingBackend:
    async def decide(self, *, state, questions, timeout_s):
        raise RuntimeError("judge backend unavailable")


def make_store(tmp_path) -> Store:
    store = Store(f"sqlite:///{tmp_path/'db.sqlite'}")
    store.migrate()
    return store


def finish_with_audit(store: Store, payload: dict, needs_human_review: bool = False) -> str:
    request_id, _ = store.create_request({"a": 1}, "c", "p", None)
    store.finish(request_id, {"status": "accepted"}, 0, "final", (1.0, "random", payload, needs_human_review))
    return request_id


def test_expired_owner_cannot_complete_reclaimed_job(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "x", "output": {}, "contract_id": "x"})
    first = store.claim_job("owner-a", lease_seconds=-1)
    second = store.claim_job("owner-b", lease_seconds=60)
    assert first and second and first["id"] == second["id"]
    assert not store.complete_job(first["id"], "owner-a", {"status": "pass"})
    assert store.complete_job(second["id"], "owner-b", {"status": "pending_human"})


def test_human_review_job_is_parked_without_invoking_the_judge(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "x", "output": {"label": "billing"}, "contract_id": "classify_ticket_v1"},
                       needs_human_review=True)
    worked = run_once(store, CONTRACTS, RaisingBackend(), "worker-1", max_attempts=3)
    assert worked is True
    row = store.connect().execute("SELECT status,result_json FROM audit_jobs").fetchone()
    assert row["status"] == "complete"
    assert '"pending_human_review"' in row["result_json"]
    assert store.record_human_review(store.connect().execute("SELECT id FROM audit_jobs").fetchone()["id"],
                                      "reviewer-1", {"verdict": "pass"})


def test_judge_reviews_and_completes_the_job(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "Ticket about a broken login page.",
                               "output": {"label": "technical"}, "contract_id": "classify_ticket_v1"})
    worked = run_once(store, CONTRACTS, FixtureDecisions(), "worker-1", max_attempts=3)
    assert worked is True
    row = store.connect().execute("SELECT status,result_json FROM audit_jobs").fetchone()
    assert row["status"] == "complete"
    assert '"judge_reviewed"' in row["result_json"]
    assert '"pass"' in row["result_json"]


def test_unknown_contract_is_a_recoverable_failure_until_attempts_are_exhausted(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "x", "output": {}, "contract_id": "does_not_exist"})
    run_once(store, CONTRACTS, FixtureDecisions(), "worker-1", max_attempts=1)
    row = store.connect().execute("SELECT status,attempts,result_json FROM audit_jobs").fetchone()
    assert row["status"] == "exhausted"
    assert row["attempts"] == 1
    assert '"unknown_contract"' in row["result_json"]


def test_judge_backend_failure_is_released_for_retry_then_exhausted(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "Ticket about a broken login page.",
                               "output": {"label": "technical"}, "contract_id": "classify_ticket_v1"})
    run_once(store, CONTRACTS, RaisingBackend(), "worker-1", max_attempts=2)
    first = store.connect().execute("SELECT status,attempts FROM audit_jobs").fetchone()
    assert first["status"] == "pending" and first["attempts"] == 1

    run_once(store, CONTRACTS, RaisingBackend(), "worker-1", max_attempts=2)
    second = store.connect().execute("SELECT status,attempts,result_json FROM audit_jobs").fetchone()
    assert second["status"] == "exhausted" and second["attempts"] == 2
    assert '"RuntimeError"' in second["result_json"]


def test_heartbeat_extends_a_lease_the_owner_still_holds(tmp_path) -> None:
    store = make_store(tmp_path)
    finish_with_audit(store, {"source": "x", "output": {}, "contract_id": "x"})
    job = store.claim_job("owner-1", lease_seconds=5)
    assert store.heartbeat_job(job["id"], "owner-1", lease_seconds=120)
    assert not store.heartbeat_job(job["id"], "owner-2", lease_seconds=120)
    later = store.claim_job("owner-2", lease_seconds=60)
    assert later is None  # the heartbeat kept the lease alive for owner-1
