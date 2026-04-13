"""Graph runner — streams the triage graph and bridges WebSocket operator decisions."""
import asyncio
import logging
from typing import Any, Optional

from langgraph.types import Command

from triage_agent.agent.checkpointer import get_checkpointer
from triage_agent.agent.constants import (
    ANALYZE_ROOT_CAUSE,
    END_REVIEW,
    EXECUTE_REMEDIATION,
    FETCH_CONTEXT,
    INGEST_ALERT,
    PROPOSE_REMEDIATION,
    VERIFY_RESOLUTION,
)
from triage_agent.agent.graph import ALL_NODES, build_graph
from triage_agent.agent.state import TriageState
from triage_agent.models.events import ApprovalMessage, WSEvent
from triage_agent.services.incident_store import IncidentStore

logger = logging.getLogger(__name__)

# Node names that map to meaningful UI steps.
_KNOWN_NODES: set[str] = set(ALL_NODES)

# Maps the node at which an interrupt fires to the state keys surfaced to the operator.
_INTERRUPT_CONTEXT: dict[str, list[str]] = {
    PROPOSE_REMEDIATION: ["root_cause", "root_cause_confidence", "fetched_logs", "fetched_metrics"],
    EXECUTE_REMEDIATION: ["proposed_remediation", "root_cause"],
    END_REVIEW:          ["verification_result", "execution_result"],
}


