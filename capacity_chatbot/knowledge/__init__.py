"""Knowledge base module for capacity chatbot."""
from pathlib import Path

from capacity_chatbot.knowledge.knowledge_store import get_relevant_knowledge
from capacity_chatbot.knowledge.loader import load_kb

_KB_DIR = Path(__file__).parent / "kb"
KB = load_kb(_KB_DIR)

__all__ = ["KB", "get_relevant_knowledge"]
