from copy import deepcopy

import pytest

from app.config import load_config, load_contracts
from app.contracts import CallResult, GenerateRequest
from app.persistence import Store
from app.providers.fixture import FixtureDecisions, FixtureProvider
from app.service import AutopilotService
from app.verification import ContractVerifier


def service(tmp_path, provider=None, decisions=None):
    config=load_config("config/default.yaml").model_copy(update={"database_url":f"sqlite:///{tmp_path/'db.sqlite'}","audit_probability":0})
    store=Store(config.database_url); store.migrate()
    return AutopilotService(config,load_contracts(config.contracts_dir),provider or FixtureProvider(),ContractVerifier(decisions or FixtureDecisions()),store)


@pytest.mark.asyncio
async def test_valid_first_attempt_and_idempotent_replay(tmp_path) -> None:
    svc=service(tmp_path); request=GenerateRequest(contract_id="extract_invoice_v1",request="extract",source="Invoice F-104. Total: 120 EUR.")
    first=await svc.execute(request,"k1"); second=await svc.execute(request,"k1")
    assert first.contract_passed and first.attempts==1 and second.request_id==first.request_id


class SequenceProvider:
    def __init__(self, contents): self.contents=list(contents); self.calls=0
    async def generate(self, **kwargs):
        content=self.contents[self.calls]; self.calls+=1
        return CallResult(status="succeeded",content=content,requested_model=kwargs["model"],resolved_model=kwargs["model"],provider="fixture",cost_microusd=0,latency_ms=1)


@pytest.mark.asyncio
async def test_invalid_cheap_then_valid_fallback_uses_exactly_two_attempts(tmp_path) -> None:
    provider=SequenceProvider([{"invoice_number":123,"total":"bad"},{"invoice_number":"F-104","total":120}])
    result=await service(tmp_path,provider).execute(GenerateRequest(contract_id="extract_invoice_v1",request="extract",source="Invoice F-104. Total: 120 EUR."))
    assert result.contract_passed and result.attempts==2 and provider.calls==2


@pytest.mark.asyncio
async def test_two_invalid_outputs_are_rejected_without_third_attempt(tmp_path) -> None:
    provider=SequenceProvider([{},{}]); result=await service(tmp_path,provider).execute(GenerateRequest(contract_id="extract_invoice_v1",request="extract",source="Invoice F-104. Total: 120 EUR."))
    assert not result.contract_passed and provider.calls==2


@pytest.mark.asyncio
async def test_missing_semantic_verifier_never_passes(tmp_path) -> None:
    svc=service(tmp_path,decisions=None); svc.verifier=ContractVerifier(None)
    result=await svc.execute(GenerateRequest(contract_id="classify_ticket_v1",request="classify",source="My payment failed"))
    assert not result.contract_passed


@pytest.mark.asyncio
async def test_budget_exhaustion_rejects_before_generation(tmp_path) -> None:
    provider=SequenceProvider([]); svc=service(tmp_path,provider)
    result=await svc.execute(GenerateRequest(contract_id="extract_invoice_v1",request="extract",source="Invoice F-104. Total: 120 EUR.",max_budget_microusd=1))
    assert result.error_code=="no_eligible_route" and provider.calls==0