class TriageRunner:
    """Orchestrates a triage graph run and routes operator decisions back into it.

    Args:
        store: The ``IncidentStore`` used to persist graph state updates.
        ws_manager: The ``ConnectionManager`` used to broadcast events to clients.
    """

    def __init__(self, store: IncidentStore, ws_manager: Any) -> None:
        self._store = store
        self._ws_manager = ws_manager
        self._queues: dict[str, asyncio.Queue] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_triage(self, incident_id: str) -> None:
        """Stream the triage graph for ``incident_id`` from start to completion.

        Fetches the incident from the store, builds the initial ``TriageState``,
        then drives the compiled graph via ``astream_events``.  Each event is
        forwarded to ``_handle_event``.  On any unhandled exception an ``error``
        WebSocket event is emitted and the incident status is set to
        ``"failed"``.

        Args:
            incident_id: The incident to run.
        """
        self._queues[incident_id] = asyncio.Queue()
        logger.info("start_triage: beginning triage for incident=%s", incident_id)

        try:
            record = await self._store.get(incident_id)
            logger.info("start_triage: fetched record for incident=%s", incident_id)
        except ValueError:
            logger.error("start_triage: incident not found: %s", incident_id)
            return
        except Exception as exc:
            logger.error("start_triage: unexpected error fetching incident=%s: %s", incident_id, exc, exc_info=True)
            return

        initial_state: TriageState = {
            "incident_id":  incident_id,
            "alert_payload": record.alert.model_dump(),
            "fetched_logs":  None,
            "fetched_metrics": None,
            "root_cause":    None,
            "root_cause_confidence": None,
            "proposed_remediation": None,
            "human_decision": None,
            "operator_edit":  None,
            "execution_result": None,
            "verification_result": None,
            "messages": [],
            "current_step": "start",
            "error":     None,
            "completed": False,
        }

        config = {"configurable": {"thread_id": incident_id}}

        await self._store.set_status(incident_id, "running")
        await self._emit(incident_id, "status_update", None, {"status": "running"})

        try:
            async with get_checkpointer() as checkpointer:
                graph = build_graph(checkpointer)
                async for event in graph.astream_events(
                    initial_state, config=config, version="v2"
                ):
                    await self._handle_event(incident_id, event, graph, config)

                # Check if graph is suspended at an interrupt
                snapshot = await graph.aget_state(config)
                logger.info(
                    "start_triage: after stream — next=%s interrupted=%s",
                    snapshot.next,
                    bool(snapshot.next),
                )

                while snapshot.next:
                    # Graph is interrupted — wait for human decision.
                    interrupted_node = snapshot.next[0]
                    context_keys = _INTERRUPT_CONTEXT.get(interrupted_node, [])
                    context_data = {k: snapshot.values.get(k) for k in context_keys}
                    logger.info(
                        "start_triage: interrupted before node=%s context_keys=%s",
                        interrupted_node,
                        context_keys,
                    )

                    await self._store.set_status(incident_id, "awaiting_approval")
                    await self._emit(
                        incident_id, "interrupt", interrupted_node,
                        {"awaiting": interrupted_node, "context": context_data},
                    )
                    logger.info("start_triage: waiting for decision at step=%s", interrupted_node)

                    approval = await self._queues[incident_id].get()
                    logger.info("start_triage: got decision=%s", approval.decision)

                    await self._store.set_status(incident_id, "running")
                    await graph.aupdate_state(
                        config,
                        {
                            "human_decision": approval.decision,
                            "operator_edit": approval.operator_edit,
                        },
                    )

                    async for event in graph.astream_events(
                        Command(resume=approval.decision), config=config, version="v2"
                    ):
                        await self._handle_event(incident_id, event, graph, config)

                    snapshot = await graph.aget_state(config)
                    logger.info("start_triage: after resume — next=%s", snapshot.next)

            await self._store.set_status(incident_id, "completed")
            await self._emit(incident_id, "complete", None, {"incident_id": incident_id})

        except Exception as exc:
            logger.error("start_triage: graph run failed for incident=%s: %s", incident_id, exc, exc_info=True)
            await self._store.set_status(incident_id, "failed")
            await self._emit(incident_id, "error", None, {"error": str(exc)})

        finally:
            self._queues.pop(incident_id, None)

    async def resume_interrupted(self) -> None:
        """On startup, recreate queues for any incidents stuck in awaiting_approval.

        When uvicorn reloads, in-memory asyncio tasks are lost.  This method
        finds incidents that were paused at a human interrupt and re-enters the
        waiting loop so operator decisions can be submitted again.
        """
        try:
            records = await self._store.list(status="awaiting_approval", limit=200)
            for record in records:
                incident_id = record.incident_id
                if incident_id in self._queues:
                    continue
                logger.info("resume_interrupted: re-attaching queue for incident=%s", incident_id)
                self._queues[incident_id] = asyncio.Queue()
                asyncio.create_task(self._wait_for_decision(incident_id))
        except Exception as exc:
            logger.error("resume_interrupted: failed: %s", exc, exc_info=True)

    async def _wait_for_decision(self, incident_id: str) -> None:
        """Wait for an operator decision and resume the graph from checkpoint."""
        try:
            async with get_checkpointer() as checkpointer:
                graph = build_graph(checkpointer)
                config = {"configurable": {"thread_id": incident_id}}

                while True:
                    snapshot = await graph.aget_state(config)
                    if not snapshot.next:
                        logger.info("_wait_for_decision: no interrupt found for incident=%s", incident_id)
                        break

                    interrupted_node = snapshot.next[0]
                    context_keys = _INTERRUPT_CONTEXT.get(interrupted_node, [])
                    context_data = {k: snapshot.values.get(k) for k in context_keys}

                    await self._store.set_status(incident_id, "awaiting_approval")
                    await self._emit(incident_id, "interrupt", interrupted_node,
                                     {"awaiting": interrupted_node, "context": context_data})
                    logger.info("_wait_for_decision: waiting for decision incident=%s step=%s",
                                incident_id, interrupted_node)

                    approval: ApprovalMessage = await self._queues[incident_id].get()
                    logger.info("_wait_for_decision: got decision=%s incident=%s",
                                approval.decision, incident_id)

                    await self._store.set_status(incident_id, "running")
                    await graph.aupdate_state(config, {
                        "human_decision": approval.decision,
                        "operator_edit": approval.operator_edit,
                    })

                    async for event in graph.astream_events(
                        Command(resume=approval.decision), config=config, version="v2"
                    ):
                        await self._handle_event(incident_id, event, graph, config)

                    snapshot = await graph.aget_state(config)
                    if not snapshot.next:
                        break

            await self._store.set_status(incident_id, "completed")
            await self._emit(incident_id, "complete", None, {"incident_id": incident_id})

        except Exception as exc:
            logger.error("_wait_for_decision: failed incident=%s: %s", incident_id, exc, exc_info=True)
            await self._store.set_status(incident_id, "failed")
            await self._emit(incident_id, "error", None, {"error": str(exc)})
        finally:
            self._queues.pop(incident_id, None)

    async def submit_decision(
        self, incident_id: str, payload: ApprovalMessage
    ) -> None:
        """Forward an operator decision to the waiting graph run.

        Args:
            incident_id: The incident whose graph is currently interrupted.
            payload: The operator's ``ApprovalMessage`` from the WebSocket.
        """
        queue = self._queues.get(incident_id)
        if queue is None:
            logger.warning(
                "submit_decision: no active run for incident=%s", incident_id
            )
            return
        await queue.put(payload)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _handle_event(
        self,
        incident_id: str,
        event: dict[str, Any],
        graph: Any,
        config: dict[str, Any],
    ) -> None:
        """Dispatch a single ``astream_events`` event to the appropriate handler.

        Args:
            incident_id: The incident being processed.
            event: The raw event dict from LangGraph.
            graph: The compiled graph (needed to get state snapshots).
            config: The graph run config containing ``thread_id``.
        """
        kind: str = event.get("event", "")
        name: str = event.get("name", "")

        logger.debug("_handle_event: kind=%s name=%s", kind, name)

        if kind == "on_chain_start" and name in _KNOWN_NODES:
            await self._store.update_step(incident_id, name)
            await self._emit(incident_id, "step_start", name, None)

        elif kind == "on_chain_end" and name in _KNOWN_NODES:
            output: dict[str, Any] = event.get("data", {}).get("output") or {}
            # Persist any state fields the node updated.
            await self._store.update_from_state(incident_id, output)
            await self._emit(incident_id, "step_complete", name, output)

        elif kind == "on_chain_end" and name == "__interrupt__":
            await self._handle_interrupt(incident_id, event, graph, config)

        elif kind == "on_tool_start":
            await self._emit(
                incident_id, "tool_call", name,
                {"input": event.get("data", {}).get("input")}
            )

        elif kind == "on_tool_end":
            await self._emit(
                incident_id, "tool_result", name,
                {"output": event.get("data", {}).get("output")}
            )

    async def _handle_interrupt(
        self,
        incident_id: str,
        event: dict[str, Any],
        graph: Any,
        config: dict[str, Any],
    ) -> None:
        """Pause the graph, surface context to the operator, and resume on decision.

        Fetches the current graph snapshot to determine which interrupt point
        was reached, selects the relevant state keys, emits an ``interrupt``
        event, sets the incident to ``"awaiting_approval"``, then blocks until
        the operator submits a decision via ``submit_decision``.

        Args:
            incident_id: The incident whose graph interrupted.
            event: The raw ``on_chain_end/__interrupt__`` event.
            graph: The compiled graph used to get the state snapshot.
            config: The graph run config containing ``thread_id``.
        """
        snapshot = await graph.aget_state(config)
        state: TriageState = snapshot.values

        # snapshot.next[0] is the node about to run (interrupt_before).
        interrupted_node: str = snapshot.next[0] if snapshot.next else state.get("current_step", "")
        context_keys = _INTERRUPT_CONTEXT.get(interrupted_node, [])
        context_data: dict[str, Any] = {k: state.get(k) for k in context_keys}

        await self._store.set_status(incident_id, "awaiting_approval")
        await self._emit(
            incident_id, "interrupt", interrupted_node,
            {"awaiting": interrupted_node, "context": context_data},
        )

        # Block until the operator submits a decision.
        queue = self._queues[incident_id]
        approval: ApprovalMessage = await queue.get()

        logger.info(
            "_handle_interrupt: incident=%s step=%s decision=%s",
            incident_id, interrupted_node, approval.decision,
        )

        await self._store.set_status(incident_id, "running")
        await self._emit(
            incident_id, "status_update", interrupted_node,
            {"status": "running", "decision": approval.decision},
        )

        # Resume the graph with the operator's decision injected into state,
        # then re-stream the remaining nodes.
        await graph.aupdate_state(
            config,
            {
                "human_decision": approval.decision,
                "operator_edit":  approval.operator_edit,
            },
        )
        async for ev in graph.astream_events(
            Command(resume=approval.decision),
            config=config,
            version="v2",
        ):
            await self._handle_event(incident_id, ev, graph, config)

    async def _emit(
        self,
        incident_id: str,
        event_type: str,
        step_name: Optional[str],
        data: Optional[Any],
    ) -> None:
        """Construct a ``WSEvent`` and broadcast it to all subscribed clients.

        Args:
            incident_id: The incident whose subscribers should receive the event.
            event_type: One of the ``WSEvent.event_type`` literals.
            step_name: The node name, if applicable.
            data: Arbitrary payload to include in the event.
        """
        ws_event = WSEvent(
            event_type=event_type,  # type: ignore[arg-type]
            incident_id=incident_id,
            step_name=step_name,
            data=data,
        )
        await self._ws_manager.broadcast(incident_id, ws_event)
