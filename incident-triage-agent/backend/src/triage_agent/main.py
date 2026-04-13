"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

from triage_agent.api.router import build_router
from triage_agent.api.websocket import ConnectionManager, websocket_handler
from triage_agent.config import config
from triage_agent.services.incident_store import IncidentStore
from triage_agent.services.runner import TriageRunner

# Module-level singletons
store = IncidentStore(config.db_path)
ws_manager = ConnectionManager()
runner = TriageRunner(store=store, ws_manager=ws_manager)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise resources on startup and clean up on shutdown."""
    await store.init_db()
    yield
    await store.close()


app = FastAPI(
    title="Incident Triage Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(build_router(store, runner))


@app.websocket("/ws/incidents/{incident_id}")
async def incidents_ws(websocket: WebSocket, incident_id: str) -> None:
    """WebSocket endpoint for real-time triage event streaming."""
    await websocket_handler(websocket, incident_id, runner)
