from __future__ import annotations

import hashlib
import json
import random
import time
from typing import Any

from app.config import AppConfig, load_profiles
from app.contracts import CheckResult, CheckStatus, GenerateRequest, GenerateResponse, PolicySnapshot, TaskContract
from app.persistence.store import BudgetExceeded, Store
from app.providers.base import DecisionBackend, GenerationProvider
from app.routing.policy import NoEligibleRoute, RoutingPolicy
from app.verification.verifier import ContractVerifier, aggregate


class AutopilotService:
    def __init__(self, config: AppConfig, contracts: dict[str, TaskContract], provider: GenerationProvider, verifier: ContractVerifier, store: Store) -> None:
        version, profiles = load_profiles(config.profiles_path, contracts, config.models)
        profile_hash = hashlib.sha256(config.profiles_path.read_bytes()).hexdigest()
        self.config, self.contracts, self.provider, self.verifier, self.store = config, contracts, provider, verifier, store
        self.router = RoutingPolicy(config.models, profiles)
        self.policy = PolicySnapshot(id=config.policy_id, version=version, profile_hash=profile_hash, mode=config.mode)

    def _rejected(self, request_id: str, checks: list[CheckResult], attempts: int, error: str, cost: int | None = 0) -> GenerateResponse:
        return GenerateResponse(request_id=request_id, status="rejected", contract_passed=False, attempts=attempts, checks=checks, cost_microusd=cost, cost_status="final" if cost is not None else "incomplete", policy=self.policy, error_code=error)

    async def execute(self, request: GenerateRequest, idempotency_key: str | None = None) -> GenerateResponse:
        if request.stream:
            return self._rejected("", [], 0, "unsupported_streaming")
        contract = self.contracts.get(request.contract_id)
        if not contract:
            return self._rejected("", [], 0, "unknown_contract")
        if len(request.source) > contract.max_source_chars:
            return self._rejected("", [], 0, "source_too_large")
        budget = request.max_budget_microusd or self.config.request_budget_microusd
        deadline_ms = request.deadline_ms or self.config.deadline_ms
        request_id, cached = self.store.create_request(request.model_dump(), contract.id, self.policy.id, idempotency_key)
        if cached:
            return GenerateResponse.model_validate(cached)
        try:
            route = self.router.select(contract, budget, deadline_ms)
        except NoEligibleRoute:
            result = self._rejected(request_id, [], 0, "no_eligible_route")
            self.store.finish(request_id, result.model_dump(mode="json"), 0, "final")
            return result
        started = time.monotonic(); total_cost: int | None = 0; all_checks: list[CheckResult] = []; attempts = 0
        aliases = [route.primary] + ([route.fallback] if route.fallback else [])
        for attempt, alias in enumerate(aliases[:self.config.max_generations], 1):
            remaining_s = (deadline_ms - int((time.monotonic()-started)*1000)) / 1000
            if remaining_s <= 0:
                break
            profile = next(p for p in self.router.profiles if p.contract_id == contract.id and p.model_alias == alias)
            try: reservation = self.store.reserve(request_id, "api", profile.expected_cost_microusd, budget)
            except BudgetExceeded: break
            attempts = attempt
            model = self.config.models[alias]
            call = await self.provider.generate(model=model.model_id, request=request.request, source=request.source, output_schema=contract.output_schema, max_tokens=self.config.max_output_tokens, timeout_s=remaining_s)
            self.store.record_call(request_id, reservation, "generation", attempt, call)
            if call.cost_microusd is None: total_cost = None
            elif total_cost is not None: total_cost += call.cost_microusd
            if call.status != "succeeded":
                all_checks = [CheckResult(check_id="generation", status=CheckStatus.ERROR, message=call.error_code)]
                continue
            tracker = _TrackedDecisionBackend(self.verifier.backend, self.store, request_id, budget,
                                              self.config.decision_reserve_microusd, attempt)
            verifier = ContractVerifier(tracker, self.verifier.fail_max, self.verifier.accept_min)
            all_checks = await verifier.verify(contract, request.source, call.content, remaining_s)
            if tracker.unknown_cost:
                total_cost = None
            elif total_cost is not None:
                total_cost += tracker.cost_microusd
            if aggregate(all_checks, contract.required_checks) == CheckStatus.PASS:
                result = GenerateResponse(request_id=request_id,status="accepted",output=call.content,contract_passed=True,attempts=attempt,final_model=call.resolved_model,checks=all_checks,cost_microusd=total_cost,cost_status="final" if total_cost is not None else "incomplete",policy=self.policy)
                selected = random.random() < self.config.audit_probability
                needs_human_review = selected and random.random() < self.config.audit_human_sample_probability
                audit = (self.config.audit_probability,"random",{"source":request.source,"output":call.content,"contract_id":contract.id},needs_human_review) if selected else None
                self.store.finish(request_id,result.model_dump(mode="json"),total_cost,result.cost_status,audit)
                return result
        result = self._rejected(request_id,all_checks,attempts,"contract_not_satisfied",total_cost)
        self.store.finish(request_id,result.model_dump(mode="json"),total_cost,result.cost_status)
        return result


class _TrackedDecisionBackend:
    def __init__(self, backend: DecisionBackend | None, store: Store, request_id: str,
                 budget_microusd: int, estimate_microusd: int, generation_attempt: int) -> None:
        self.backend, self.store, self.request_id = backend, store, request_id
        self.budget_microusd, self.estimate_microusd = budget_microusd, estimate_microusd
        self.generation_attempt = generation_attempt
        self.calls = 0
        self.cost_microusd = 0
        self.unknown_cost = False

    async def decide(self, *, state: Any, questions: dict[str, Any], timeout_s: float):
        from app.contracts import CallResult
        self.calls += 1
        if self.backend is None:
            return CallResult(status="failed", requested_model="unavailable", latency_ms=0, error_code="verifier_unavailable")
        try:
            reservation = self.store.reserve(self.request_id, "api-verifier", self.estimate_microusd, self.budget_microusd)
        except BudgetExceeded:
            return CallResult(status="failed", requested_model="budget", latency_ms=0, error_code="verification_budget_exceeded")
        result = await self.backend.decide(state=state, questions=questions, timeout_s=timeout_s)
        self.store.record_call(self.request_id, reservation, "verification", self.generation_attempt, result)
        if result.cost_microusd is None:
            self.unknown_cost = True
        else:
            self.cost_microusd += result.cost_microusd
        return result
