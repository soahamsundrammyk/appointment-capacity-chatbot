"""Node for composing final response to user."""

import logging
from typing import Dict, Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from capacity_chatbot.state import CapacityChatbotState

logger = logging.getLogger(__name__)


def format_capacity_data(capacity_data: Dict[str, Any]) -> str:
    """Format capacity data into readable text for LLM."""
    if not capacity_data:
        return "No capacity data available"
    
    capacity_map = capacity_data.get("capacityMap", {})
    if not capacity_map:
        return "No capacity information found"
    
    formatted = "Capacity Information:\n"
    
    # Extract APPOINTMENT_COUNT data
    appointment_count = capacity_map.get("APPOINTMENT_COUNT", {})
    for date, entity_capacity in appointment_count.items():
        formatted += f"\nDate: {date}\n"
        
        combination_capacity = entity_capacity.get("combinationWiseCapacity", {})
        for key, capacity in combination_capacity.items():
            used = capacity.get("usedCount", 0)
            total = capacity.get("totalCount", 0)
            available = total - used if total != float('inf') else "unlimited"
            
            formatted += f"  {key}: {used} used, {total} total, {available} available\n"
    
    return formatted


def compose_response(state: CapacityChatbotState) -> CapacityChatbotState:
    """Compose human-readable response based on API data."""
    
    # Get the latest user message
    user_messages = [msg for msg in state.messages if isinstance(msg, HumanMessage)]
    user_message = user_messages[-1].content if user_messages else ""
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    # Build context for LLM
    context_parts = []
    
    if state.capacity_data:
        context_parts.append(format_capacity_data(state.capacity_data))
    
    if state.schedule_data:
        context_parts.append(f"Schedule Data: {state.schedule_data}")
    
    if state.errors:
        context_parts.append(f"Errors encountered: {', '.join(state.errors)}")
    
    context = "\n\n".join(context_parts) if context_parts else "No data available"
    
    # Create prompt
    prompt = f"""You are a helpful capacity assistant. Answer the user's question based on the provided data.

User question: {user_message}

Available data:
{context}

Provide a clear, concise, and helpful answer. If there's no data available, explain that politely.
If there are errors, mention them but still try to be helpful.

Response:"""
    
    try:
        response = llm.invoke(prompt)
        state.response_message = response.content
        state.reasoning.append("Composed response using LLM")
        logger.info(f"Composed response: {state.response_message[:100]}...")
        
    except Exception as e:
        logger.error(f"Error composing response: {e}")
        state.errors.append(f"Error composing response: {str(e)}")
        state.response_message = "I apologize, but I encountered an error while processing your request. Please try again."
    
    return state

