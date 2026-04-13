from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from triage_agent.config import config


@asynccontextmanager
async def get_checkpointer():
    """Yields an AsyncSqliteSaver backed by the configured DB path.

    Usage:
        async with get_checkpointer() as cp:
            graph = build_graph(cp)
    """
    async with AsyncSqliteSaver.from_conn_string(config.db_path) as checkpointer:
        yield checkpointer
