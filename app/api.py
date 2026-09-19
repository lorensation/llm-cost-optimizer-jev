from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, FastAPI, Header, HTTPException

from app.config import load_config, load_contracts
from app.contracts import GenerateRequest, GenerateResponse
from app.persistence import Store
from app.persistence.store import IdempotencyConflict
from app.providers.fixture import FixtureDecisions, FixtureProvider
from app.providers.openrouter import OpenRouterDecisions, OpenRouterProvider
from app.providers.typesafe import TypeSafeDirect
from app.service import AutopilotService
from app.verification import ContractVerifier


@lru_cache
def get_service() -> AutopilotService:
    config = load_config()
    contracts = load_contracts(config.contracts_dir)
    store = Store(config.database_url)
    store.migrate()
    if config.mode == "fixture":
        provider, decisions = FixtureProvider(), FixtureDecisions()
    else:
        if not config.openrouter_api_key:
            raise RuntimeError("OpenRouter generation requires OPENROUTER_API_KEY")
        provider = OpenRouterProvider(config.openrouter_api_key)
        decisions = (OpenRouterDecisions(config.openrouter_api_key, config.decision_model)
                     if config.decision_transport == "openrouter_decisions"
                     else TypeSafeDirect(config.typesafe_api_key or "", config.decision_model))
    return AutopilotService(config, contracts, provider, ContractVerifier(decisions), store)


app = FastAPI(title="LLM Cost Autopilot", version="0.1.0")


def authenticate(authorization: str | None = Header(default=None)) -> None:
    service = get_service()
    if service.config.bind_host not in {"127.0.0.1", "localhost", "::1"} and not service.config.api_key:
        raise HTTPException(503, "API authentication must be configured off localhost")
    if service.config.api_key and authorization != f"Bearer {service.config.api_key}":
        raise HTTPException(401, "invalid API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/contracts", dependencies=[Depends(authenticate)])
def contracts() -> list[dict[str, object]]:
    return [{"id": c.id, "version": c.version, "family": c.family, "description": c.description}
            for c in get_service().contracts.values()]


@app.post("/v1/generate", response_model=GenerateResponse, dependencies=[Depends(authenticate)])
async def generate(payload: GenerateRequest, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key")) -> GenerateResponse:
    try:
        return await get_service().execute(payload, idempotency_key)
    except IdempotencyConflict as exc:
        raise HTTPException(409, "idempotency key reused with different request") from exc

