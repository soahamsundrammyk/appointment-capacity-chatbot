"""Capacity chatbot graph definition."""

import logging
import os

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from capacity_chatbot.state import CapacityChatbotState, InputState, OutputState
from capacity_chatbot.nodes.capacity_agent import capacity_agent

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


# Global connection pool for Postgres checkpointer
_postgres_pool = None


def get_checkpointer():
    """
    Get the appropriate checkpointer based on configuration.
    
    Returns PostgresSaver if POSTGRES_CONNECTION_STRING is configured, 
    otherwise MemorySaver for local development.
    """
    global _postgres_pool
    
    postgres_conn_string = os.getenv("POSTGRES_CONNECTION_STRING")
    
    if postgres_conn_string:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            from psycopg_pool import ConnectionPool
            import psycopg
            
            # Create a persistent connection pool (only once)
            if _postgres_pool is None:
                _postgres_pool = ConnectionPool(
                    conninfo=postgres_conn_string,
                    min_size=1,
                    max_size=10,
                )
                
                # Setup tables using a direct connection with autocommit
                # CREATE INDEX CONCURRENTLY cannot run inside a transaction block
                try:
                    setup_conn = psycopg.connect(postgres_conn_string, autocommit=True)
                    setup_checkpointer = PostgresSaver(conn=setup_conn)
                    setup_checkpointer.setup()  # Create required tables
                    setup_conn.close()
                    logger.info("Postgres checkpointer tables initialized")
                except Exception as setup_error:
                    # If setup fails, log but continue (tables might already exist)
                    logger.warning(f"Postgres setup had issues (may already be initialized): {setup_error}")
            
            # Create checkpointer with the pool (for actual operations)
            checkpointer = PostgresSaver(conn=_postgres_pool)
            
            logger.info("Using Postgres checkpointer for persistence")
            return checkpointer
        except ImportError as e:
            logger.warning(f"Missing package: {e}, falling back to MemorySaver")
        except Exception as e:
            logger.error(f"Postgres connection failed: {e}, falling back to MemorySaver")
    
    logger.info("Using in-memory checkpointer (data lost on restart)")
    return MemorySaver()


# Cached graph instance to preserve memory across requests
_cached_graph = None


def get_graph():
    """
    Get the default compiled graph with persistence.
    
    Returns the cached graph instance to ensure checkpointer persists.
    Uses PostgreSQL if configured, otherwise falls back to MemorySaver.
    
    Returns:
        Compiled LangGraph
    """
    global _cached_graph
    if _cached_graph is None:
        builder = build_graph()
        checkpointer = get_checkpointer()
        _cached_graph = builder.compile(checkpointer=checkpointer)
        logger.info("Graph compiled with checkpointer")
    return _cached_graph


# For backward compatibility - compile without checkpointer for langgraph CLI
# (though we'll use custom FastAPI server now)
graph = build_graph().compile()



