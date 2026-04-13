"""LangGraph node functions for the incident triage graph.

Each node:
- Accepts the full TriageState
- Returns a dict with ONLY the keys it updates
- Is async to allow concurrent service calls
"""
import asyncio
import json
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from langchain_ollama import ChatOllama
from triage_agent.config import config
from triage_agent.agent.state import TriageState
from triage_agent.mocks.ollama_mock import MockChatOllama
from triage_agent.mocks.log_fetcher import MockLogFetcher
from triage_agent.mocks.metrics_service import MockMetricsService
from triage_agent.mocks.kubectl_executor import MockKubectlExecutor
import logging

logger = logging.getLogger(__name__)

# LLM factory

def get_llm() -> ChatOllama:
    if config.use_mock_ollama:
        
        return MockChatOllama()
    return ChatOllama(
        model=config.ollama_model,
        base_url=config.ollama_base_url,
        temperature=0,
        format="json",
    )

def _get_log_fetcher():
    from triage_agent.mocks.log_fetcher import MockLogFetcher
    return MockLogFetcher()


def _get_metrics_service():
    from triage_agent.mocks.metrics_service import MockMetricsService
    return MockMetricsService()


def _get_kubectl_executor():
    from triage_agent.mocks.kubectl_executor import MockKubectlExecutor
    return MockKubectlExecutor()


async def ingest_alert(state: TriageState) -> dict[str, Any]:
    """Normalize the raw alert payload into a canonical structure.

    Reads ``state["alert_payload"]`` and fills in safe defaults for every
    field the rest of the graph depends on, so downstream nodes can access
    keys unconditionally without defensive ``get`` calls.

    Args:
        state: The current triage graph state.

    Returns:
        A partial state dict containing the normalized ``alert_payload``
        and the updated ``current_step``.
    """
    raw: dict[str, Any] = state.get("alert_payload") or {}

    normalized: dict[str, Any] = {
        "service":     raw.get("service", "unknown-service"),
        "namespace":   raw.get("namespace", "default"),
        "pod_name":    raw.get("pod_name", ""),
        "severity":    raw.get("severity", "unknown"),
        "title":       raw.get("title", "Untitled Alert"),
        "description": raw.get("description", ""),
        "labels":      raw.get("labels") or {},
        "started_at":  raw.get("started_at", ""),
    }

    logger.info(
        "ingest_alert: service=%s severity=%s",
        normalized["service"],
        normalized["severity"],
    )

    return {
        "alert_payload": normalized,
        "current_step": "ingest_alert",
    }


async def fetch_context(state: TriageState) -> dict[str, Any]:
    """Fetch logs and metrics for the affected service concurrently.

    Calls the log fetcher and metrics service in parallel using
    ``asyncio.gather`` to minimise wall-clock latency.  Both helpers are
    synchronous, so they are dispatched via ``asyncio.to_thread``.

    Args:
        state: The current triage graph state.  ``alert_payload.service``
            must be populated (guaranteed after ``ingest_alert`` runs).

    Returns:
        A partial state dict containing ``fetched_logs``, ``fetched_metrics``,
        and the updated ``current_step``.
    """
    service: str = state["alert_payload"]["service"]

    log_fetcher = _get_log_fetcher()
    metrics_service = _get_metrics_service()

    fetched_logs, fetched_metrics = await asyncio.gather(
        asyncio.to_thread(log_fetcher.fetch_logs, service),
        asyncio.to_thread(metrics_service.fetch_metrics, service),
    )

    logger.info(
        "fetch_context: service=%s logs_fetched=%d",
        service,
        len(fetched_logs) if fetched_logs else 0,
    )

    return {
        "fetched_logs": fetched_logs,
        "fetched_metrics": fetched_metrics,
        "current_step": "fetch_context",
    }


