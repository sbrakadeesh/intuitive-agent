"""Pydantic v2 models for incident triage requests and records."""
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertPayload(BaseModel):
    """Normalized alert payload ingested at the start of a triage run."""

    service: str
    namespace: str
    pod_name: Optional[str] = None
    severity: Literal["critical", "high", "medium", "low", "warning"]
    title: str
    description: str
    labels: dict[str, str] = Field(default_factory=dict)
    started_at: Optional[str] = None


class IncidentRecord(BaseModel):
    """Persisted record of a single triage incident and its current state."""

    incident_id: str = Field(default_factory=lambda: str(uuid4()))
    alert: AlertPayload
    status: str = "pending"
    current_step: Optional[str] = None
    root_cause: Optional[str] = None
    root_cause_confidence: Optional[float] = None
    proposed_remediation: Optional[dict[str, Any]] = None
    execution_result: Optional[dict[str, Any]] = None
    verification_result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)


class CreateIncidentRequest(BaseModel):
    """Request body for creating a new triage incident."""

    alert: AlertPayload


class HumanDecisionRequest(BaseModel):
    """Operator decision submitted at a human-in-the-loop interrupt."""

    decision: Literal["approved", "rejected", "edited", "abort", "escalate", "close"]
    operator_edit: Optional[dict[str, Any]] = None
    operator_notes: Optional[str] = None
