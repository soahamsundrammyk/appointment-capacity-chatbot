# Capacity Chatbot Service

AI-powered chatbot for answering capacity-related questions for automotive service departments.

## Quick Start

```bash
# 1. Install dependencies
pip install -e ".[dev]"

# 2. Configure environment
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY and LANGSMITH_API_KEY

# 3. Start the service
langgraph up
```

Service runs at `http://localhost:3334`

## Features

- 🤖 Natural language interface for capacity queries
- 🔍 Smart tool orchestration (get_capacity, get_rules, search_opcode, etc.)
- 📊 LangSmith integration for monitoring and persistence
- 🤝 **Requires integration with appointment-ui-client**

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  appointment-   │────▶│  capacity-       │────▶│  kappointment-api  │
│  ui-client      │◀────│  chatbot-service │◀────│                    │
└─────────────────┘     └──────────────────┘     └────────────────────┘
      │                         │
      │                         ▼
      │                  ┌──────────────┐
      │                  │ Claude LLM   │
      │                  │ (Anthropic)  │
      │                  └──────────────┘
      │
      └──── Provides: department_uuid, dealer_uuid, mkid, cached_data
```

## UI Client Integration

The chatbot **requires** the following from the UI client in each request:

| Field | Description |
|-------|-------------|
| `department_uuid` | Department UUID for API calls |
| `dealer_uuid` | Dealer UUID for opcode search |
| `mkid` | Authentication cookie |
| `cached_data` | Transport options, advisors, teams |

## Project Structure

```
src/capacity_chatbot/
├── graph.py              # LangGraph graph definition
├── state.py              # Input/Output state definitions
├── prompts.py            # System prompts
├── config.py             # API configuration
├── knowledge_base.py     # RAG knowledge base
├── nodes/
│   └── capacity_agent.py # ReAct agent node
├── clients/
│   ├── kappointment_client.py
│   └── kopcode_client.py
├── tools/
│   ├── capacity.py
│   ├── rules.py
│   ├── opcode.py
│   ├── first_available_slot.py
│   ├── entities.py
│   └── knowledge.py
└── utils/
    ├── date_parser.py
    ├── uuid_mapper.py
    └── enums.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `LANGSMITH_API_KEY` | Yes | For persistence |
| `KAPPOINTMENT_API_BASE_URL` | Yes | API server URL |
| `LOG_LEVEL` | No | Default: INFO |

## Development

```bash
# Run with auto-reload
langgraph dev

# Run tests
pytest tests/
```

## Deployment

```bash
# Production deployment with LangSmith persistence
langgraph up --host 0.0.0.0 --port 3334
```
