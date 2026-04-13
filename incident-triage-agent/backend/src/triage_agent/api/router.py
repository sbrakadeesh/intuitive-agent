"""FastAPI router factory — wires HTTP endpoints to the store and runner."""
import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import JSONResponse

from triage_agent.agent.checkpointer import get_checkpointer
from triage_agent.agent.graph import build_graph
from triage_agent.config import config
from triage_agent.models.incident import (
    CreateIncidentRequest,
    HumanDecisionRequest,
    IncidentRecord,
)
from triage_agent.services.incident_store import IncidentStore
from triage_agent.services.runner import TriageRunner

logger = logging.getLogger(__name__)


def build_router(store: IncidentStore, runner: TriageRunner) -> APIRouter:
    """Construct and return the application APIRouter.

    All routes are registered against the returned router, which should be
    included in the top-level FastAPI app.

    Args:
        store: The ``IncidentStore`` used by incident CRUD endpoints.
        runner: The ``TriageRunner`` used to start and resume graph runs.

    Returns:
        A configured ``APIRouter`` instance.
    """
    router = APIRouter()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @router.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        """Kubernetes liveness probe — confirms the process is alive."""
        return {"status": "ok"}

    @router.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, Any]:
        """Kubernetes readiness probe — confirms the app is ready to serve."""
        return {"status": "ok", "ollama": config.ollama_model}

    # ------------------------------------------------------------------
    # Incidents
    # ------------------------------------------------------------------

    @router.post(
        "/api/incidents",
        response_model=IncidentRecord,
        status_code=201,
        tags=["incidents"],
    )
    async def create_incident(
        body: CreateIncidentRequest,
        background_tasks: BackgroundTasks,
    ) -> IncidentRecord:
        """Create a new incident and immediately kick off background triage.

        Args:
            body: The alert payload to triage.
            background_tasks: FastAPI background task queue.

        Returns:
            The newly created ``IncidentRecord`` (status ``"pending"``).
        """
        record = await store.create(body.alert)
        background_tasks.add_task(runner.start_triage, record.incident_id)
        logger.info("create_incident: started triage for incident=%s", record.incident_id)
        return record

    @router.get(
        "/api/incidents",
        response_model=list[IncidentRecord],
        tags=["incidents"],
    )
    async def list_incidents(
        status: Optional[str] = Query(default=None, description="Filter by status"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> list[IncidentRecord]:
        """List incidents, optionally filtered by status.

        Args:
            status: Optional status filter (e.g. ``"running"``, ``"completed"``).
            limit: Maximum number of records to return.
            offset: Number of records to skip for pagination.

        Returns:
            A list of ``IncidentRecord`` instances ordered by creation time descending.
        """
        return await store.list(status=status, limit=limit, offset=offset)

    @router.get(
        "/api/incidents/{incident_id}",
        response_model=IncidentRecord,
        tags=["incidents"],
    )
    async def get_incident(incident_id: str) -> IncidentRecord:
        """Fetch a single incident by ID.

        Args:
            incident_id: The incident to retrieve.

        Returns:
            The matching ``IncidentRecord``.

        Raises:
            HTTPException: 404 if the incident does not exist.
        """
        try:
            return await store.get(incident_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

    @router.post(
        "/api/incidents/{incident_id}/approve",
        tags=["incidents"],
    )
    async def approve_incident(
        incident_id: str,
        body: HumanDecisionRequest,
    ) -> dict[str, str]:
        """Submit an operator decision at a human-in-the-loop interrupt.

        Args:
            incident_id: The incident currently awaiting approval.
            body: The operator's decision and any parameter overrides.

        Returns:
            ``{"status": "decision_received"}`` on success.

        Raises:
            HTTPException: 404 if the incident does not exist.
        """
        try:
            await store.get(incident_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

        from triage_agent.models.events import ApprovalMessage
        approval = ApprovalMessage(
            decision=body.decision,
            operator_edit=body.operator_edit,
            operator_notes=body.operator_notes,
        )
        await runner.submit_decision(incident_id, approval)
        logger.info(
            "approve_incident: incident=%s decision=%s", incident_id, body.decision
        )
        return {"status": "decision_received"}

    @router.get(
        "/api/incidents/{incident_id}/state",
        tags=["incidents"],
    )
    async def get_incident_state(incident_id: str) -> dict[str, Any]:
        """Return the raw LangGraph checkpoint values for an incident.

        Reads the latest checkpointed state directly from the graph without
        triggering any graph execution.

        Args:
            incident_id: The incident whose state to retrieve.

        Returns:
            The raw state values dict from the LangGraph checkpoint.

        Raises:
            HTTPException: 404 if the incident or checkpoint does not exist.
        """
        try:
            await store.get(incident_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")

        graph_config = {"configurable": {"thread_id": incident_id}}
        try:
            async with get_checkpointer() as checkpointer:
                graph = build_graph(checkpointer)
                snapshot = await graph.aget_state(graph_config)
        except Exception as exc:
            logger.error("get_incident_state: failed for incident=%s: %s", incident_id, exc)
            raise HTTPException(status_code=404, detail="No checkpoint found for incident")

        if snapshot is None:
            raise HTTPException(status_code=404, detail="No checkpoint found for incident")

        return snapshot.values

    return router
