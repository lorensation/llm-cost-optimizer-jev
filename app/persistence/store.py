from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from app.contracts import CallResult


def utcnow() -> str:
    return datetime.now(UTC).isoformat()


class BudgetExceeded(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


class Store:
    def __init__(self, database_url: str, migrations_dir: str | Path = "migrations") -> None:
        if not database_url.startswith("sqlite:///"):
            raise ValueError("V1 supports sqlite:/// URLs only")
        self.path = Path(database_url.removeprefix("sqlite:///"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.migrations_dir = Path(migrations_dir)
        self._lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        for path in sorted(self.migrations_dir.glob("*.sql")):
            version = int(path.stem.split("_", 1)[0])
            with self.connect() as conn:
                if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
                    continue
                conn.executescript(path.read_text(encoding="utf-8"))
                conn.execute("INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)", (version, utcnow()))

    @contextmanager
    def immediate(self) -> Iterator[sqlite3.Connection]:
        with self._lock, self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.rollback()
                raise
            else:
                conn.commit()

    @staticmethod
    def canonical_hash(payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(body.encode()).hexdigest()

    def create_request(self, payload: dict[str, Any], contract_id: str, policy_id: str, idempotency_key: str | None) -> tuple[str, dict[str, Any] | None]:
        request_hash = self.canonical_hash(payload)
        with self.immediate() as conn:
            if idempotency_key:
                row = conn.execute("SELECT request_hash,result_json FROM requests WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if row:
                    if row["request_hash"] != request_hash:
                        raise IdempotencyConflict(idempotency_key)
                    return "", json.loads(row["result_json"]) if row["result_json"] else None
            request_id = str(uuid.uuid4())
            expires = (datetime.now(UTC) + timedelta(days=7)).isoformat()
            conn.execute(
                "INSERT INTO requests(id,idempotency_key,request_hash,contract_id,policy_id,status,request_json,created_at,expires_at) VALUES(?,?,?,?,?,'running',?,?,?)",
                (request_id, idempotency_key, request_hash, contract_id, policy_id, json.dumps(payload), utcnow(), expires),
            )
            return request_id, None

    def reserve(self, request_id: str, owner: str, amount_microusd: int, budget_microusd: int) -> str:
        with self.immediate() as conn:
            used = conn.execute("SELECT COALESCE(SUM(CASE WHEN status='final' THEN COALESCE(final_microusd,amount_microusd) ELSE amount_microusd END),0) n FROM reservations WHERE request_id=? AND status IN ('reserved','unknown','final')", (request_id,)).fetchone()["n"]
            if used + amount_microusd > budget_microusd:
                raise BudgetExceeded(f"{used}+{amount_microusd}>{budget_microusd}")
            reservation_id = str(uuid.uuid4())
            now = utcnow()
            conn.execute("INSERT INTO reservations VALUES(?,?,?,?,?,?,?,?)", (reservation_id, request_id, owner, amount_microusd, "reserved", None, now, now))
            return reservation_id

    def record_call(self, request_id: str, reservation_id: str, kind: str, attempt: int, result: CallResult) -> None:
        status = "unknown" if result.cost_microusd is None and result.status != "failed" else "final"
        with self.immediate() as conn:
            conn.execute(
                "INSERT INTO calls VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), request_id, reservation_id, kind, attempt, result.requested_model,
                 result.resolved_model, result.provider, result.status, result.input_tokens, result.output_tokens,
                 result.cost_microusd, result.latency_ms, result.error_code, json.dumps(result.raw), utcnow()),
            )
            conn.execute("UPDATE reservations SET status=?,final_microusd=?,updated_at=? WHERE id=?", (status, result.cost_microusd, utcnow(), reservation_id))

    def finish(self, request_id: str, result: dict[str, Any], cost_microusd: int | None, cost_status: str, audit: tuple[float, str, dict[str, Any], bool] | None = None) -> None:
        with self.immediate() as conn:
            conn.execute("UPDATE requests SET status=?,result_json=?,cost_microusd=?,cost_status=? WHERE id=?", (result["status"], json.dumps(result), cost_microusd, cost_status, request_id))
            if audit:
                probability, reason, payload, needs_human_review = audit
                now = utcnow()
                expiry = (datetime.now(UTC) + timedelta(days=7)).isoformat()
                conn.execute(
                    "INSERT INTO audit_jobs(id,request_id,status,inclusion_probability,selection_reason,payload_json,"
                    "payload_expires_at,lease_owner,lease_until,attempts,result_json,needs_human_review,human_review_json,"
                    "created_at,updated_at) VALUES(?,?, 'pending',?,?,?,?,NULL,NULL,0,NULL,?,NULL,?,?)",
                    (str(uuid.uuid4()), request_id, probability, reason, json.dumps(payload), expiry,
                     int(needs_human_review), now, now),
                )

    def claim_job(self, owner: str, lease_seconds: int = 60) -> sqlite3.Row | None:
        now = datetime.now(UTC)
        with self.immediate() as conn:
            row = conn.execute("SELECT * FROM audit_jobs WHERE status='pending' OR (status='leased' AND lease_until<?) ORDER BY created_at LIMIT 1", (now.isoformat(),)).fetchone()
            if not row:
                return None
            lease_until = (now + timedelta(seconds=lease_seconds)).isoformat()
            conn.execute("UPDATE audit_jobs SET status='leased',lease_owner=?,lease_until=?,attempts=attempts+1,updated_at=? WHERE id=?", (owner, lease_until, now.isoformat(), row["id"]))
            return conn.execute("SELECT * FROM audit_jobs WHERE id=?", (row["id"],)).fetchone()

    def complete_job(self, job_id: str, owner: str, result: dict[str, Any]) -> bool:
        with self.immediate() as conn:
            changed = conn.execute("UPDATE audit_jobs SET status='complete',result_json=?,updated_at=? WHERE id=? AND status='leased' AND lease_owner=? AND lease_until>=?", (json.dumps(result), utcnow(), job_id, owner, utcnow())).rowcount
            return changed == 1

    def heartbeat_job(self, job_id: str, owner: str, lease_seconds: int) -> bool:
        """Extends an in-progress lease so a slow judge call is not reclaimed by another worker mid-flight."""
        with self.immediate() as conn:
            lease_until = (datetime.now(UTC) + timedelta(seconds=lease_seconds)).isoformat()
            changed = conn.execute(
                "UPDATE audit_jobs SET lease_until=?,updated_at=? WHERE id=? AND status='leased' AND lease_owner=? AND lease_until>=?",
                (lease_until, utcnow(), job_id, owner, utcnow()),
            ).rowcount
            return changed == 1

    def fail_job(self, job_id: str, owner: str, max_attempts: int, error: str) -> str:
        """Distinguishes a recoverable failure (released back to 'pending' for retry) from an exhausted one
        (terminal 'exhausted' status), per PLAN section 5. Never silently marks a failure as 'pass'."""
        with self.immediate() as conn:
            row = conn.execute(
                "SELECT attempts FROM audit_jobs WHERE id=? AND status='leased' AND lease_owner=?", (job_id, owner)
            ).fetchone()
            if not row:
                raise RuntimeError("lease lost before failure could be recorded")
            if row["attempts"] >= max_attempts:
                conn.execute(
                    "UPDATE audit_jobs SET status='exhausted',result_json=?,updated_at=? WHERE id=?",
                    (json.dumps({"status": "exhausted", "error": error, "attempts": row["attempts"]}), utcnow(), job_id),
                )
                return "exhausted"
            conn.execute(
                "UPDATE audit_jobs SET status='pending',lease_owner=NULL,lease_until=NULL,updated_at=? WHERE id=?",
                (utcnow(), job_id),
            )
            return "pending"

    def record_human_review(self, job_id: str, reviewer: str, verdict: dict[str, Any]) -> bool:
        with self.immediate() as conn:
            changed = conn.execute(
                "UPDATE audit_jobs SET human_review_json=?,updated_at=? WHERE id=? AND needs_human_review=1",
                (json.dumps({"reviewer": reviewer, "verdict": verdict, "recorded_at": utcnow()}), utcnow(), job_id),
            ).rowcount
            return changed == 1

    def expire_payloads(self) -> int:
        with self.immediate() as conn:
            return conn.execute("UPDATE audit_jobs SET payload_json=NULL,status=CASE WHEN status='pending' THEN 'skipped' ELSE status END,updated_at=? WHERE payload_expires_at<? AND payload_json IS NOT NULL", (utcnow(), utcnow())).rowcount
