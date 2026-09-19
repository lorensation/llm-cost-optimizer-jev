from concurrent.futures import ThreadPoolExecutor

from app.persistence import Store
from app.persistence.store import BudgetExceeded, IdempotencyConflict


def make_store(tmp_path) -> Store:
    store=Store(f"sqlite:///{tmp_path/'db.sqlite'}"); store.migrate(); return store


def test_idempotency_replays_and_conflicts(tmp_path) -> None:
    store=make_store(tmp_path)
    request_id,_=store.create_request({"a":1},"c","p","same")
    store.finish(request_id,{"request_id":request_id,"status":"rejected","contract_passed":False,"attempts":0,"checks":[],"cost_microusd":0,"cost_status":"final","policy":{"id":"p","version":"1","profile_hash":"x","mode":"fixture"},"error_code":"x"},0,"final")
    empty,cached=store.create_request({"a":1},"c","p","same")
    assert empty=="" and cached is not None
    try: store.create_request({"a":2},"c","p","same")
    except IdempotencyConflict: pass
    else: raise AssertionError("expected conflict")


def test_atomic_reservations_do_not_overspend(tmp_path) -> None:
    store=make_store(tmp_path); request_id,_=store.create_request({"a":1},"c","p",None)
    def reserve():
        try: store.reserve(request_id,"test",60,100); return True
        except BudgetExceeded: return False
    with ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(lambda _:reserve(),range(2)))
    assert sorted(results)==[False,True]

