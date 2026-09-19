from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import UTC, datetime

from app.config import load_config
from app.persistence import Store


def run_once(store: Store, owner: str) -> bool:
    store.expire_payloads()
    job = store.claim_job(owner)
    if not job:
        return False
    payload = json.loads(job["payload_json"]) if job["payload_json"] else None
    result = ({"status": "skipped", "reason": "payload_expired"} if payload is None else
              {"status": "pending_human_or_independent_judge",
               "notice": "No audit result is fabricated in fixture mode.",
               "observed_at": datetime.now(UTC).isoformat()})
    if not store.complete_job(job["id"], owner, result):
        raise RuntimeError("lease lost before completion")
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = load_config()
    store = Store(config.database_url)
    store.migrate()
    owner = f"{socket.gethostname()}-{time.time_ns()}"
    while True:
        worked = run_once(store, owner)
        if args.once:
            return
        if not worked:
            time.sleep(2)


if __name__ == "__main__":
    main()

