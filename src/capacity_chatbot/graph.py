"""Define the capacity chatbot graph using LangGraph."""

import logging
import os
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from capacity_chatbot.state import CapacityChatbotState, InputState
from capacity_chatbot.nodes.capacity_agent import capacity_agent

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Define the graph
builder = StateGraph(CapacityChatbotState, input_schema=InputState)

# Add nodes
builder.add_node("capacity_agent", capacity_agent)

# Set entry point
builder.add_edge("__start__", "capacity_agent")

# Capacity agent handles everything (ReAct - single LLM call with reasoning loop)
builder.add_edge("capacity_agent", END)

# Initialize SQLite checkpointer for conversation storage
db_path = os.getenv("SQLITE_DB_PATH", "./data/checkpoints.sqlite")
logger.info(f"Initializing SQLite checkpointer at: {db_path}")

# Ensure the directory exists for the database file
db_dir = os.path.dirname(os.path.abspath(db_path))
if db_dir and not os.path.exists(db_dir):
    os.makedirs(db_dir, exist_ok=True)
    logger.info(f"Created directory for checkpointer: {db_dir}")

# Create checkpointer (sync - works with langgraph dev)
checkpointer = SqliteSaver.from_conn_string(db_path)

# Compile the graph with checkpointer
graph = builder.compile(checkpointer=checkpointer)

logger.info("Capacity chatbot graph compiled successfully")

