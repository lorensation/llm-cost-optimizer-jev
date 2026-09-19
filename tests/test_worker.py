from app.persistence import Store


def test_expired_owner_cannot_complete_reclaimed_job(tmp_path) -> None:
    store=Store(f"sqlite:///{tmp_path/'db.sqlite'}"); store.migrate()
    request_id,_=store.create_request({"a":1},"c","p",None)
    store.finish(request_id,{"status":"accepted"},0,"final",(1.0,"random",{"source":"x"}))
    first=store.claim_job("owner-a",lease_seconds=-1)
    second=store.claim_job("owner-b",lease_seconds=60)
    assert first and second and first["id"]==second["id"]
    assert not store.complete_job(first["id"],"owner-a",{"status":"pass"})
    assert store.complete_job(second["id"],"owner-b",{"status":"pending_human"})
