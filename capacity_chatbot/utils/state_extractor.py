"""Utility for extracting state from LangGraph RunnableConfig."""

from langchain_core.runnables import RunnableConfig

from capacity_chatbot.state import CapacityChatbotState


def extract_state(config: RunnableConfig) -> tuple[CapacityChatbotState | None, str | None]:
    """Extract and validate state from config.

    Args:
        config: LangGraph RunnableConfig containing state

    Returns:
        Tuple of (state, error_message). If successful, error_message is None.
    """
    if not config:
        return None, "Error: Config not available"

    state: CapacityChatbotState = config.get("configurable", {}).get("state")
    if not state:
        return None, "Error: State not available"

    if not state.department_uuid:
        return (
            None,
            "Error: Department UUID is required. Please ensure the UI client provides this value.",
        )

    return state, None
