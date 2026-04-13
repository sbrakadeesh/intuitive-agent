"""SQLite-backed persistence layer for incident triage records."""
import json
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

from triage_agent.models.incident import AlertPayload, IncidentRecord


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id               TEXT PRIMARY KEY,
    alert_json                TEXT NOT NULL,
    status                    TEXT NOT NULL DEFAULT 'pending',
    current_step              TEXT,
    root_cause                TEXT,
    root_cause_confidence     REAL,
    proposed_remediation_json TEXT,
    execution_result_json     TEXT,
    verification_result       TEXT,
    error                     TEXT,
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL
)
"""

_UPDATABLE_FIELDS = {
    "root_cause",
    "proposed_remediation",
    "execution_result",
    "verification_result",
    "error",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_record(row: aiosqlite.Row) -> IncidentRecord:
    """Convert a raw SQLite row into an ``IncidentRecord``.

    Args:
        row: A row returned by aiosqlite with ``row_factory = aiosqlite.Row``.

    Returns:
        A fully populated ``IncidentRecord`` instance.
    """
    return IncidentRecord(
        incident_id=row["incident_id"],
        alert=AlertPayload(**json.loads(row["alert_json"])),
        status=row["status"],
        current_step=row["current_step"],
        root_cause=row["root_cause"],
        root_cause_confidence=row["root_cause_confidence"],
        proposed_remediation=json.loads(row["proposed_remediation_json"])
            if row["proposed_remediation_json"] else None,
        execution_result=json.loads(row["execution_result_json"])
            if row["execution_result_json"] else None,
        verification_result=row["verification_result"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class IncidentStore:
    """Async SQLite store for incident triage records.

    Opens a new connection per query so the store is safe to use from
    multiple concurrent coroutines without connection sharing.

    Args:
        db_path: File path for the SQLite database (e.g. ``"./triage.db"``).
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    async def init_db(self) -> None:
        """Create the ``incidents`` table if it does not already exist."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(_CREATE_TABLE)
            await db.commit()

    async def close(self) -> None:
        """No-op — connections are opened and closed per query."""

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    async def create(self, alert: AlertPayload) -> IncidentRecord:
        """Persist a new incident record and return it.

        Args:
            alert: The normalized alert payload for the incident.

        Returns:
            The newly created ``IncidentRecord`` with a generated
            ``incident_id`` and timestamps.
        """
        record = IncidentRecord(alert=alert)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO incidents (
                    incident_id, alert_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.incident_id,
                    record.alert.model_dump_json(),
                    record.status,
                    record.created_at,
                    record.updated_at,
                ),
            )
            await db.commit()
        return record

    async def update_step(self, incident_id: str, step: str) -> None:
        """Set ``current_step`` and refresh ``updated_at``.

        Args:
            incident_id: The incident to update.
            step: The name of the node that just started or completed.
        """
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE incidents SET current_step = ?, updated_at = ? WHERE incident_id = ?",
                (step, _utc_now(), incident_id),
            )
            await db.commit()

    async def set_status(self, incident_id: str, status: str) -> None:
        """Set ``status`` and refresh ``updated_at``.

        Args:
            incident_id: The incident to update.
            status: The new status string (e.g. ``"running"``, ``"completed"``).
        """
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE incidents SET status = ?, updated_at = ? WHERE incident_id = ?",
                (status, _utc_now(), incident_id),
            )
            await db.commit()

    async def update_from_state(
        self, incident_id: str, patch: dict[str, Any]
    ) -> None:
        """Apply a partial state patch to the incident record.

        Only keys present in ``_UPDATABLE_FIELDS`` are applied; any other
        keys in ``patch`` are silently ignored.  Dict-valued fields
        (``proposed_remediation``, ``execution_result``) are JSON-serialised
        before storage.

        Args:
            incident_id: The incident to update.
            patch: A dict of field names to new values, typically a subset of
                the LangGraph state returned by a node.
        """
        _JSON_FIELDS = {"proposed_remediation", "execution_result"}

        assignments: list[str] = []
        values: list[Any] = []

        for field in _UPDATABLE_FIELDS:
            if field not in patch:
                continue
            value = patch[field]
            col = f"{field}_json" if field in _JSON_FIELDS else field
            assignments.append(f"{col} = ?")
            values.append(json.dumps(value) if field in _JSON_FIELDS else value)

        if not assignments:
            return

        assignments.append("updated_at = ?")
        values.append(_utc_now())
        values.append(incident_id)

        sql = f"UPDATE incidents SET {', '.join(assignments)} WHERE incident_id = ?"
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(sql, values)
            await db.commit()

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get(self, incident_id: str) -> IncidentRecord:
        """Fetch a single incident by ID.

        Args:
            incident_id: The incident to retrieve.

        Returns:
            The matching ``IncidentRecord``.

        Raises:
            ValueError: If no incident with ``incident_id`` exists.
        """
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM incidents WHERE incident_id = ?", (incident_id,)
            ) as cursor:
                row = await cursor.fetchone()

        if row is None:
            raise ValueError(f"Incident not found: {incident_id}")
        return _row_to_record(row)

    async def list(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[IncidentRecord]:
        """List incidents, optionally filtered by status.

        Args:
            status: If provided, only incidents with this status are returned.
            limit: Maximum number of records to return (default 50).
            offset: Number of records to skip for pagination (default 0).

        Returns:
            A list of ``IncidentRecord`` instances ordered by ``created_at``
            descending.
        """
        if status is not None:
            sql = (
                "SELECT * FROM incidents WHERE status = ? "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            params: tuple[Any, ...] = (status, limit, offset)
        else:
            sql = "SELECT * FROM incidents ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params = (limit, offset)

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()

        return [_row_to_record(row) for row in rows]
