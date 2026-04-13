"""LangChain tool definitions — callable by the LLM during analysis nodes."""

from langchain_core.tools import tool
from triage_agent.mocks.log_fetcher import MockLogFetcher
from triage_agent.mocks.metrics_service import MockMetricsService
from triage_agent.mocks.kubectl_executor import MockKubectlExecutor


@tool
async def fetch_logs(service: str, minutes_back: int = 30) -> list[dict]:
    """Fetch recent log entries for a service.

    Args:
        service: The service name (e.g. 'payment-service').
        minutes_back: How many minutes of history to retrieve.
    """
   
    return await MockLogFetcher().get_logs(service, minutes_back)


@tool
async def fetch_metrics(service: str, minutes_back: int = 30) -> dict:
    """Fetch CPU, memory, and error rate metrics for a service.

    Args:
        service: The service name.
        minutes_back: How many minutes of history to retrieve.
    """
    return await MockMetricsService().get_metrics(service, minutes_back)


@tool
async def run_kubectl(action: str, target: str, dry_run: bool = True) -> dict:
    """Execute a kubectl command against the cluster.

    Args:
        action: One of 'restart_pod', 'scale_up', 'rollback'.
        target: The deployment or pod name.
        dry_run: When True (default) only simulates the action.
    """
    params = {"dry_run": dry_run}
    return await MockKubectlExecutor().execute(action, target, params)


ALL_TOOLS = [fetch_logs, fetch_metrics, run_kubectl]
