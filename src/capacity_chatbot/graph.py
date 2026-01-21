"""Capacity chatbot graph definition."""

import logging
import os

from langgraph.graph import StateGraph, END

from capacity_chatbot.state import CapacityChatbotState, InputState, OutputState
from capacity_chatbot.nodes.capacity_agent import capacity_agent

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

builder = StateGraph(
    CapacityChatbotState,
    input_schema=InputState,
    output_schema=OutputState
)

builder.add_node("capacity_agent", capacity_agent)
builder.add_edge("__start__", "capacity_agent")
builder.add_edge("capacity_agent", END)

graph = builder.compile()

logger.info("Graph compiled")
