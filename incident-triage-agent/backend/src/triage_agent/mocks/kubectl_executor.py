"""Mock kubectl executor — simulates cluster operations without a real cluster."""
import asyncio
from typing import Any


_TEMPLATES: dict[str, dict[str, Any]] = {
    "restart_pod": {
        "stdout":      "pod/{pod} deleted\npod/{pod} created",
        "stderr":      "",
        "exit_code":   0,
        "duration_ms": 1200,
    },
    "scale_up": {
        "stdout":      "deployment.apps/{service} scaled",
        "stderr":      "",
        "exit_code":   0,
        "duration_ms": 800,
    },
    "rollback": {
        "stdout":      "deployment.apps/{service} rolled back\ndeployment.apps/{service} successfully rolled out",
        "stderr":      "",
        "exit_code":   0,
        "duration_ms": 2100,
    },
    "increase_memory_limit": {
        "stdout":      "deployment.apps/{service} patched",
        "stderr":      "",
        "exit_code":   0,
        "duration_ms": 600,
    },
    "other": {
        "stdout":      "Command executed successfully",
        "stderr":      "",
        "exit_code":   0,
        "duration_ms": 500,
    },
}


class MockKubectlExecutor:
    """Simulates kubectl operations against a Kubernetes cluster.

    Looks up a canned response template by action name, substitutes
    ``{pod}`` and ``{service}`` placeholders, and returns the result
    enriched with the original ``action``, ``target``, and ``params``.
    """

    async def execute(
        self, action: str, target: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Simulate a kubectl command for the given remediation action.

        Waits briefly to simulate cluster round-trip latency, selects the
        template matching ``action`` (falling back to ``"other"`` for
        unrecognised actions), and interpolates ``{pod}`` and ``{service}``
        placeholders before returning.

        Args:
            action: The remediation action key (e.g. ``"restart_pod"``).
            target: The Kubernetes resource name, used as ``{service}`` in
                template strings and as the base for the default pod name.
            params: Execution parameters forwarded from the graph.  May
                contain ``"pod_name"`` to override the generated pod name.

        Returns:
            A dict with ``stdout``, ``stderr``, ``exit_code``,
            ``duration_ms``, ``action``, ``target``, and ``params`` keys.
        """
        await asyncio.sleep(0.3)

        template = dict(_TEMPLATES.get(action, _TEMPLATES["other"]))

        pod = params.get("pod_name", f"{target}-7d9f6c8b4-xk9p2")

        template["stdout"] = template["stdout"].format(pod=pod, service=target)

        return {
            **template,
            "action": action,
            "target": target,
            "params": params,
        }

    def execute_sync(self, action: str, target: str, params: dict[str, Any]) -> dict[str, Any]:
        """Synchronous wrapper around ``execute`` for use with ``asyncio.to_thread``.

        Args:
            action: The remediation action key.
            target: The Kubernetes resource name.
            params: Execution parameters forwarded from the graph.

        Returns:
            The same dict returned by ``execute``.
        """
        return asyncio.run(self.execute(action, target, params))
