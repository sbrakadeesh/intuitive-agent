"""Mock metrics service — returns plausible CPU/memory/error-rate snapshots."""
import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Any


# Each metric definition: (baseline, spike_value, spike_index, unit)
_SCENARIO_SPECS: dict[str, dict[str, tuple[float, float, int, str]]] = {
    "oom_kill": {
        "memory_usage_bytes": (200_000_000, 512_000_000, 6, "bytes"),
        "error_rate_rps":     (0.01,        2.4,         7, "rps"),
        "restart_count":      (0,           5,           5, "count"),
        "cpu_usage_cores":    (0.15,        0.15,        10, "cores"),  # spike_index beyond range = always baseline
    },
    "crash_loop": {
        "restart_count":      (0,           8,           3, "count"),
        "error_rate_rps":     (0.01,        8.0,         4, "rps"),
        "memory_usage_bytes": (180_000_000, 180_000_000, 10, "bytes"),
        "cpu_usage_cores":    (0.1,         0.1,         10, "cores"),
    },
    "high_latency": {
        "p99_latency_ms":     (80,          3200,        5, "ms"),
        "cpu_usage_cores":    (0.2,         0.95,        5, "cores"),
        "error_rate_rps":     (0.01,        1.2,         5, "rps"),
        "memory_usage_bytes": (220_000_000, 220_000_000, 10, "bytes"),
    },
}

_NUM_POINTS = 10


def _build_series(
    baseline: float,
    spike_value: float,
    spike_index: int,
    timestamps: list[str],
) -> list[dict[str, Any]]:
    """Build a 10-point time series for a single metric.

    Points before ``spike_index`` use the baseline with ±5 % random noise.
    Points at and after ``spike_index`` use the spike value exactly.

    Args:
        baseline: The normal operating value.
        spike_value: The anomalous value applied from the spike index onward.
        spike_index: The first index at which the spike value is used.
        timestamps: Pre-computed ISO timestamp strings, oldest first.

    Returns:
        A list of ``{"timestamp": str, "value": float}`` dicts.
    """
    points: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        if i < spike_index:
            noise = random.uniform(-0.05, 0.05)
            value = baseline * (1 + noise)
        else:
            value = spike_value
        points.append({"timestamp": ts, "value": round(value, 4)})
    return points


class MockMetricsService:
    """Simulates a Prometheus-style metrics backend for local development.

    Randomly selects one of three incident scenarios per call so the graph
    exercises different metric shapes during development and testing.
    """

    async def get_metrics(
        self, service: str, minutes_back: int = 30
    ) -> dict[str, Any]:
        """Fetch simulated metrics for the given service.

        Waits briefly to simulate backend latency, then returns a 10-point
        time series for each metric in the randomly chosen scenario.
        Timestamps are spaced 3 minutes apart ending at the current UTC time.

        Args:
            service: The service name to include in the response envelope.
            minutes_back: Recorded in the response envelope; does not affect
                the number of data points (always 10).

        Returns:
            A dict with ``service``, ``scenario``, ``window_minutes``, and
            ``metrics`` keys.  Each entry in ``metrics`` has ``values``
            (list of timestamp/value dicts) and ``unit``.
        """
        await asyncio.sleep(0.05)

        if "payment" in service.lower():
            scenario = "oom_kill"
        elif "auth" in service.lower():
            scenario = "crash_loop"
        elif "recommendation" in service.lower():
            scenario = "high_latency"
        else:
            scenario = random.choice(list(_SCENARIO_SPECS.keys()))
        specs = _SCENARIO_SPECS[scenario]

        now = datetime.now(timezone.utc)
        timestamps = [
            (now - timedelta(minutes=3 * (_NUM_POINTS - 1 - i))).isoformat()
            for i in range(_NUM_POINTS)
        ]

        metrics: dict[str, Any] = {}
        for name, (baseline, spike_value, spike_index, unit) in specs.items():
            metrics[name] = {
                "values": _build_series(baseline, spike_value, spike_index, timestamps),
                "unit": unit,
            }

        return {
            "service": service,
            "scenario": scenario,
            "window_minutes": minutes_back,
            "metrics": metrics,
        }

    def fetch_metrics(self, service: str, minutes_back: int = 30) -> dict[str, Any]:
        """Synchronous wrapper around ``get_metrics`` for use with ``asyncio.to_thread``.

        Args:
            service: The service name to include in the response envelope.
            minutes_back: Passed through to ``get_metrics``.

        Returns:
            The same dict returned by ``get_metrics``.
        """
        return asyncio.run(self.get_metrics(service, minutes_back))
