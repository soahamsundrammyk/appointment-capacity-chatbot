"""FastAPI server for the capacity chatbot.

This server provides LangGraph-compatible API endpoints for the UI client.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel

from capacity_chatbot.graph import get_graph

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================================
# FastAPI App Setup
# ============================================================================

# Get mount prefix from environment (for HAProxy routing)
MOUNT_PREFIX = os.getenv("MOUNT_PREFIX", "")

# Create the internal API app with all the routes
api_app = FastAPI(
    title="Capacity Chatbot API",
    description="AI-powered chatbot for capacity-related questions",
    version="1.0.0",
)

# Create the main app - routes will be mounted under MOUNT_PREFIX if set
app = FastAPI(
    title="Capacity Chatbot",
    version="1.0.0",
)

# CORS middleware on both apps
for fast_app in [app, api_app]:
    fast_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount the API under the prefix (e.g., /capacity-chatbot)
if MOUNT_PREFIX:
    # Add root-level health check for Kubernetes probes (works without prefix)
    @app.get("/health")
    async def root_health_check():
        return {"status": "healthy"}

    @app.get("/ok")
    async def root_ok_check():
        return {"status": "ok"}

    app.mount(MOUNT_PREFIX, api_app)
    logger.info(f"API mounted under prefix: {MOUNT_PREFIX}")
else:
    # No prefix - use api_app directly
    app = api_app


# ============================================================================
# Request/Response Models
# ============================================================================

class RunInput(BaseModel):
    """Input for a run - matches LangGraph API format."""
    messages: List[Dict[str, Any]]
    department_uuid: Optional[str] = ""
    dealer_uuid: Optional[str] = ""
    mkid: Optional[str] = ""
    cached_data: Optional[Dict[str, Any]] = None


class RunRequest(BaseModel):
    """Request to create a run - matches LangGraph API format."""
    input: RunInput
    config: Optional[Dict[str, Any]] = None
    stream_mode: Optional[List[str]] = None


# ============================================================================
# Health Endpoints
# ============================================================================

@api_app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy"}


@api_app.get("/ok")
async def ok_check():
    """Simple OK check."""
    return {"status": "ok"}


# ============================================================================
# Helper Functions
# ============================================================================

def convert_to_langchain_messages(messages: List[Dict[str, Any]]) -> List:
    """Convert API message format to LangChain messages."""
    result = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get("role", msg.get("type", "user"))
            content = msg.get("content", "")

            if role in ("user", "human"):
                result.append(HumanMessage(content=content))
            elif role in ("assistant", "ai"):
                result.append(AIMessage(content=content))
    return result


def serialize_message(msg) -> Dict[str, Any]:
    """Convert a LangChain message to API format."""
    if hasattr(msg, "type"):
        return {
            "type": msg.type,
            "content": msg.content,
        }
    return {"type": "unknown", "content": str(msg)}


def build_graph_input(
    state, messages: List, input_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Build the graph input from state and new messages.
    
    Always merges updated context fields (mkid, department_uuid, dealer_uuid, cached_data)
    from input_data to handle session/auth refreshes mid-conversation.
    """
    # Always use latest context from input_data to handle session refreshes
    updated_context = {}
    if input_data.get("mkid"):
        updated_context["mkid"] = input_data["mkid"]
    if input_data.get("department_uuid"):
        updated_context["department_uuid"] = input_data["department_uuid"]
    if input_data.get("dealer_uuid"):
        updated_context["dealer_uuid"] = input_data["dealer_uuid"]
    if input_data.get("cached_data"):
        updated_context["cached_data"] = input_data["cached_data"]

    if state.values and state.values.get("messages"):
        # Append to existing conversation, but merge updated context
        existing_messages = state.values.get("messages", [])
        return {
            **state.values,
            **updated_context,  # Override with fresh context from UI
            "messages": existing_messages + messages,
        }
    else:
        # New conversation
        return {
            "messages": messages,
            "department_uuid": input_data.get("department_uuid", ""),
            "dealer_uuid": input_data.get("dealer_uuid", ""),
            "mkid": input_data.get("mkid", ""),
            "cached_data": input_data.get("cached_data"),
        }


# ============================================================================
# Streaming Run Endpoint
# ============================================================================

async def run_graph_stream(
    thread_id: str, input_data: Dict[str, Any], stream_mode: List[str]
):
    """Run the graph and stream results with real-time tool call events."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)
        messages = convert_to_langchain_messages(input_data.get("messages", []))
        graph_input = build_graph_input(state, messages, input_data)

        logger.info(f"Running graph for thread {thread_id} with astream_events")

        final_messages = []

        async for event in graph.astream_events(graph_input, config, version="v2"):
            event_type = event.get("event", "")

            if event_type == "on_tool_start":
                tool_name = event.get("name", "unknown")
                event_data = {"event": "on_tool_start", "name": tool_name}
                yield f"event: on_tool_start\ndata: {json.dumps(event_data)}\n\n"
                logger.debug(f"Tool started: {tool_name}")

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "unknown")
                event_data = {"event": "on_tool_end", "name": tool_name}
                yield f"event: on_tool_end\ndata: {json.dumps(event_data)}\n\n"
                logger.debug(f"Tool ended: {tool_name}")

            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    event_data = {
                        "event": "on_chat_model_stream",
                        "data": {"chunk": {"content": chunk.content}}
                    }
                    yield f"event: on_chat_model_stream\ndata: {json.dumps(event_data)}\n\n"

            elif event_type == "on_chain_end" and event.get("name") == "LangGraph":
                output = event.get("data", {}).get("output", {})
                if "messages" in output:
                    final_messages = output["messages"]

        # Stream final values
        if "values" in stream_mode and final_messages:
            final_values = {
                "messages": [serialize_message(m) for m in final_messages]
            }
            yield f"event: values\ndata: {json.dumps(final_values)}\n\n"

        yield f"event: end\ndata: {json.dumps({'status': 'done'})}\n\n"

    except Exception as e:
        logger.exception(f"Error running graph: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@api_app.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(thread_id: str, request: RunRequest):
    """
    Stream a run with real-time SSE events.
    
    Used by the UI client for streaming responses with tool call visibility.
    """
    stream_mode = request.stream_mode or ["messages-tuple", "values"]

    return StreamingResponse(
        run_graph_stream(thread_id, request.input.model_dump(), stream_mode),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# Non-Streaming Run Endpoint (wait for completion)
# ============================================================================

@api_app.post("/threads/{thread_id}/runs/wait")
async def create_run_wait(thread_id: str, request: RunRequest):
    """
    Run the graph and wait for completion (non-streaming).
    
    Used by the UI client as a fallback when SSE streaming is not available.
    Returns the complete response once the graph finishes execution.
    """
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}

    try:
        state = graph.get_state(config)
        messages = convert_to_langchain_messages(request.input.messages)
        graph_input = build_graph_input(state, messages, request.input.model_dump())

        logger.info(f"Running graph for thread {thread_id} (wait mode)")

        result = await graph.ainvoke(graph_input, config)

        return {
            "thread_id": thread_id,
            "messages": [serialize_message(m) for m in result.get("messages", [])],
            "values": {
                "messages": [serialize_message(m) for m in result.get("messages", [])]
            },
        }

    except Exception as e:
        logger.exception(f"Error running graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Startup
# ============================================================================

@api_app.on_event("startup")
async def startup_event():
    """Initialize the graph on startup."""
    logger.info("Starting Capacity Chatbot API server...")
    try:
        get_graph()
        logger.info("Graph initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize graph: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3334"))
    uvicorn.run(app, host="0.0.0.0", port=port)
