"""Knowledge base for capacity chatbot - stores common questions and documentation."""

from typing import List, Dict, Any, Optional

# Common questions users can ask (knowledge-based, no API calls needed)
COMMON_QUESTIONS: List[Dict[str, str]] = [
    {
        "question": "What is capacity?",
        "answer": "Capacity refers to the maximum number of appointments that can be scheduled for a given time period, advisor, team, or transport option. It's controlled by capacity rules that set limits based on various conditions.",
        "category": "concept",
        "keywords": ["capacity", "what is", "definition"]
    },
    {
        "question": "How do capacity rules work?",
        "answer": "Capacity rules define when and how many appointments can be scheduled. They have three parts: 1) Applicability Clause (when the rule applies - date, day, time), 2) If Clauses (conditions like team, advisor, transport option), 3) Then Clauses (the capacity limit - e.g., max appointments per day/slot).",
        "category": "rules",
        "keywords": ["rules", "how do", "work", "capacity rules"]
    },
    {
        "question": "What is a transport option?",
        "answer": "Transport options are ways customers can get to/from the service department. Examples include: Loaner (loaner vehicle), Shuttle (shuttle service), Rental (rental car), Will Wait (customer waits), Pickup and Delivery, Uber, etc. Each transport option can have its own capacity limits.",
        "category": "concept",
        "keywords": ["transport", "option", "loaner", "shuttle"]
    },
    {
        "question": "What is a team?",
        "answer": "A team is a group of service advisors who work together. Teams can have their own capacity rules. Examples: Main Shop, Express Shop, Rotation Shop. Each team can have multiple advisors assigned to it.",
        "category": "concept",
        "keywords": ["team", "teams", "advisor group"]
    },
    {
        "question": "How do I increase transport option capacity?",
        "answer": "To increase transport option capacity (e.g., Loaner, Shuttle): 1) Go to Settings > Appointments > Transport Options, 2) Select the transport option from the dropdown menu, 3) In the capacity configuration section at the bottom, increase the limit, 4) You can set limits per day of the week or for specific dates, 5) Click 'Allow changes only for selected dates' for date-specific changes. The current limit is shown in the diagnostics when you fetch capacity data.",
        "category": "how-to",
        "keywords": ["increase", "transport", "option", "capacity", "limit", "how to", "change", "modify", "loaner", "shuttle"]
    },
    {
        "question": "How do I increase capacity limited by a capacity rule?",
        "answer": "To increase capacity limited by a capacity rule: 1) Go to Settings > Capacity Rules (or Rules Management), 2) Find the rule that's limiting capacity (the rule name is shown in diagnostics), 3) Edit the rule's 'Then' clause to increase the capacity limit, 4) The limit is set in the TOTAL_APPOINTMENT_COUNT field. Increase this value in the rule's Then clause to allow more appointments.",
        "category": "how-to",
        "keywords": ["increase", "capacity", "rule", "limit", "how to", "change", "modify", "capacity rule"]
    },
    {
        "question": "How do I increase dealer schedule capacity?",
        "answer": "To increase capacity limited by dealer schedule: 1) Go to Settings > Appointments > Dealer Schedule, 2) Find the day in the grid view (Sunday-Saturday), 3) Increase the appointment limit for that day, 4) For date-specific changes, toggle 'Allow Changes Only for Selected Dates'. Increase this value in the dealer schedule grid to allow more appointments.",
        "category": "how-to",
        "keywords": ["increase", "dealer", "schedule", "capacity", "limit", "how to", "change", "modify"]
    },
    {
        "question": "How do I increase individual advisor schedule capacity?",
        "answer": "To increase capacity limited by individual advisor schedule: 1) Go to Settings > Appointments > Individuals, 2) Select the advisor from the list, 3) In the grid view, increase the appointment limit for the specific day, 4) For date-specific changes, toggle 'Allow Changes Only for Selected Dates'. Increase this value in the individual schedule grid to allow more appointments.",
        "category": "how-to",
        "keywords": ["increase", "individual", "advisor", "schedule", "capacity", "limit", "how to", "change", "modify"]
    },
    {
        "question": "How do I increase operation/opcode capacity limit?",
        "answer": "To increase capacity limited by operation/opcode limit: 1) Go to Settings > Operations/Opcode Settings, 2) Find the operation/opcode that's limiting capacity, 3) Increase the appointment count limit for that operation. Increase this value in the operation settings to allow more appointments.",
        "category": "how-to",
        "keywords": ["increase", "operation", "opcode", "capacity", "limit", "how to", "change", "modify"]
    },
]

