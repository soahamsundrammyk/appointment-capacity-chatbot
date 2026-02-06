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


def get_checkpointer():
    """
    Get the appropriate checkpointer.

    Uses PostgreSQL when POSTGRES_CONNECTION_STRING is set (production).
    Falls back to MemorySaver for local development.
    """
    postgres_conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if postgres_conn_string:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool
            import psycopg

            # Add connection timeout if not specified
            conn_params = postgres_conn_string
            if "connect_timeout" not in conn_params:
                separator = "&" if "?" in conn_params else "?"
                conn_params = f"{conn_params}{separator}connect_timeout=10"

            pool = ConnectionPool(
                conninfo=conn_params,
                min_size=1,
                max_size=10,
                timeout=30,
            )

            # Setup tables (only on first connection)
            setup_conn = psycopg.connect(conn_params, autocommit=True, connect_timeout=10)
            setup_checkpointer = PostgresSaver(conn=setup_conn)
            setup_checkpointer.setup()
            setup_conn.close()

            checkpointer = PostgresSaver(conn=pool)
            logger.info("Using Postgres checkpointer for persistence")
            return checkpointer
        except Exception as e:
            logger.warning(f"Postgres connection failed: {e}, falling back to MemorySaver")

    logger.info("Using in-memory checkpointer (data lost on restart)")
    return MemorySaver()


# Cached graph instance
_cached_graph = None


def get_graph():
    """
    Get the compiled graph with checkpointer.
    """
    global _cached_graph
    if _cached_graph is None:
        builder = build_graph()
        checkpointer = get_checkpointer()
        _cached_graph = builder.compile(checkpointer=checkpointer)
        logger.info("Graph compiled with checkpointer")
    return _cached_graph


# Module-level graph export for langgraph CLI (required by langgraph.json)
# This is used by `langgraph dev` command
graph = build_graph().compile()
