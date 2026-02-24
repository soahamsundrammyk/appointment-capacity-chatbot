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

## API Endpoints

When the app is mounted at `MOUNT_PREFIX` (default `/capacity-chatbot`):

| Method | Path | Description |
|--------|------|-------------|
| GET | `{MOUNT_PREFIX}/ok` | Health check |
| POST | `{MOUNT_PREFIX}/threads/{thread_id}/runs/stream` | Stream a chat run (SSE). Requires valid session (e.g. Bearer token with mkid when `ENABLE_MKID_AUTH` is true). |

Request body for the stream endpoint: `RunRequest` with `input` (messages, optional `department_uuid`, `dealer_uuid`, `cached_data`) and optional `stream_mode`.

## UI Client Integration

The chatbot uses the following from the UI client (in the request body and/or from auth session):

| Field | Description |
|-------|-------------|
| `department_uuid` | Department UUID for API calls (body or session) |
| `dealer_uuid` | Dealer UUID for opcode search (body or session) |
| `mkid` | MyKaarma ID; from request body or from Bearer token when auth is enabled |
| `cached_data` | Transport options, advisors, teams (from request body) |

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
├── tools/                # LangChain tool wrappers
│   ├── capacity.py
│   ├── rules.py
│   ├── opcode.py
│   ├── first_available_slot.py
│   ├── entities.py
│   └── knowledge.py
├── nodes/                # Graph nodes
│   └── capacity_agent.py # ReAct agent node
├── knowledge/            # Knowledge base (Q&A database)
│   └── knowledge_store.py
├── enums/                # Domain constants and type definitions
│   └── enums.py          # Enumerations (DayName, FilterField, etc.)
├── model/                # Data models
│   └── requests.py       # Request/Response models (RunInput, RunRequest)
└── utils/                # Pure utility functions
    ├── date_parser.py
    ├── uuid_mapper.py
    ├── state_extractor.py
    ├── validation.py     # Entity name validation (used by tools)
    └── test_data.py      # Test/sample data helpers for local dev
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `LANGSMITH_API_KEY` | LangSmith persistence and monitoring |
| `APPOINTMENT_CAPACITY_CHATBOT_USERNAME` | Service subscriber username for KAppointment/KManage API auth |
| `APPOINTMENT_CAPACITY_CHATBOT_PASSWORD` | Service subscriber password for API auth |

### Optional (API and backends)

| Variable | Description | Default |
|----------|-------------|---------|
| `KAPPOINTMENT_API_BASE_URL` | KAppointment API base URL (includes `/appointment/v2` path) | `https://srishti244.mykaarma.dev/appointment/v2` |
| `KMANAGE_API_URL` | KManage API URL for authentication | `https://srishti244.mykaarma.dev/manage/v2` |
| `PORT` | Server port when running via `python -m capacity_chatbot.api.routes` | `3334` |
| `MOUNT_PREFIX` | URL prefix for routes (e.g. health at `{MOUNT_PREFIX}/ok`) | `/capacity-chatbot` |
| `ENABLE_MKID_AUTH` | Enable Bearer-token (mkid) auth via KManage; set to `false` to skip auth | `true` |
| `MODEL` | Primary Claude model for the agent (e.g. `claude-sonnet-4-5-20250929`) | `claude-sonnet-4-5-20250929` |
| `FALLBACK_MODEL` | Claude model used when the primary times out or errors | `claude-3-5-haiku-20241022` |

**Note**: In production/QA/GVM, these are set via Kubernetes ConfigMaps and Secrets, not `.env` files.

### Testing (local / LangSmith)

Used only when the UI client does not send values; in production, context comes from the UI client.

| Variable | Description |
|----------|-------------|
| `TEST_DEALER_UUID` | Dealer UUID fallback for testing |
| `TEST_DEPARTMENT_UUID` | Department UUID fallback for testing |
| `TEST_MKID` | MKID fallback for testing |
| `TEST_DATA_PATH` | Path to JSON file with sample cached data (advisors, teams, transport options) |

## Development

```bash
# Run with auto-reload
langgraph dev

# Run tests (when added)
pytest tests/
```

## Deployment

```bash
# Production deployment with LangSmith persistence
langgraph up --host 0.0.0.0 --port 3334
```
