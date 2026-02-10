# Capacity Chatbot Service

AI-powered chatbot for answering capacity-related questions for automotive service departments. Built with LangGraph and Claude (Anthropic).

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)
- [Project Structure](#project-structure)
- [API Endpoints](#api-endpoints)
- [Tools Reference](#tools-reference)
- [How It Works](#how-it-works)
- [Deployment](#deployment)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Capacity Chatbot is an AI assistant that helps dealership staff understand and manage appointment capacity. It can:

- **Query capacity data** - Show available appointments by date, advisor, transport option, or team
- **Explain capacity rules** - Display and describe capacity and assignment rules in natural language
- **Find available slots** - Locate the first available appointment based on various criteria
- **Search for services** - Find opcodes/services and their daily limits
- **Answer how-to questions** - Provide step-by-step instructions for modifying capacity settings

> **Note:** This is a **READ-ONLY** assistant. It cannot book appointments or modify settings—only view data and explain how users can make changes themselves.

---

## Architecture

```
┌─────────────────────────┐     ┌────────────────────────────┐     ┌────────────────────────┐
│  appointment-ui-client  │────▶│  capacity-chatbot-service  │────▶│    kappointment-api    │
│                         │◀────│        (this repo)         │◀────│                        │
└─────────────────────────┘     └────────────────────────────┘     └────────────────────────┘
         │                                    │
         │                                    ▼
         │                         ┌───────────────────┐
         │                         │ Claude Sonnet LLM │
         │                         │   (Anthropic)     │
         │                         └───────────────────┘
         │
         └────── Provides: department_uuid, dealer_uuid, mkid, cached_data
```

### Component Flow

1. **UI Client** sends a message with context (UUIDs, cached entity data)
2. **FastAPI Server** (`api.py`) receives the request and routes to the graph
3. **LangGraph** (`graph.py`) manages conversation state and orchestrates the agent
4. **ReAct Agent** (`capacity_agent.py`) uses Claude to reason and decide which tools to call
5. **Tools** (`tools/*.py`) make API calls to `kappointment-api` and format responses
6. **Response** flows back to UI with streaming SSE events for real-time updates

---

## Quick Start

### Prerequisites

- Python 3.11+
- Anthropic API key
- Access to kappointment-api (or test data)

### Installation

```bash
# 1. Clone and navigate to the repo
cd appointment-capacity-chatbot

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 4. Start the service
uvicorn capacity_chatbot.api:app --host 0.0.0.0 --port 3334 --reload
```

Service runs at `http://localhost:3334/capacity-chatbot`

### Using Docker

```bash
# Build and run
docker build -t capacity-chatbot .
docker run -p 3334:3334 --env-file .env capacity-chatbot

# Or use docker-compose
docker-compose up
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | Claude API key from Anthropic |
| `LANGSMITH_API_KEY` | ✅ Yes | LangSmith API key for tracing |
| `KAPPOINTMENT_API_BASE_URL` | ✅ Yes | Base URL for kappointment-api (e.g., `https://api.example.com`) |
| `APPOINTMENT_CAPACITY_CHATBOT_USERNAME` | ✅ Yes | Basic auth username for kappointment-api calls |
| `APPOINTMENT_CAPACITY_CHATBOT_PASSWORD` | ✅ Yes | Basic auth password for kappointment-api calls |
| `KMANAGE_API_URL` | Auth | Kmanage API URL for mkid validation (default: `https://api.mykaarma.com/manage/v2`) |
| `APPOINTMENT_CAPACITY_CHATBOT_SERVICE_SUBSCRIBER_USER` | Auth | Service subscriber username for kmanage auth |
| `APPOINTMENT_CAPACITY_CHATBOT_SERVICE_SUBSCRIBER_PASSWORD` | Auth | Service subscriber password for kmanage auth |
| `ENABLE_MKID_AUTH` | No | Enable mkid authentication (default: `true`). Set to `false` for local dev |
| `MODEL` | No | Claude model name (default: `claude-sonnet-4-5-20250929`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |
| `MOUNT_PREFIX` | No | URL prefix for HAProxy routing (default: `/capacity-chatbot`) |
| `PORT` | No | Server port (default: `3334`) |
| `POSTGRES_CONNECTION_STRING` | No | PostgreSQL connection string for conversation persistence (format: `postgresql://user:pass@host:port/db`) |

### Optional: Testing Without UI Client

For local testing without the UI client, set these to use test data:

| Variable | Description |
|----------|-------------|
| `TEST_DEPARTMENT_UUID` | Test department UUID |
| `TEST_DEALER_UUID` | Test dealer UUID |
| `TEST_DATA_PATH` | Path to test data JSON file |
| `ENABLE_TEST_DATA` | Set to `true` to load `test_data.json` |

---

## Project Structure

```
src/capacity_chatbot/
├── api.py                    # FastAPI server with LangGraph-compatible endpoints
├── auth.py                   # MKID authentication via kmanage API
├── graph.py                  # LangGraph state machine definition
├── state.py                  # Pydantic state models (Input/Output/Full state)
├── prompts.py                # System prompts for Claude
├── config.py                 # API client configuration
├── knowledge_base.py         # Keyword-based knowledge retrieval (50+ Q&As)
│
├── nodes/
│   └── capacity_agent.py     # ReAct agent node using Claude
│
├── clients/
│   └── kappointment_client.py  # HTTP client for kappointment-api
│
├── tools/
│   ├── __init__.py           # Tool exports (CAPACITY_TOOLS list)
│   ├── capacity.py           # get_capacity_tool - fetch capacity data
│   ├── rules.py              # get_rules_tool - fetch and format rules
│   ├── opcode.py             # search_opcode_tool - find services
│   ├── first_available_slot.py  # get_first_available_slot_tool
│   ├── entities.py           # get_available_entities, confirm_entity
│   ├── knowledge.py          # get_knowledge_answer - RAG search
│   └── validation.py         # Entity validation utilities (fuzzy matching)
│
└── utils/
    ├── date_parser.py        # Natural language date parsing
    ├── uuid_mapper.py        # UUID ↔ human-readable name mapping
    ├── enums.py              # Centralized enums (DayName, FilterField, FieldDisplayName, etc.)
    └── test_data.py          # Test data loading utilities
```

---

## API Endpoints

All endpoints are mounted under `MOUNT_PREFIX` (default: `/capacity-chatbot`).

### Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Kubernetes liveness probe |
| `GET` | `/ok` | Kubernetes readiness probe |

### Chat (Main API)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/threads/{thread_id}/runs/stream` | SSE streaming chat with real-time tool events |
| `POST` | `/threads/{thread_id}/runs/wait` | Non-streaming chat (waits for completion) |

### Request Format

Requests require `Authorization: Bearer <mkid>` header:

```http
POST /capacity-chatbot/threads/{thread_id}/runs/stream
Authorization: Bearer <mkid>
Content-Type: application/json
```

```json
{
  "input": {
    "messages": [{"role": "user", "content": "What is capacity for tomorrow?"}],
    "department_uuid": "uuid-here",
    "dealer_uuid": "uuid-here",
    "cached_data": {
      "transport_options": [...],
      "advisors": [...],
      "teams": [...]
    }
  },
  "stream_mode": ["values", "messages-tuple"]
}
```

### SSE Events

The streaming endpoint sends these event types:

| Event | Description |
|-------|-------------|
| `on_tool_start` | Tool execution started |
| `on_tool_end` | Tool execution completed |
| `on_chat_model_stream` | Streaming token from Claude |
| `values` | Final state with complete response |
| `end` | Stream complete |

---

## Tools Reference

The agent has access to these tools for answering user queries:

### 1. `get_knowledge_answer`

**Purpose:** Answer conceptual and how-to questions from the knowledge base.

**When to use:**
- "What is capacity?"
- "How do I create a capacity rule?"
- "What is a transport option?"

**Example call:**
```python
get_knowledge_answer(query="How do I increase transport option capacity?")
```

---

### 2. `get_available_entities`

**Purpose:** List available transport options, advisors, or teams from cached data.

**When to use:**
- "What transport options are available?"
- "List all advisors"
- "What teams are there?"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `entity_type` | `str` | One of: `transport_options`, `advisors`, `teams` |

---

### 3. `confirm_entity`

**Purpose:** Validate entity names before API calls using fuzzy matching.

**When to use:**
- Before calling capacity/rules with user-provided names
- "Visal" → suggests "Vishal"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `entity_type` | `str` | `advisor`, `transport`, or `team` |
| `entity_names` | `str` | Comma-separated names to validate |

---

### 4. `get_rules_tool`

**Purpose:** Fetch capacity and assignment rules with optional filtering.

**When to use:**
- "What rules are affecting Thursday?"
- "Show me rules for the Express team"
- "Are there any opcode restrictions?"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `dates` | `List[str]` | Optional. Natural language dates (`tomorrow`, `this week`) |
| `team_name` | `str` | Optional. Filter by team name |
| `advisor_name` | `str` | Optional. Filter by advisor name |
| `transport_option` | `str` | Optional. Filter by transport option |
| `opcode_name` | `str` | Optional. Filter by opcode/service |
| `entity_type` | `str` | Optional. Filter by entity type (`advisor`, `team`, `transport`, `opcode`) |

**Output includes:**
- Natural language description of each rule
- Applicability timing (dates, days of week)
- Conflict detection for assignment rules

---

### 5. `get_capacity_tool`

**Purpose:** Fetch capacity data showing used vs available appointments.

**When to use:**
- "What is capacity for tomorrow?"
- "How many loaner appointments are left?"
- "Capacity for Vishal next week"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `dates` | `List[str]` | Dates or natural language (`tomorrow`, `next Monday`) |
| `transport_option_names` | `List[str]` | Optional. Filter by transport options |
| `advisor_names` | `List[str]` | Optional. Filter by advisors |
| `team_names` | `List[str]` | Optional. Filter by teams |
| `opcodes` | `List[str]` | Optional. Opcode UUIDs (from `search_opcode`) |
| `source` | `str` | Optional. Channel filter (`Web`, `Dealer App`) |
| `start_time` | `str` | Optional. Time filter (`HH:mm:ss`) |

**Output includes:**
- Used/available counts per slot
- Breakdown by entity (advisor, transport, etc.)
- Limiting factor information (what's constraining capacity)

---

### 6. `get_first_available_slot_tool`

**Purpose:** Find the first available appointment slot.

**When to use:**
- "When is the first available appointment?"
- "Next slot for Vishal with loaner"
- "First available for oil change?"

**Parameters:**
| Name | Type | Description |
|------|------|-------------|
| `advisor_names` | `List[str]` | Optional. Filter by advisors |
| `team_names` | `List[str]` | Optional. Filter by teams |
| `transport_option_names` | `List[str]` | Optional. Filter by transport options |
| `dates` | `List[str]` | Optional. Start date (searches forward up to 90 days) |
| `start_time` | `str` | Optional. Earliest time (`HH:mm:ss`) |
| `end_time` | `str` | Optional. Latest time (`HH:mm:ss`) |
| `opcodes` | `List[str]` | Optional. Opcode UUIDs |

---

### 7. `search_opcode_tool`

**Purpose:** Search for services/opcodes or list all with daily limits.

**Two modes:**

1. **Search mode** - Find specific service by name:
   ```python
   search_opcode_tool(concern_text="oil change")
   ```

2. **List limits mode** - Get all opcodes with restrictions:
   ```python
   search_opcode_tool(list_all_with_limits=True)
   ```

**Output includes:**
- Opcode name, UUID, description
- Duration in minutes
- Daily limits per day of week

---

## How It Works

### ReAct Agent Architecture

The chatbot uses the **ReAct (Reasoning + Acting)** pattern:

1. **Receive** user message
2. **Reason** about what information is needed
3. **Act** by calling appropriate tools
4. **Observe** tool results
5. **Repeat** steps 2-4 until ready to respond
6. **Respond** with synthesized answer

### State Management

```python
@dataclass
class CapacityChatbotState:
    messages: List[AnyMessage]      # Conversation history
    department_uuid: str            # From UI client
    dealer_uuid: str                # From UI client  
    mkid: str                       # Auth cookie
    cached_data: Dict[str, Any]     # Transport options, advisors, teams
```

### Conversation Persistence

Currently uses **MemorySaver** (in-memory checkpointer):
- Conversations persist within a session
- Data is lost on restart

PostgreSQL checkpointer code is available but commented out in `graph.py` for future production use.

---

## Deployment

### Docker (Production)

The Dockerfile builds a production-ready container:

```bash
docker build -t capacity-chatbot .
docker run -d \
  -p 3334:3334 \
  -e ANTHROPIC_API_KEY=your-key \
  -e LANGSMITH_API_KEY=your-key \
  -e KAPPOINTMENT_API_BASE_URL=https://your-api.com \
  capacity-chatbot
```

### Jenkins CI/CD

The `Jenkinsfile` builds multi-arch images (amd64/arm64) and pushes to ECR:

1. Checkout code
2. Docker login to ECR
3. Build multi-platform image
4. Push to registry

Image versioning uses `version.txt`:
```
version=1.0.0
```

### Kubernetes

Deploy with:
- Health probes pointing to `/capacity-chatbot/health`
- Environment variables from secrets
- MOUNT_PREFIX set to match ingress path

---

## Development

### Running Locally

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Start with auto-reload
uvicorn capacity_chatbot.api:app --host 0.0.0.0 --port 3334 --reload
```

### Code Quality

```bash
# Run linter
ruff check src/

# Auto-fix issues
ruff check src/ --fix

# Type checking
mypy src/
```

### Testing with curl

```bash
# Health check
curl http://localhost:3334/capacity-chatbot/health

# Create thread
curl -X POST http://localhost:3334/capacity-chatbot/threads

# Send message (non-streaming)
curl -X POST http://localhost:3334/capacity-chatbot/threads/{thread_id}/runs \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "messages": [{"role": "user", "content": "What is capacity?"}],
      "department_uuid": "your-uuid",
      "dealer_uuid": "your-uuid"
    }
  }'
```

### Using Test Data

1. Copy `test_data.example.json` to `test_data.json`
2. Fill in real UUIDs and entity data
3. Set `ENABLE_TEST_DATA=true` in `.env`

---

## Troubleshooting

### Common Issues

**"Department UUID is required"**
- The UI client must provide `department_uuid` in the request
- For testing, set `DEPARTMENT_UUID` env var and `ENABLE_TEST_DATA=true`

**"ANTHROPIC_API_KEY not set"**
- Ensure `.env` file exists with valid API key
- Key format: `sk-ant-api03-...`

**"Error calling getCapacity"**
- Check `KAPPOINTMENT_API_BASE_URL` is correct
- Verify `mkid` cookie is valid
- Check API server is accessible

**No response streaming**
- Use `/runs/stream` endpoint, not `/runs`
- Ensure `Accept: text/event-stream` header

### Viewing Logs

LangSmith tracing is enabled by default when `LANGSMITH_API_KEY` is set:
- View traces at [smith.langchain.com](https://smith.langchain.com)
- Project name: `capacity-chatbot`

Local logs:
```bash
# Increase verbosity
LOG_LEVEL=DEBUG uvicorn capacity_chatbot.api:app ...
```

---

## License

Internal use only - MyKaarma proprietary.
