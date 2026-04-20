"""Capacity agent node using ReAct architecture."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt import create_react_agent

from capacity_chatbot.knowledge import KB
from capacity_chatbot.knowledge.prompt_builder import build_system_messages
from capacity_chatbot.prompts import get_capacity_agent_system_prompt
from capacity_chatbot.state import CapacityChatbotState
from capacity_chatbot.tools import CAPACITY_TOOLS
from capacity_chatbot.utils.test_data import ensure_cached_data, ensure_state_uuids

logger = logging.getLogger(__name__)

RECURSION_LIMIT = 12
ERROR_MESSAGE = "I apologize, but something went wrong. Please contact the dealership directly and the team will help you out."

# Cap messages sent to the model each turn to avoid unbounded growth (P0 production fix).
# Each turn can add 5–7 messages (human + AI tool_calls + ToolMessage + … + final AI).
# Without a cap: token cost and latency grow per turn and can hit context window limit.
DEFAULT_MAX_AGENT_MESSAGES = 24  # ~8–12 conversation turns of context

# Cached primary model instance (loaded once, reused across invocations)
_cached_model: ChatAnthropic | None = None


def _get_model_name() -> str:
    """Get primary model name from environment variable."""
    return os.getenv("MODEL", "claude-sonnet-4-5-20250929")


def _get_fallback_model_name() -> str:
    """Get fallback model name (env or default Haiku). Used when primary times out or errors."""
    return os.getenv("FALLBACK_MODEL", "claude-3-5-haiku-20241022")


def _get_max_agent_messages() -> int:
    """Max messages to send to the model per turn (sliding window). Prevents unbounded history."""
    raw = os.getenv("AGENT_MAX_MESSAGES", str(DEFAULT_MAX_AGENT_MESSAGES))
    try:
        n = int(raw)
        return max(6, min(n, 200))  # clamp to [6, 200]
    except ValueError:
        return DEFAULT_MAX_AGENT_MESSAGES


def _trim_messages_for_agent(messages: list, max_messages: int) -> list:
    """Keep all human messages and final AI replies; drop tool calls and ToolMessages. Then apply cap."""
    filtered: list = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            filtered.append(msg)
        elif isinstance(msg, ToolMessage):
            continue  # drop tool call results
        elif isinstance(msg, AIMessage):
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                continue  # drop AI messages that are only/mostly tool_calls
            if msg.content:
                filtered.append(msg)
            # else skip empty AI message
        else:
            filtered.append(msg)  # keep other message types (e.g. system) if any
    if len(filtered) <= max_messages:
        result = list(filtered)
    else:
        result = list(filtered[-max_messages:])
        logger.info(
            "Trimmed message history: %d (from %d raw) -> %d messages (AGENT_MAX_MESSAGES=%d)",
            len(filtered),
            len(messages),
            len(result),
            max_messages,
        )
    return result


def _build_model(model_name: str) -> ChatAnthropic:
    """Build a ChatAnthropic instance for the given model name (no caching)."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable is required")
    return ChatAnthropic(model=model_name, temperature=0, api_key=api_key)


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
    """Load primary model from Anthropic (cached, loaded once)."""
    global _cached_model
    if _cached_model is None:
        model_name = _get_model_name()
        logger.info("Loading Anthropic model: %s", model_name)
        _cached_model = _build_model(model_name)
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

    current_time = datetime.now().strftime("%A, %B %d, %Y %I:%M %p")
    behavioral_prompt = get_capacity_agent_system_prompt(current_time=current_time)
    system_blocks = build_system_messages(
        entries=KB,
        tier=state.user_tier,
        behavioral_prompt=behavioral_prompt,
    )
    system_message = SystemMessage(content=system_blocks)
    max_messages = _get_max_agent_messages()
    messages_for_agent = _trim_messages_for_agent(state.messages, max_messages)
    agent_input = {"messages": messages_for_agent}
    agent_config = _create_agent_config(state, config)

    async def _run_agent(model: ChatAnthropic):
        agent = create_react_agent(model, tools=CAPACITY_TOOLS, prompt=system_message)
        return await agent.ainvoke(agent_input, config=agent_config)

    try:
        model = _load_model()
        result = await _run_agent(model)
        final_message = result["messages"][-1].content
        return {
            "assistant_message": final_message,
            "messages": [AIMessage(content=final_message)],
            "response_message": final_message,
        }
    except (Exception, asyncio.TimeoutError) as e:
        fallback_name = _get_fallback_model_name()
        logger.warning(
            "Primary model failed (%s), retrying with fallback: %s",
            e,
            fallback_name,
            exc_info=True,
        )
        try:
            fallback_model = _build_model(fallback_name)
            result = await _run_agent(fallback_model)
            final_message = result["messages"][-1].content
            return {
                "assistant_message": final_message,
                "messages": [AIMessage(content=final_message)],
                "response_message": final_message,
            }
        except Exception as fallback_e:
            logger.error("Fallback model also failed: %s", fallback_e, exc_info=True)
            return {
                "assistant_message": ERROR_MESSAGE,
                "messages": [AIMessage(content=ERROR_MESSAGE)],
                "response_message": ERROR_MESSAGE,
                "errors": [str(fallback_e)],
            }
