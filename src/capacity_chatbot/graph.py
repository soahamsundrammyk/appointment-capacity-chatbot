"""Define the capacity chatbot graph using LangGraph."""

import logging
import os
from typing import Literal

from langgraph.graph import StateGraph, END

from capacity_chatbot.state import CapacityChatbotState, InputState, OutputState
from capacity_chatbot.nodes.capacity_agent import capacity_agent

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# Define the graph with input and output schemas
builder = StateGraph(
    CapacityChatbotState,
    input_schema=InputState,
    output_schema=OutputState
)

# Add nodes
builder.add_node("capacity_agent", capacity_agent)

# Set entry point
builder.add_edge("__start__", "capacity_agent")

# Capacity agent handles everything (ReAct - single LLM call with reasoning loop)
builder.add_edge("capacity_agent", END)

# Compile the graph - LangGraph API handles checkpointing automatically
graph = builder.compile()

logger.info("Capacity chatbot graph compiled successfully")
