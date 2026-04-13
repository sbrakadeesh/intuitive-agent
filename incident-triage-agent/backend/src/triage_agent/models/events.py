"""Pydantic v2 models for WebSocket events and operator approval messages."""
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


HumanDecision = Literal["approved", "rejected", "edited", "abort", "escalate", "close"]


class WSEvent(BaseModel):
    """A server-sent WebSocket event emitted during a triage run."""

    event_type: Literal[
        "step_start",
        "step_complete",
        "interrupt",
        "tool_call",
        "tool_result",
        "complete",
        "error",
        "status_update",
    ]
    incident_id: str
    step_name: Optional[str] = None
    data: Optional[Any] = None
    timestamp: str = Field(default_factory=_utc_now)


class ApprovalMessage(BaseModel):
    """Operator decision message received over WebSocket at a HITL interrupt."""

    decision: HumanDecision
    operator_edit: Optional[dict[str, Any]] = None
    operator_notes: Optional[str] = None
