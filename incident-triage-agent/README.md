# Incident Triage Agent

An AI-powered SRE incident triage system built with LangGraph. It automatically analyzes alerts, identifies root causes, proposes remediation plans, and walks an operator through three human-in-the-loop approval steps before closing or escalating an incident.

---

## What This App Does

When an alert fires (OOMKilled pod, CrashLoopBackOff, high p99 latency), the agent:

1. **Ingests** the alert and normalizes it into a structured payload
2. **Fetches context** — logs and metrics for the affected service in parallel
3. **Analyzes root cause** — LLM reasons over logs and metrics and returns a root cause + confidence score
4. **Pauses for operator review** — you confirm or abort the root cause
5. **Proposes remediation** — LLM generates a concrete action (scale up, rollback, increase memory limit, etc.)
6. **Pauses for operator approval** — you approve, reject, or override the plan with custom params
7. **Executes remediation** — the approved action is applied to the cluster
8. **Verifies resolution** — LLM checks fresh metrics to confirm the incident is resolved
9. **Pauses for final sign-off** — you close the incident or escalate for further investigation

The frontend streams all agent activity over WebSocket in real time and renders each pause as an approval panel.

---

## How Agents Surface Information

The agent graph runs as a LangGraph `StateGraph`. Each node updates a shared `TriageState` and the runner broadcasts state changes as WebSocket events to the frontend.

| Event | When it fires | What the frontend does |
|---|---|---|
| `step_complete` | After each graph node finishes | Updates the step timeline |
| `interrupt` | Graph pauses at a HITL checkpoint | Shows the ApprovalPanel with context |
| `complete` | Graph reaches END | Sets status to `completed` or `escalated` |
| `error` | Unhandled exception in graph | Sets status to `failed` |

**Three interrupts, three contexts shown:**

| Interrupt | Node waiting | Shown to operator |
|---|---|---|
| 1 | `propose_remediation` | Root cause + confidence score |
| 2 | `execute_remediation` | Remediation plan (action, target, params, risk level, rationale) |
| 3 | `end_review` | Verification result (RESOLVED / UNRESOLVED explanation) |

Operator decisions (`approved`, `rejected`, `edited`, `abort`, `close`, `escalate`) are sent back over WebSocket and injected into the graph via `Command(resume=decision)`.

---

## What Is Mocked

Everything except the FastAPI server and LangGraph runtime is mocked. No real cluster, LLM, or observability backend is required to run the app.

| Mock | Real system it replaces | File |
|---|---|---|
| `MockChatOllama` | Ollama LLM server (`llama3.1`) | `backend/src/triage_agent/mocks/ollama_mock.py` |
| `MockMetricsService` | Prometheus / metrics backend | `backend/src/triage_agent/mocks/metrics_service.py` |
| `MockLogFetcher` | Log aggregation (ELK, Loki, etc.) | `backend/src/triage_agent/mocks/log_fetcher.py` |
| `MockKubectlExecutor` | Kubernetes cluster + kubectl | `backend/src/triage_agent/mocks/kubectl_executor.py` |

**Mock scenario routing** — each mock detects the active scenario from the service name and returns consistent, scenario-appropriate data across all three LLM calls:

| Service name | Scenario | Root cause |
|---|---|---|
| `payment-service` | OOMKilled | JVM heap exceeded 512Mi container limit — cache leak in session manager |
| `auth-service` | CrashLoopBackOff | Missing `DATABASE_URL` env var — pod fails liveness probe on startup |
| `recommendation-service` | High latency | Connection pool exhausted — 200 idle connections against a limit of 50 |

**To use a real Ollama instance** set `USE_MOCK_OLLAMA=false` and point `OLLAMA_BASE_URL` to your server. Logs, metrics, and kubectl remain mocked — there is no switch to route those to real backends.

---

## Prerequisites

- Python 3.11+
- Node.js 18+ with pnpm (`npm install -g pnpm`)
- Docker + Docker Compose (optional, for containerised run)
- Ollama (optional, only if `USE_MOCK_OLLAMA=false`)

---

## Running Locally

### Option A — Make (recommended)

```bash
# Starts backend (port 8000) + frontend (port 5173) together
make dev-local
```

### Option B — Manual

**Backend**

```bash
cd backend
pip install -e ".[dev]"
uvicorn src.triage_agent.main:app --reload --port 8000
```

**Frontend** (in a separate terminal)

```bash
cd frontend
pnpm install
pnpm dev
```

Open [http://localhost:5173](http://localhost:5173).

### Option C — Docker Compose

```bash
docker-compose up --build
```

- Backend: [http://localhost:8000](http://localhost:8000)
- Frontend: [http://localhost:80](http://localhost:80)

> Docker Compose sets `USE_MOCK_OLLAMA=false` and `OLLAMA_BASE_URL=http://host.docker.internal:11434` by default. Change these in `docker-compose.yml` if you don't have Ollama running, or set `USE_MOCK_OLLAMA=true`.

---

## Clearing the Database

All incident records and LangGraph checkpoints are stored in a single SQLite file. Delete it to reset the app to a clean state.

**Local dev** (default path is `backend/triage.db`):

```bash
rm -f backend/triage.db
```

**Custom path** — if you set `DB_PATH` in your `.env`, delete that file instead:

```bash
rm -f path/to/your.db
```

**Docker** — the database is written inside the container. Bring it down and remove the volume:

```bash
docker-compose down -v
```

After deleting the file, restart the backend — it recreates the schema automatically on startup. The frontend will show an empty incident list.

---

## Environment Variables

Copy `backend/.env.example` and adjust as needed:

| Variable | Default | Description |
|---|---|---|
| `USE_MOCK_OLLAMA` | `true` | Use deterministic mock LLM instead of real Ollama |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (ignored when mock is on) |
| `OLLAMA_MODEL` | `llama3.1` | Model to load from Ollama |
| `DB_PATH` | `./data/triage.db` | SQLite path for incident records and LangGraph checkpoints |

---

## Running Tests

```bash
cd backend
pytest
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health/live` | Liveness probe |
| `GET` | `/health/ready` | Readiness probe |
| `POST` | `/api/incidents` | Create and start triage for a new alert |
| `GET` | `/api/incidents` | List incidents (filterable by status, paginated) |
| `GET` | `/api/incidents/{id}` | Fetch a single incident record |
| `POST` | `/api/incidents/{id}/approve` | Submit operator decision at a HITL interrupt |
| `GET` | `/api/incidents/{id}/state` | Raw LangGraph checkpoint state |
| `WS` | `/ws/incidents/{id}` | Real-time event stream for an incident |

---

## Project Structure

```
incident-triage-agent/
├── backend/
│   └── src/triage_agent/
│       ├── agent/          # LangGraph graph, nodes, state, constants
│       ├── api/            # FastAPI routes + WebSocket handler
│       ├── mocks/          # MockChatOllama, metrics, logs, kubectl
│       ├── models/         # Pydantic schemas (alerts, events, incidents)
│       └── services/       # GraphRunner, IncidentStore
├── frontend/
│   └── src/
│       ├── components/     # ApprovalPanel, TriageView, IncidentList
│       ├── hooks/          # useIncidentWebSocket, useIncidentList
│       ├── store/          # Zustand incident store
│       └── types/          # TypeScript types
├── docker-compose.yml
└── Makefile
```