# Short summary version (for fast queries)
KNOWLEDGE_SUMMARY = """You are a capacity chatbot assistant. Key concepts:
- Capacity = max appointments per time period/advisor/team/transport
- Capacity Rules = define when/how many appointments (Applicability + If + Then clauses)
- Transport Options = ways customers get to/from service (Loaner, Shuttle, etc.)
- Teams = groups of advisors (Main Shop, Express Shop, etc.)
- Use get_rules tool to fetch current rules
- Use get_capacity tool to fetch current capacity data (includes actionable "HOW TO INCREASE CAPACITY" advice)
- Answer concept questions from knowledge, use tools for current data queries
- IMPORTANT: When users ask follow-up questions like "how do I increase it?", check previous tool responses for specific actionable advice before generating generic responses."""

# Additional knowledge documentation (can be expanded)
# NOTE: If you have the full KNOWLEDGE_DOCUMENTATION dict with all sections,
# it will be included when condensed=False
KNOWLEDGE_DOCUMENTATION: Dict[str, str] = {
    # Add your documentation sections here if needed
    # Example structure:
    # "capacity_concepts": "...",
    # "rule_structure": "...",
    # etc.
}

def get_knowledge_base_section(condensed: bool = True) -> str:
    """Generate the knowledge base section for the system prompt.
    
    Args:
        condensed: If True, use short summary. If False, include full Q&A list.
                   Default True for better performance.
    
    Returns:
        Formatted string containing knowledge base content
    """
    if condensed:
        # Use short summary for better latency
        return KNOWLEDGE_SUMMARY
    
    # Full knowledge base (only use when needed)
    sections = []
    
    # Add common questions
    sections.append("=== COMMON QUESTIONS & ANSWERS ===")
    sections.append("Users frequently ask these questions. Answer them directly using this knowledge (no API calls needed):")
    sections.append("")
    
    for i, qa in enumerate(COMMON_QUESTIONS, 1):
        sections.append(f"Q{i}: {qa['question']}")
        sections.append(f"A{i}: {qa['answer']}")
        sections.append("")
    
    # Add documentation sections (if available)
    if KNOWLEDGE_DOCUMENTATION:
        sections.append("=== ADDITIONAL KNOWLEDGE ===")
        for key, content in KNOWLEDGE_DOCUMENTATION.items():
            sections.append(content.strip())
            sections.append("")
    
    return "\n".join(sections)


def get_relevant_knowledge(user_query: str, max_items: int = 5) -> str:
    """Get only relevant knowledge base items based on user query.
    
    This uses simple keyword matching. For better results, consider using
    semantic search or embeddings.
    
    Args:
        user_query: User's query text
        max_items: Maximum number of Q&A items to include
    
    Returns:
        Formatted string with relevant knowledge only
    """
    query_lower = user_query.lower()
    relevant_items = []
    
    # Simple keyword matching
    for qa in COMMON_QUESTIONS:
        # Check if query matches question or answer keywords
        question_lower = qa.get("question", "").lower()
        answer_lower = qa.get("answer", "").lower()
        keywords = qa.get("keywords", [])
        
        # Check for matches
        matches = False
        for keyword in keywords:
            if keyword.lower() in query_lower:
                matches = True
                break
        
        if matches or any(word in question_lower for word in query_lower.split() if len(word) > 3):
            relevant_items.append(qa)
            if len(relevant_items) >= max_items:
                break
    
    if not relevant_items:
        # Fallback to summary if no matches
        return KNOWLEDGE_SUMMARY
    
    # Format relevant items
    sections = ["=== RELEVANT KNOWLEDGE ==="]
    for i, qa in enumerate(relevant_items, 1):
        sections.append(f"Q{i}: {qa['question']}")
        sections.append(f"A{i}: {qa['answer']}")
        sections.append("")
    
    return "\n".join(sections)


def get_question_examples() -> str:
    """Get example questions users might ask.
    
    Returns:
        Formatted string with example questions
    """
    questions = [qa["question"] for qa in COMMON_QUESTIONS]
    return "\n".join([f"- {q}" for q in questions[:10]])  # Show first 10 as examples


# You can extend this by loading from external files
def load_knowledge_from_file(file_path: str) -> None:
    """Load additional knowledge from a file (e.g., markdown, JSON).
    
    Args:
        file_path: Path to knowledge file
    """
    # TODO: Implement file loading if needed
    pass
