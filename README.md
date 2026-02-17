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
capacity_chatbot/
├── graph.py              # LangGraph graph definition
├── state.py              # Input/Output state definitions
├── prompts.py            # System prompts
├── api/                  # API layer
│   ├── routes.py         # FastAPI routes and endpoints
│   └── middleware/       # API middleware
│       └── auth.py       # Authentication middleware
├── config/               # Configuration management
│   └── api_config.py    # API client configuration
├── clients/              # External API clients
│   ├── kappointment_client.py  # KAppointment API client
│   └── kmanage_client.py       # KManage API client (for auth)
├── services/             # Business logic layer (planned - currently empty)
├── tools/                # LangChain tool wrappers (thin layer)
│   ├── capacity.py
│   ├── rules.py
│   ├── opcode.py
│   ├── first_available_slot.py
│   ├── entities.py
│   ├── knowledge.py
│   └── validation.py
├── nodes/                # Graph nodes
│   └── capacity_agent.py # ReAct agent node
├── knowledge/            # Knowledge base (Q&A database)
│   └── knowledge_store.py
├── enums/                # Domain constants and type definitions
│   └── enums.py          # Enumerations (EntityType, DayName, etc.)
├── model/                # Data models
│   └── requests.py       # Request/Response models (RunInput, RunRequest)
└── utils/                # Pure utility functions
    ├── date_parser.py
    └── uuid_mapper.py
```

## Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key | - |
| `LANGSMITH_API_KEY` | Yes | For persistence | - |
| `KAPPOINTMENT_API_BASE_URL` | No | KAppointment API base URL (includes `/appointment/v2` path) | `https://srishti244.mykaarma.dev/appointment/v2` |
| `KMANAGE_API_URL` | No | KManage API URL for authentication | `https://srishti244.mykaarma.dev/manage/v2` |
| `APPOINTMENT_CAPACITY_CHATBOT_USERNAME` | Yes | Service subscriber username for API auth | - |
| `APPOINTMENT_CAPACITY_CHATBOT_PASSWORD` | Yes | Service subscriber password for API auth | - |

**Note**: In production/QA/GVM, these environment variables are set via Kubernetes ConfigMaps and Secrets, not in `.env` files. 

### Testing Configuration (Local/LangSmith Only)

For local testing and LangSmith integration, you can set these optional environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `TEST_DEALER_UUID` | No | Dealer UUID for testing (fallback if UI client doesn't provide) |
| `TEST_DEPARTMENT_UUID` | No | Department UUID for testing (fallback if UI client doesn't provide) |
| `TEST_MKID` | No | MKID for testing (fallback if UI client doesn't provide) |
| `TEST_DATA_PATH` | No | Path to JSON file with sample cached data (advisors, teams, transport options) |

**⚠️ Note**: These test variables are ONLY used when the UI client doesn't provide values. In production, all values come from the UI client. See `ENV_SETUP.md` for detailed setup instructions.

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
