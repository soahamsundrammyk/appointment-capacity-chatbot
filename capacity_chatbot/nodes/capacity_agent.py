"""Capacity agent node using ReAct architecture."""

import logging
import os
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from capacity_chatbot.prompts import get_capacity_agent_system_prompt
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools import CAPACITY_TOOLS
from capacity_chatbot.utils.test_data import ensure_cached_data, ensure_state_uuids

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 12
ERROR_MESSAGE = "I apologize, but something went wrong. Please contact the dealership directly and the team will help you out."

# Cached model instance (loaded once, reused across invocations)
_cached_model: ChatAnthropic | None = None


def _get_model_name() -> str:
    """Get model name from environment variable."""
    return os.getenv("MODEL", "claude-sonnet-4-5-20250929")


def _create_agent_config(state: CapacityChatbotState, config: RunnableConfig | None) -> dict:
    """Create config dict for the agent with state and LangSmith metadata."""
    safe_config = {}

    if config:
        # Preserve thread_id, checkpoint info, and mkid from incoming config
        for key in ["thread_id", "checkpoint_ns", "checkpoint_id", "mkid"]:
            if config.get("configurable", {}).get(key):
                safe_config[key] = config["configurable"][key]

    safe_config["state"] = state

    model_name = _get_model_name()
    prompt_version = os.getenv("PROMPT_VERSION", "v1")

    return {
        "configurable": safe_config,
        "recursion_limit": RECURSION_LIMIT,
        "tags": ["approach:react", "model:%s" % model_name, "prompt:%s" % prompt_version],
        "metadata": {
            "model": model_name,
            "approach": "react",
            "prompt_version": prompt_version,
            "timestamp": datetime.now().isoformat(),
        },
    }


def _load_model() -> ChatAnthropic:
    """Load Claude Sonnet model from Anthropic (cached, loaded once)."""
    global _cached_model

    if _cached_model is None:
        model_name = _get_model_name()
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required")

        logger.info("Loading Anthropic model: %s", model_name)
        _cached_model = ChatAnthropic(model=model_name, temperature=0, api_key=api_key)

    return _cached_model


async def capacity_agent(
    state: CapacityChatbotState,
    config: RunnableConfig | None = None,
) -> dict[str, Any]:
    """ReAct capacity agent that uses tools to answer capacity-related queries."""
    logger.info("Capacity agent invoked")

    # Ensure UUIDs are populated from env vars for testing (if not provided by UI client)
    ensure_state_uuids(state)
    ensure_cached_data(state)

    department_uuid = state.department_uuid
    if not department_uuid:
        error_msg = "Department UUID is required. Please ensure the UI client provides department_uuid in the request."
        logger.error(error_msg)
        return {
            "assistant_message": "I need a department UUID to help you. Please ensure you're connected through the appointment UI.",
            "messages": [
                AIMessage(
                    content="I need a department UUID to help you. Please ensure you're connected through the appointment UI."
                )
            ],
            "errors": [error_msg],
        }

    user_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
    if not user_messages:
        error_msg = "No user message found"
        logger.error(error_msg)
        return {
            "assistant_message": "I didn't receive your message. Please try again.",
            "messages": [AIMessage(content="I didn't receive your message. Please try again.")],
            "errors": [error_msg],
        }

    try:
        model = _load_model()
        current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
        system_prompt = get_capacity_agent_system_prompt(current_time=current_time)

        agent = create_react_agent(model, tools=CAPACITY_TOOLS, prompt=system_prompt)
        agent_input = {"messages": list(state.messages)}
        agent_config = _create_agent_config(state, config)

        result = await agent.ainvoke(agent_input, config=agent_config)
        final_message = result["messages"][-1].content

        return {
            "assistant_message": final_message,
            "messages": [AIMessage(content=final_message)],
            "response_message": final_message,
        }

    except Exception as e:
        logger.error("Capacity agent error: %s", e, exc_info=True)
        return {
            "assistant_message": ERROR_MESSAGE,
            "messages": [AIMessage(content=ERROR_MESSAGE)],
            "response_message": ERROR_MESSAGE,
            "errors": [str(e)],
        }
