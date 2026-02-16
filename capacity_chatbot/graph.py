"""Capacity chatbot graph definition."""

import logging
import os

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from capacity_chatbot.nodes.capacity_agent import capacity_agent
from capacity_chatbot.state import CapacityChatbotState, InputState, OutputState

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build the LangGraph state graph structure (without compilation)."""
    builder = StateGraph(
        CapacityChatbotState,
        input_schema=InputState,
        output_schema=OutputState
    )

    builder.add_node("capacity_agent", capacity_agent)
    builder.add_edge("__start__", "capacity_agent")
    builder.add_edge("capacity_agent", END)

    return builder


async def get_checkpointer():
    """
    Get the appropriate checkpointer (async).

    Uses PostgreSQL when POSTGRES_CONNECTION_STRING is set (production).
    Falls back to MemorySaver for local development.
    """
    postgres_conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if postgres_conn_string:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            from psycopg_pool import AsyncConnectionPool
            from psycopg.rows import dict_row

            # Add connection timeout if not specified
            conn_params = postgres_conn_string
            if "connect_timeout" not in conn_params:
                separator = "&" if "?" in conn_params else "?"
                conn_params = f"{conn_params}{separator}connect_timeout=10"

            # Create async pool with open=False to avoid deprecated auto-open
            # autocommit=True and row_factory=dict_row are REQUIRED by AsyncPostgresSaver:
            #   - autocommit ensures checkpoint writes are committed immediately
            #   - dict_row ensures query results are accessible as dictionaries
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
            # Properly open the pool in async context
            await pool.open()

            checkpointer = AsyncPostgresSaver(conn=pool)
            # Setup tables using async method
            await checkpointer.setup()

            # Verify connection works by checking tables exist
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
                tables = await cur.fetchall()
                logger.info(f"PostgreSQL tables found: {[t['tablename'] for t in tables]}")

            logger.info("Using AsyncPostgresSaver with async pool for persistence")
            return checkpointer
        except Exception as e:
            logger.warning(f"Postgres connection failed: {e}, falling back to MemorySaver")

    logger.info("Using in-memory checkpointer (data lost on restart)")
    return MemorySaver()


# Cached graph instance
_cached_graph = None


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
