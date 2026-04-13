"""Mock ChatOllama — returns deterministic JSON responses without a real Ollama server.

Detects which node is calling by inspecting the system message content and returns
a response that matches the expected JSON schema for that node.
"""
import json
from typing import Any, Iterator

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


_RESPONSE_ROOT_CAUSE = {
    "root_cause": "Memory limit exceeded (OOMKilled), restarted 5 times",
    "confidence": 0.92,
}

_RESPONSE_REMEDIATION = {
    "action": "restart_pod",
    "target": "payment-service",
    "params": {"namespace": "production"},
    "risk_level": "low",
    "rationale": "Restart clears heap state",
}

_RESPONSE_VERIFICATION = {
    "resolved": True,
    "explanation": "Memory back to baseline, no new OOMKill events",
}

_RESPONSE_DEFAULT = {"result": "ok"}


def _pick_response(messages: list[BaseMessage]) -> dict[str, Any]:
    """Select the canned response that matches the calling node.

    Concatenates all message content into a single string and checks for
    keyword pairs that identify which node is invoking the LLM.

    Args:
        messages: The message list passed to the model.

    Returns:
        The canned response dict for the detected node, or the default dict.
    """
    combined = " ".join(
        m.content if isinstance(m.content, str) else json.dumps(m.content)
        for m in messages
    )

    if "root_cause" in combined and "confidence" in combined:
        return _RESPONSE_ROOT_CAUSE
    if "action" in combined and "risk_level" in combined:
        return _RESPONSE_REMEDIATION
    if "resolved" in combined and "explanation" in combined:
        return _RESPONSE_VERIFICATION
    return _RESPONSE_DEFAULT


class MockChatOllama(BaseChatModel):
    """Deterministic stand-in for ChatOllama used during local development and testing.

    Inspects the content of the messages it receives to decide which canned
    JSON payload to return, so the rest of the graph can exercise its full
    parsing and routing logic without a running Ollama server.
    """

    @property
    def _llm_type(self) -> str:
        """Identifier returned by LangChain when introspecting the model."""
        return "mock"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Return a canned JSON response synchronously.

        Args:
            messages: The conversation messages forwarded by the node.
            stop: Ignored — included for interface compatibility.
            run_manager: Ignored — included for interface compatibility.
            **kwargs: Absorbed for interface compatibility.

        Returns:
            A ``ChatResult`` wrapping a single ``AIMessage`` whose content is
            a JSON-serialised string matching the detected node's schema.
        """
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
        """Return a canned JSON response asynchronously.

        Delegates directly to ``_generate`` — no I/O to await.

        Args:
            messages: The conversation messages forwarded by the node.
            stop: Ignored — included for interface compatibility.
            run_manager: Ignored — included for interface compatibility.
            **kwargs: Absorbed for interface compatibility.

        Returns:
            A ``ChatResult`` wrapping a single ``AIMessage`` whose content is
            a JSON-serialised string matching the detected node's schema.
        """
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
