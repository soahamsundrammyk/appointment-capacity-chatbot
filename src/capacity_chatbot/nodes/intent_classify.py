"""Node for classifying user intent."""

import logging
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from capacity_chatbot.state import CapacityChatbotState

logger = logging.getLogger(__name__)


def intent_classify(state: CapacityChatbotState) -> CapacityChatbotState:
    """Classify user intent based on message and extracted entities.
    
    Intent types:
    - simple_capacity: "What's the capacity for tomorrow?"
    - schedule_query: "When is Advisor A available?"
    - diagnostic_query: "Why can't I book a loaner?" (requires investigation)
    """
    # Get the latest user message
    user_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
    if not user_messages:
        state.errors.append("No user message found for intent classification")
        return state
    
    latest_message = user_messages[-1].content
    entities = state.extracted_entities
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Create prompt for intent classification
    prompt = f"""Classify the user's intent based on their message and extracted entities.

User message: {latest_message}
Extracted entities: {entities}

Intent types:
1. "simple_capacity" - Asking about capacity numbers (e.g., "What's the capacity?", "How many slots available?")
2. "rules_query" - Asking about rules (e.g., "What are the rules?", "Fetch all rules", "Show me the capacity rules")
3. "tool_calling" - General query that might need tool calling (e.g., "fetch rules", "get capacity")
4. "diagnostic_query" - Asking "why" questions or investigating unavailability (e.g., "Why can't I book?", "Why is it unavailable?")

Respond with ONLY one word: simple_capacity, schedule_query, or diagnostic_query
"""
    
    try:
        response = llm.invoke(prompt)
        intent = response.content.strip().lower()
        
        # Validate intent
        valid_intents = ["simple_capacity", "rules_query", "tool_calling", "diagnostic_query"]
        if intent not in valid_intents:
            # Default to simple_capacity if unclear
            intent = "simple_capacity"
            logger.warning(f"Invalid intent '{response.content}', defaulting to simple_capacity")
        
        state.parsed_intent = intent
        state.reasoning.append(f"Classified intent: {intent}")
        logger.info(f"Classified intent: {intent}")
        
    except Exception as e:
        logger.error(f"Error classifying intent: {e}")
        state.errors.append(f"Error classifying intent: {str(e)}")
        # Default to simple_capacity on error
        state.parsed_intent = "simple_capacity"
    
    return state


def route_after_intent(state: CapacityChatbotState) -> Literal["call_capacity_tool", "call_rules_tool", "tool_calling_node", "compose_response"]:
    """Route to appropriate node based on classified intent."""
    intent = state.parsed_intent
    
    if intent == "simple_capacity":
        return "call_capacity_tool"
    elif intent == "rules_query":
        return "call_rules_tool"
    elif intent == "tool_calling":
        return "tool_calling_node"
    else:  # diagnostic_query - for now, use capacity tool (will enhance later)
        return "call_capacity_tool"