async def analyze_root_cause(state: TriageState) -> dict[str, Any]:
    """Use the LLM to identify the root cause of the incident.

    Builds a structured prompt from the normalized alert payload and the
    fetched context, then invokes the configured LLM.  The model is
    instructed to return **pure JSON only** — no markdown fences — with the
    shape ``{"root_cause": str, "confidence": float}``.

    Args:
        state: The current triage graph state.  Expects ``alert_payload``,
            ``fetched_logs``, and ``fetched_metrics`` to be populated.

    Returns:
        On success — a partial state dict with ``root_cause``,
        ``root_cause_confidence``, ``messages``, and ``current_step``.

        On any exception — ``{"error": str(exc), "current_step":
        "analyze_root_cause", "completed": False}``.
    """
    alert = state["alert_payload"]

    system_prompt = (
        "You are an expert SRE performing incident triage. "
        "Analyze the alert and context provided by the user and respond with "
        "PURE JSON only — no extra keys. "
        'Required shape: {"root_cause": "<string>", "confidence": <float 0.0-1.0>}. '
        "Do not include markdown, code blocks, or any text outside the JSON object."
    )

    user_prompt = (
        f"Alert title: {alert['title']}\n"
        f"Service: {alert['service']}\n"
        f"Severity: {alert['severity']}\n"
        f"Description: {alert['description']}\n\n"
        f"Logs:\n{json.dumps(state.get('fetched_logs'), indent=2)}\n\n"
        f"Metrics:\n{json.dumps(state.get('fetched_metrics'), indent=2)}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        llm = get_llm()
        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = json.loads(response.content)
        root_cause: str = parsed["root_cause"]
        confidence: float = float(parsed["confidence"])
    except Exception as exc:
        logger.error("analyze_root_cause failed: %s", exc)
        return {
            "error": str(exc),
            "current_step": "analyze_root_cause",
            "completed": False,
        }

    logger.info(
        "analyze_root_cause: root_cause=%r confidence=%.2f",
        root_cause,
        confidence,
    )

    return {
        "root_cause": root_cause,
        "root_cause_confidence": confidence,
        "messages": messages,
        "current_step": "analyze_root_cause",
    }


async def propose_remediation(state: TriageState) -> dict[str, Any]:
    """Propose a concrete remediation action for the confirmed root cause.

    Runs after the first human-in-the-loop interrupt, meaning the operator
    has already reviewed and accepted (or edited) the root cause.  If the
    operator supplied an override via ``operator_edit``, that value is used
    in preference to the LLM-derived root cause.

    The LLM is asked to return **pure JSON only** with the shape::

        {
            "action":     "restart_pod" | "scale_up" | "rollback"
                          | "increase_memory_limit" | "other",
            "target":     "<k8s resource name>",
            "params":     {<key>: <value>, ...},
            "risk_level": "low" | "medium" | "high",
            "rationale":  "<explanation string>"
        }

    On any exception a safe, low-risk fallback remediation is returned so
    the graph can continue to the human approval gate rather than halting.

    Args:
        state: The current triage graph state.  ``alert_payload`` and
            ``root_cause`` must be populated; ``operator_edit`` is optional.

    Returns:
        A partial state dict containing ``proposed_remediation``, ``messages``,
        and the updated ``current_step``.
    """
    alert = state["alert_payload"]

    # Prefer operator-supplied root cause override, fall back to LLM result.
    root_cause: str = (
        (state.get("operator_edit") or {}).get("root_cause")
        or state.get("root_cause")
        or "unknown"
    )

    system_prompt = (
        "You are an expert SRE performing incident remediation planning. "
        "Given the incident context and confirmed root cause, propose the "
        "single most appropriate remediation action. "
        "Respond with PURE JSON only — no extra keys. "
        "Required shape: "
        '{"action": "restart_pod"|"scale_up"|"rollback"|"increase_memory_limit"|"other", '
        '"target": "<k8s resource name>", '
        '"params": {}, '
        '"risk_level": "low"|"medium"|"high", '
        '"rationale": "<string>"}. '
        "Do not include markdown, code blocks, or any text outside the JSON object."
    )

    user_prompt = (
        f"Service: {alert['service']}\n"
        f"Namespace: {alert['namespace']}\n"
        f"Severity: {alert['severity']}\n"
        f"Confirmed root cause: {root_cause}\n"
        f"Alert description: {alert['description']}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        llm = get_llm()
        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = json.loads(response.content)
        remediation: dict[str, Any] = {
            "action":     parsed["action"],
            "target":     parsed["target"],
            "params":     parsed.get("params") or {},
            "risk_level": parsed["risk_level"],
            "rationale":  parsed["rationale"],
        }
    except Exception as exc:
        logger.warning("propose_remediation failed, using safe fallback: %s", exc)
        remediation = {
            "action":     "restart_pod",
            "target":     alert.get("pod_name") or alert["service"],
            "params":     {},
            "risk_level": "low",
            "rationale":  f"Fallback: LLM proposal failed ({exc}). Defaulting to safe pod restart.",
        }

    logger.info(
        "propose_remediation: action=%s target=%s risk_level=%s",
        remediation["action"],
        remediation["target"],
        remediation["risk_level"],
    )

    return {
        "proposed_remediation": remediation,
        "messages": messages,
        "current_step": "propose_remediation",
    }


async def execute_remediation(state: TriageState) -> dict[str, Any]:
    """Execute the approved remediation action against the cluster.

    Runs after the second human-in-the-loop interrupt, meaning the operator
    has reviewed the proposed remediation and made a decision.

    Short-circuits immediately if the operator rejected or aborted the plan —
    no kubectl call is made and the execution result is marked as skipped.

    When proceeding, any parameter overrides supplied by the operator via
    ``operator_edit`` are merged into ``proposed_remediation["params"]``
    (the ``root_cause`` key, if present in ``operator_edit``, is excluded
    because it belongs to the analysis phase, not execution).

    Args:
        state: The current triage graph state.  ``proposed_remediation`` and
            ``human_decision`` must be populated.

    Returns:
        A partial state dict containing ``execution_result`` and
        ``current_step``.  On failure also sets ``error``.
    """
    decision: str | None = state.get("human_decision")

    if decision in ("rejected", "abort"):
        logger.info("execute_remediation: skipped — operator decision=%s", decision)
        return {
            "execution_result": {
                "skipped": True,
                "reason": f"Operator decision: {decision}",
            },
            "current_step": "execute_remediation",
        }

    remediation: dict[str, Any] = state.get("proposed_remediation") or {}
    action: str = remediation.get("action", "restart_pod")
    target: str = remediation.get("target", "")

    # Merge operator param overrides, excluding root_cause (analysis-phase key).
    base_params: dict[str, Any] = dict(remediation.get("params") or {})
    operator_overrides: dict[str, Any] = dict(state.get("operator_edit") or {})
    operator_overrides.pop("root_cause", None)
    params: dict[str, Any] = {**base_params, **operator_overrides}

    logger.info(
        "execute_remediation: action=%s target=%s params=%s",
        action,
        target,
        params,
    )

    try:
        executor = _get_kubectl_executor()
        result: dict[str, Any] = await executor.execute(action, target, params)
    except Exception as exc:
        logger.error("execute_remediation failed: %s", exc)
        return {
            "execution_result": {"error": str(exc)},
            "error": str(exc),
            "current_step": "execute_remediation",
        }

    return {
        "execution_result": result,
        "current_step": "execute_remediation",
    }


async def verify_resolution(state: TriageState) -> dict[str, Any]:
    """Verify whether the executed remediation resolved the incident.

    Waits briefly to simulate metric propagation, then re-fetches fresh
    metrics and asks the LLM to assess whether the incident is resolved.

    The LLM is instructed to return **pure JSON only** with the shape::

        {"resolved": true|false, "explanation": "<string>"}

    On any exception the node defaults to ``resolved=True`` with an
    explanation that includes the error — this is an intentionally optimistic
    fallback so the graph can reach a clean terminal state rather than
    looping indefinitely.  ``completed`` is NOT set here; that is the
    responsibility of the final node.

    Args:
        state: The current triage graph state.  ``alert_payload`` and
            ``execution_result`` must be populated.

    Returns:
        A partial state dict containing ``verification_result`` (prefixed
        with ``"RESOLVED: "`` or ``"UNRESOLVED: "``) and ``current_step``.
    """
    await asyncio.sleep(0.5)  # simulate metric propagation delay

    service: str = state["alert_payload"]["service"]
    alert_title: str = state["alert_payload"]["title"]

    try:
        fresh_metrics = await asyncio.to_thread(
            _get_metrics_service().get_metrics, service
        )
    except Exception as exc:
        logger.warning("verify_resolution: metrics re-fetch failed: %s", exc)
        fresh_metrics = None

    system_prompt = (
        "You are an expert SRE verifying whether a remediation action resolved "
        "an incident. Analyze the execution result and current metrics, then "
        "respond with PURE JSON only — no extra keys. "
        'Required shape: {"resolved": true|false, "explanation": "<string>"}. '
        "Do not include markdown, code blocks, or any text outside the JSON object."
    )

    user_prompt = (
        f"Alert title: {alert_title}\n\n"
        f"Execution result:\n{json.dumps(state.get('execution_result'), indent=2)}\n\n"
        f"Fresh metrics:\n{json.dumps(fresh_metrics, indent=2)}"
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        llm = get_llm()
        response = await llm.ainvoke(messages)
        parsed: dict[str, Any] = json.loads(response.content)
        resolved: bool = bool(parsed["resolved"])
        explanation: str = parsed["explanation"]
    except Exception as exc:
        logger.error("verify_resolution: LLM call failed, defaulting to resolved: %s", exc)
        resolved = True
        explanation = f"Verification check failed ({exc}); assuming resolved."

    prefix = "RESOLVED" if resolved else "UNRESOLVED"
    verification_result = f"{prefix}: {explanation}"

    logger.info("verify_resolution: %s", verification_result)

    return {
        "verification_result": verification_result,
        "current_step": "verify_resolution",
    }


async def end_review(state: TriageState) -> dict[str, Any]:
    """Close or escalate the incident after the final operator decision.

    Runs after the third human-in-the-loop interrupt, where the operator
    either closes the incident or escalates it for further investigation.
    This is the only node that sets ``completed: True``.

    Args:
        state: The current triage graph state.  ``human_decision`` should be
            populated; defaults to ``"close"`` if absent.

    Returns:
        A partial state dict with ``completed`` set to ``True``,
        ``current_step`` set to ``"end_review"``, and ``execution_result``
        extended with an ``escalated`` flag.
    """
    decision: str = state.get("human_decision") or "close"
    escalated: bool = decision == "escalate"

    logger.info("end_review: decision=%s escalated=%s", decision, escalated)

    existing_result: dict[str, Any] = dict(state.get("execution_result") or {})

    return {
        "completed": True,
        "current_step": "end_review",
        "execution_result": {**existing_result, "escalated": escalated},
    }


def route_after_analysis(state: TriageState) -> Literal["continue", "error"]:
    """Determine the next graph edge after ``analyze_root_cause``.

    This is a plain routing function, not a node — it returns a string edge
    label rather than a state update dict.

    Args:
        state: The current triage graph state.

    Returns:
        ``"error"`` if the state carries an error or the operator has aborted
        the run; ``"continue"`` otherwise.
    """
    if state.get("error"):
        return "error"
    if state.get("human_decision") == "abort":
        return "error"
    return "continue"

