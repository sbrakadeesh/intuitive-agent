"""Mock log fetcher — returns realistic-looking log entries without a real backend."""
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Any


_SCENARIOS: dict[str, list[dict[str, str]]] = {
    "oom_kill": [
        {"level": "ERROR", "component": "kubelet", "msg": "OOMKilled exceeded memory 512Mi"},
        {"level": "WARN",  "component": "service", "msg": "{service} memory at 98%"},
        {"level": "ERROR", "component": "service", "msg": "{service} OutOfMemoryError heap space"},
        {"level": "INFO",  "component": "kubelet", "msg": "{service} back-off restarting restart_count=5"},
    ],
    "crash_loop": [
        {"level": "ERROR", "component": "kubelet", "msg": "{service} back-off restarting restart_count=8"},
        {"level": "ERROR", "component": "service", "msg": "{service} liveness probe failed 503"},
        {"level": "ERROR", "component": "service", "msg": "{service} failed to connect to database"},
        {"level": "WARN",  "component": "kubelet", "msg": "{service} pod sandbox changed"},
    ],
    "high_latency": [
        {"level": "WARN",  "component": "service", "msg": "{service} p99 latency 3200ms exceeds SLO 500ms"},
        {"level": "ERROR", "component": "service", "msg": "{service} upstream timeout 30s"},
        {"level": "WARN",  "component": "service", "msg": "{service} connection pool exhausted 100/100"},
        {"level": "ERROR", "component": "service", "msg": "{service} circuit breaker OPEN"},
    ],
}


class MockLogFetcher:
    """Simulates a log aggregation backend with realistic incident log entries.

    Randomly selects one of three incident scenarios on each call so the
    graph exercises different log patterns during development and testing.
    """

    async def get_logs(self, service: str) -> list[dict[str, Any]]:
        """Fetch simulated log entries for the given service.

        Waits briefly to simulate backend latency, then returns four log
        entries for a randomly chosen incident scenario.  Timestamps are
        spaced four minutes apart ending at the current UTC time, giving
        the appearance of a real recent log tail.

        Args:
            service: The service name to embed in log messages.

        Returns:
            A list of four log entry dicts, each with ``timestamp``,
            ``level``, ``component``, ``msg``, and ``service`` keys.
        """
        await asyncio.sleep(0.1)

        scenario = random.choice(list(_SCENARIOS.keys()))
        templates = _SCENARIOS[scenario]

        now = datetime.now(timezone.utc)
        entries: list[dict[str, Any]] = []

        for i, template in enumerate(templates):
            timestamp = now - timedelta(minutes=4 * (len(templates) - 1 - i))
            entries.append({
                "timestamp": timestamp.isoformat(),
                "level":     template["level"],
                "component": template["component"],
                "msg":       template["msg"].format(service=service),
                "service":   service,
            })

        return entries

    def fetch_logs(self, service: str) -> list[dict[str, Any]]:
        """Synchronous wrapper around ``get_logs`` for use with ``asyncio.to_thread``.

        Args:
            service: The service name to embed in log messages.

        Returns:
            The same list returned by ``get_logs``.
        """
        return asyncio.run(self.get_logs(service))
