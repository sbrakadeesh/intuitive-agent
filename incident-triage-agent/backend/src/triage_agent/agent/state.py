from typing import Annotated, Any, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph import add_messages

class TriageState(TypedDict):
    # Incident input
    incident_id: str
    alert_payload: dict[str, Any]

    fetched_logs: Optional[list[dict]]
    fetched_metrics: Optional[dict]

    root_cause: Optional[str]
    root_cause_confidence: Optional[float]

    proposed_remediation: Optional[dict]  # {action, target, params, risk_level, rationale}

    # Human in the loop gate
    human_decision: Optional[Literal["approved", "rejected", "edited"]]
    operator_edit: Optional[dict]  # operator-supplied param overrides

    # Execution and verification
    execution_result: Optional[dict]
    verification_result: Optional[str]

    messages: Annotated[list, add_messages]

    # Workflow metadata
    current_step: str
    error: Optional[str]
    completed: bool