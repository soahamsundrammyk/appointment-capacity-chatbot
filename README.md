# Appointment Chatbot Service

AI-powered chatbot for automotive service departments — answers questions about appointment capacity, rules, scheduling, and appointment data/history.

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

## What It Can Do

**Capacity queries** — "How many slots tomorrow?", "Loaner capacity per advisor?"

**Appointment data** — "How many appointments last month?", "Show me Donald's appointments this week", "Break down by advisor"

**Rules & opcodes** — "What are the capacity rules?", "Search for oil change"

**First available slot** — "When is the next available slot for Loaner?"

**Knowledge base** — "How do I increase capacity?", "What is a limiting factor?"

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  appointment-   │────▶│  appointment-    │────▶│  kappointment-api  │
│  ui-client      │◀────│  chatbot-service │◀────│                    │
└─────────────────┘     └──────────────────┘     └────────────────────┘
      │                     │         │
      │                     ▼         ▼
      │              ┌──────────┐  ┌──────────────────────┐
      │              │ Claude   │  │ MongoDB               │
      │              │ (LLM)   │  │ AppointmentViewData   │
      │              └──────────┘  └──────────────────────┘
      │
      └──── Provides: department_uuid, dealer_uuid, mkid, cached_data
```

**Single-node LangGraph ReAct agent** with 8 tools. The agent decides which tools to call based on the user's question.

### Data Sources

| Data | Source | Endpoint |
|------|--------|----------|
| Capacity, rules, slots, opcodes | Aurora (MySQL) | `POST /department/{uuid}/capacity`, etc. |
| Appointment history & data | MongoDB `AppointmentViewData` | `POST /webservice/dealers/{uuid}/appointments` |
| Chat thread persistence | PostgreSQL | LangGraph checkpointer |

The appointment data tool uses the **same MongoDB endpoint as the appointment-ui-client**, ensuring data consistency between the chatbot and the UI.

## Tools

| Tool | Description |
|------|-------------|
| `get_appointments_tool` | Query appointment data with 11 filter types (advisor, team, status, source, transport, etc.). Summary or list mode. |
| `get_capacity_tool` | Check available vs booked appointment slots with filters |
| `get_rules_tool` | View capacity and assignment rules |
| `get_first_available_slot_tool` | Find next open appointment slot |
| `search_opcode_tool` | Search services/opcodes, view daily limits |
| `get_available_entities` | List advisors, teams, transport options |
| `confirm_entity` | Validate entity names with fuzzy matching |
| `get_knowledge_answer` | Search knowledge base for how-to answers |

## API Endpoints

Mounted at `MOUNT_PREFIX` (default `/capacity-chatbot`):

| Method | Path | Description |
|--------|------|-------------|
| GET | `{prefix}/ok` | Health check |
| POST | `{prefix}/threads/{thread_id}/runs/stream` | Stream a chat run (SSE) |
| GET | `{prefix}/threads` | List conversation threads for authenticated user |
| GET | `{prefix}/threads/{thread_id}/history` | Get messages for a thread (ownership enforced) |

## Project Structure

```
capacity_chatbot/
├── graph.py                    # LangGraph graph definition + checkpointer
├── state.py                    # Input/Output state definitions
├── prompts.py                  # System prompt (behavioral rules)
├── chat_history.py             # Thread metadata storage (Postgres)
├── api/
│   ├── routes.py               # FastAPI routes, SSE streaming, friendly tool names
│   └── middleware/
│       └── auth.py             # mkid Bearer token auth via KManage
├── config/
│   └── api_config.py           # API client configuration
├── clients/
│   ├── kappointment_client.py  # KAppointment API client (capacity + Mongo endpoints)
│   └── kmanage_client.py       # KManage API client (auth)
├── tools/
│   ├── appointments.py         # Appointment data query (Mongo endpoint, 11 filters)
│   ├── capacity.py             # Capacity queries
│   ├── rules.py                # Rule queries
│   ├── opcode.py               # Opcode search
│   ├── first_available_slot.py # First available slot
│   ├── entities.py             # Entity listing and validation
│   └── knowledge.py            # Knowledge base search
├── nodes/
│   └── capacity_agent.py       # ReAct agent node
├── knowledge/
│   └── knowledge_store.py      # Embedded Q&A knowledge base
├── enums/
│   └── enums.py                # Domain enums
├── model/
│   └── requests.py             # Request/Response models
└── utils/
    ├── appointment_filters.py  # Client-side filter pipeline (11 filter types)
    ├── appointment_formatter.py # Summary, list, grouped summary formatters
    ├── date_parser.py          # Natural language date parsing + date ranges
    ├── uuid_mapper.py          # UUID → name resolution
    ├── state_extractor.py      # LangGraph state extraction
    ├── validation.py           # Entity name validation (fuzzy matching)
    ├── rule_analysis.py        # Rule conflict detection
    └── test_data.py            # Test/sample data helpers for local dev

tests/
├── test_appointment_filters.py  # Filter pipeline tests (16 tests)
├── test_appointment_formatter.py # Formatter tests (7 tests)
└── test_date_parser.py          # Date range parsing tests (15 tests)
```

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `LANGSMITH_API_KEY` | LangSmith monitoring |
| `APPOINTMENT_CAPACITY_CHATBOT_USERNAME` | Service subscriber username for API auth |
| `APPOINTMENT_CAPACITY_CHATBOT_PASSWORD` | Service subscriber password for API auth |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `KAPPOINTMENT_API_BASE_URL` | KAppointment API base URL | `https://app.mykaarma.com/appointment/v2` |
| `KMANAGE_API_URL` | KManage API URL for auth | `https://srishti244.mykaarma.dev/manage/v2` |
| `MYKAARMA_MKID` | Fallback mkid for webservice endpoints (when auth disabled) | — |
| `POSTGRES_CONNECTION_STRING` | PostgreSQL for thread persistence | — (uses in-memory) |
| `PORT` | Server port | `3334` |
| `MOUNT_PREFIX` | URL prefix for routes | `/capacity-chatbot` |
| `ENABLE_MKID_AUTH` | Enable Bearer token auth | `true` |
| `MODEL` | Primary Claude model | `claude-sonnet-4-5-20250929` |
| `FALLBACK_MODEL` | Fallback Claude model | `claude-3-5-haiku-20241022` |

### Testing (local dev)

| Variable | Description |
|----------|-------------|
| `TEST_DEALER_UUID` | Dealer UUID fallback |
| `TEST_DEPARTMENT_UUID` | Department UUID fallback |
| `TEST_MKID` | MKID fallback |
| `TEST_DATA_PATH` | Path to sample cached data JSON |

## Development

```bash
# Run with auto-reload
langgraph dev

# Run tests
pytest tests/ -v
```

## Deployment

```bash
# Docker (GVM/production)
docker-compose up -d --build

# Or direct
langgraph up --host 0.0.0.0 --port 3334
```
