"""Capacity chatbot graph definition."""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from capacity_chatbot.nodes.capacity_agent import capacity_agent
from capacity_chatbot.state import CapacityChatbotState, InputState, OutputState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the LangGraph state graph structure (without compilation)."""
    builder = StateGraph(CapacityChatbotState, input_schema=InputState, output_schema=OutputState)

    builder.add_node("capacity_agent", capacity_agent)
    builder.add_edge("__start__", "capacity_agent")
    builder.add_edge("capacity_agent", END)

    return builder


def _add_connection_timeout(conn_string: str) -> str:
    """Add connect_timeout parameter to connection string if not present."""
    if "connect_timeout" not in conn_string:
        separator = "&" if "?" in conn_string else "?"
        return f"{conn_string}{separator}connect_timeout=10"
    return conn_string


async def _create_postgres_pool(conn_string: str):
    """Create and open async PostgreSQL connection pool."""
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    conn_params = _add_connection_timeout(conn_string)
    pool = AsyncConnectionPool(
        conninfo=conn_params,
        min_size=1,
        max_size=10,
        timeout=30,
        open=False,
        kwargs={
            "autocommit": True,
            "row_factory": dict_row,
        },
    )
    await pool.open()
    return pool


async def get_checkpointer():
    """Get checkpointer: PostgreSQL for production, MemorySaver for local development."""
    postgres_conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if not postgres_conn_string:
        logger.info("Using in-memory checkpointer (data lost on restart)")
        return MemorySaver()

    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        pool = await _create_postgres_pool(postgres_conn_string)
        checkpointer = AsyncPostgresSaver(conn=pool)
        await checkpointer.setup()

        logger.info("Using AsyncPostgresSaver with async pool for persistence")
        return checkpointer
    except Exception as e:
        logger.warning("Postgres connection failed: %s, falling back to MemorySaver", e)
        return MemorySaver()


# Cached graph instance
_cached_graph = None

# Cached postgres pool for direct queries (chat_history, etc.)
_postgres_pool = None


async def get_postgres_pool():
    """Get a Postgres pool for direct queries (e.g., chat_history).

    Separate from the checkpointer's pool. Returns None if no Postgres configured.
    """
    global _postgres_pool
    if _postgres_pool is None:
        conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
        if not conn_string:
            return None
        try:
            _postgres_pool = await _create_postgres_pool(conn_string)
        except Exception as e:
            logger.warning("Failed to create chat_history pool: %s", e)
            return None
    return _postgres_pool


async def get_graph():
    """
    Get the compiled graph with checkpointer.
    Must be called from an async context (e.g., FastAPI startup).
    """
    global _cached_graph
    if _cached_graph is None:
        builder = build_graph()
        checkpointer = await get_checkpointer()
        _cached_graph = builder.compile(checkpointer=checkpointer)
        logger.info("Graph compiled with checkpointer")
    return _cached_graph


# Module-level graph export for langgraph CLI (required by langgraph.json)
# This is used by `langgraph dev` command
graph = build_graph().compile()
