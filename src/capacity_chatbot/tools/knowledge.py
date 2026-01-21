"""Knowledge base tool for answering conceptual and how-to questions."""

import logging

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from capacity_chatbot.knowledge_base import get_relevant_knowledge

logger = logging.getLogger(__name__)


@tool
async def get_knowledge_answer(
    query: str,
    config: RunnableConfig = None,
) -> str:
    """Search the knowledge base for answers to conceptual and how-to questions.
    
    Use this tool when the user asks:
    
    CONCEPTUAL QUESTIONS:
    - "What is capacity?"
    - "How do capacity rules work?"
    - "What is a transport option?"
    - "What are teams?"
    
    HOW-TO QUESTIONS (after identifying bottleneck from get_capacity):
    - "How do I increase transport option capacity?" → query with bottleneck type
    - "How do I modify advisor schedule?"
    - "How do I create a capacity rule?"
    - "How do I change team assignments?"
    
    Args:
        query: The user's question (be specific about entity type for how-to questions)
        config: RunnableConfig (automatically provided)
    
    Returns:
        Step-by-step instructions from the knowledge base
    """
    if not query:
        return "Please provide a question to search the knowledge base."
    
    logger.info(f"get_knowledge_answer called with query: {query}")
    
    relevant_knowledge = get_relevant_knowledge(query, max_items=3)
    
    if relevant_knowledge:
        return relevant_knowledge
    
    return """I couldn't find a specific answer in the knowledge base.

The knowledge base covers:
- What is capacity?
- How do capacity rules work?
- What is a transport option/team?
- How to increase capacity limits
- How to create/modify rules

Try rephrasing your question."""


KNOWLEDGE_TOOLS = [
    get_knowledge_answer,
]
