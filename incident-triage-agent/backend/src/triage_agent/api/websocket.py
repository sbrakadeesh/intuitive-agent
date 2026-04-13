"""WebSocket connection manager and handler for real-time triage event streaming."""
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from triage_agent.models.events import ApprovalMessage, WSEvent
from triage_agent.services.incident_store import IncidentStore

# Maps the last-completed node to the interrupted (next) node name.
_NEXT_NODE: dict[str, str] = {
    "analyze_root_cause": "propose_remediation",
    "propose_remediation": "execute_remediation",
    "verify_resolution": "end_review",
}

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections grouped by incident ID.

    Multiple clients may connect to the same incident simultaneously;
    events are broadcast to all of them.
    """

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    async def connect(self, incident_id: str, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and register it for the incident.

        Args:
            incident_id: The incident this client is subscribing to.
            websocket: The incoming WebSocket connection to accept.
        """
        await websocket.accept()
        self._connections.setdefault(incident_id, set()).add(websocket)
        logger.info("websocket connected: incident=%s", incident_id)

    def disconnect(self, incident_id: str, websocket: WebSocket) -> None:
        """Remove a WebSocket from the incident's subscriber set.

        Args:
            incident_id: The incident the client was subscribed to.
            websocket: The WebSocket connection to remove.
        """
        sockets = self._connections.get(incident_id)
        if sockets:
            sockets.discard(websocket)
            if not sockets:
                del self._connections[incident_id]
        logger.info("websocket disconnected: incident=%s", incident_id)

    async def broadcast(self, incident_id: str, event: WSEvent) -> None:
        """Send an event to every connected client for the given incident.

        Broken connections are silently removed so one dead client does not
        block delivery to the rest.

        Args:
            incident_id: The incident whose subscribers should receive the event.
            event: The event to serialise and send.
        """
        sockets = list(self._connections.get(incident_id, set()))
        if not sockets:
            return

        payload = event.model_dump_json()
        dead: list[WebSocket] = []

        for ws in sockets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(incident_id, ws)


manager = ConnectionManager()


async def websocket_handler(
    websocket: WebSocket,
    incident_id: str,
    runner: Any,
    store: IncidentStore,
) -> None:
    """Handle the full lifecycle of a single WebSocket client connection.

    Connects the client, replays a synthetic interrupt event if the incident
    is already awaiting approval, then loops receiving operator decisions and
    forwarding them to the graph runner.  Cleans up on disconnect.

    Args:
        websocket: The WebSocket connection from the FastAPI route.
        incident_id: The incident this client is interacting with.
        runner: A graph runner instance that exposes ``submit_decision``.
        store: The incident store used to replay state on reconnect.
    """
    await manager.connect(incident_id, websocket)
    try:
        # If the graph is already paused at an interrupt, the client missed
        # the original broadcast.  Replay a synthetic interrupt event so the
        # ApprovalPanel renders immediately on connect / reconnect.
        try:
            record = await store.get(incident_id)
            if record.status == "awaiting_approval" and record.current_step:
                interrupted_node = _NEXT_NODE.get(record.current_step)
                if interrupted_node:
                    context: dict[str, Any] = {}
                    if interrupted_node == "propose_remediation":
                        context = {
                            "root_cause": record.root_cause,
                            "root_cause_confidence": record.root_cause_confidence,
                        }
                    elif interrupted_node == "execute_remediation":
                        context = {"proposed_remediation": record.proposed_remediation}
                    elif interrupted_node == "end_review":
                        context = {"verification_result": record.verification_result}
                    replay = WSEvent(
                        event_type="interrupt",
                        incident_id=incident_id,
                        step_name=interrupted_node,
                        data={"awaiting": interrupted_node, "context": context},
                    )
                    await websocket.send_text(replay.model_dump_json())
                    logger.info(
                        "websocket_handler: replayed interrupt event for incident=%s step=%s",
                        incident_id,
                        interrupted_node,
                    )
        except Exception as exc:
            logger.warning(
                "websocket_handler: could not replay interrupt for incident=%s: %s",
                incident_id,
                exc,
            )

        while True:
            raw = await websocket.receive_text()
            try:
                message = ApprovalMessage.model_validate_json(raw)
                await runner.submit_decision(incident_id, message)
            except Exception as exc:
                logger.warning(
                    "websocket_handler: invalid message for incident=%s: %s",
                    incident_id,
                    exc,
                )
    except WebSocketDisconnect:
        logger.info("websocket_handler: client disconnected incident=%s", incident_id)
        manager.disconnect(incident_id, websocket)
    except Exception as exc:
        logger.error("websocket_handler: unexpected error incident=%s: %s", incident_id, exc, exc_info=True)
        manager.disconnect(incident_id, websocket)
