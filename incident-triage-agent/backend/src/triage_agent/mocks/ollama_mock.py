"""Mock ChatOllama — returns deterministic JSON responses without a real Ollama server.

Detects which node is calling by inspecting the system message content, then
picks a scenario-appropriate response based on keywords in the user message.
"""
import json
from typing import Any, Iterator

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

# ---------------------------------------------------------------------------
# Canned responses keyed by scenario
# ---------------------------------------------------------------------------

_ROOT_CAUSE_RESPONSES = {
    "oom": {
        "root_cause": "Memory limit exceeded (OOMKilled) — JVM heap grew beyond the 512Mi container limit due to a cache leak in the session manager",
        "confidence": 0.92,
    },
    "crash": {
        "root_cause": "CrashLoopBackOff caused by missing DATABASE_URL environment variable — pod fails liveness probe within 2s of startup",
        "confidence": 0.88,
    },
    "latency": {
        "root_cause": "Connection pool exhausted — upstream recommendation-service holding 200 idle connections against a pool limit of 50, causing p99 to spike to 3200ms",
        "confidence": 0.85,
    },
}

_REMEDIATION_RESPONSES = {
    "oom": {
        "action": "increase_memory_limit",
        "target": "payment-service",
        "params": {"memory_limit": "1Gi", "namespace": "production"},
        "risk_level": "low",
        "rationale": "Doubling the memory limit gives headroom while the cache leak is patched; no rolling restart required",
    },
    "crash": {
        "action": "rollback",
        "target": "auth-service",
        "params": {"revision": "previous", "namespace": "production"},
        "risk_level": "medium",
        "rationale": "Roll back to the last known-good deployment that had DATABASE_URL set correctly in the secret",
    },
    "latency": {
        "action": "scale_up",
        "target": "recommendation-service",
        "params": {"replicas": 6, "namespace": "staging"},
        "risk_level": "low",
        "rationale": "Adding replicas distributes connection load and brings p99 back within the 500ms SLO while the pool limit is tuned",
    },
}

_VERIFICATION_RESPONSES = {
    "oom": {
        "resolved": True,
        "explanation": "Memory usage stabilised at 480Mi — no new OOMKill events in the last 5 minutes, pod restart count unchanged",
    },
    "crash": {
        "resolved": True,
        "explanation": "auth-service liveness probe returning 200, restart count reset to 0 after rollback",
    },
    "latency": {
        "resolved": True,
        "explanation": "p99 latency dropped to 320ms after scale-up — circuit breaker CLOSED, connection pool utilisation at 60%",
    },
}


def _detect_scenario(combined: str) -> str:
    """Pick a scenario key from message content keywords."""
    low = combined.lower()
    if "oom" in low or "memory" in low or "payment" in low:
        return "oom"
    if "crash" in low or "liveness" in low or "auth" in low or "database" in low:
        return "crash"
    if "latency" in low or "recommendation" in low or "pool" in low or "p99" in low:
        return "latency"
    return "oom"  # default


def _pick_response(messages: list[BaseMessage]) -> dict[str, Any]:
    combined = " ".join(
        m.content if isinstance(m.content, str) else json.dumps(m.content)
        for m in messages
    )
    scenario = _detect_scenario(combined)

    if "root_cause" in combined and "confidence" in combined:
        return _ROOT_CAUSE_RESPONSES[scenario]
    if "action" in combined and "risk_level" in combined:
        return _REMEDIATION_RESPONSES[scenario]
    if "resolved" in combined and "explanation" in combined:
        return _VERIFICATION_RESPONSES[scenario]
    return {"result": "ok"}


class MockChatOllama(BaseChatModel):
    """Deterministic stand-in for ChatOllama used during local development and testing."""

    @property
    def _llm_type(self) -> str:
        return "mock"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        payload = _pick_response(messages)
        message = AIMessage(content=json.dumps(payload))
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        import asyncio
        await asyncio.sleep(1.5)
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
