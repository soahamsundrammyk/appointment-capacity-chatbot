"""FastAPI server for the capacity chatbot - replaces langgraph dev.

This server provides LangGraph-compatible API endpoints with PostgreSQL persistence.
"""

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

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

app = FastAPI(
    title="Capacity Chatbot API",
    description="AI-powered chatbot for capacity-related questions",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models (LangGraph-compatible format)
# ============================================================================

class MessageContent(BaseModel):
    """A message in the conversation."""
    role: str  # "user" or "assistant"
    content: str


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


class ThreadState(BaseModel):
    """Current state of a thread."""
    values: Dict[str, Any]
    next: List[str] = []


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint for Kubernetes probes."""
    return {"status": "healthy"}


@app.get("/ok")
async def ok_check():
    """Simple OK check."""
    return {"status": "ok"}


@app.get("/info")
async def info():
    """Service information."""
    return {
        "service": "capacity-chatbot",
        "version": "1.0.0",
    }


# ============================================================================
# Thread Management Endpoints
# ============================================================================

@app.post("/threads")
async def create_thread():
    """Create a new thread and return its ID."""
    thread_id = str(uuid.uuid4())
    return {"thread_id": thread_id}


@app.get("/threads/{thread_id}/state")
async def get_thread_state(thread_id: str):
    """Get the current state of a thread."""
    try:
        graph = get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        state = graph.get_state(config)
        
        # Convert messages to serializable format
        messages = []
        if state.values and "messages" in state.values:
            for msg in state.values["messages"]:
                if hasattr(msg, "type"):
                    messages.append({
                        "role": "user" if msg.type == "human" else "assistant",
                        "content": msg.content,
                    })
        
        return {
            "values": {"messages": messages},
            "next": list(state.next) if state.next else [],
        }
    except Exception as e:
        logger.error(f"Error getting thread state: {e}")
        return {"values": {"messages": []}, "next": []}


# ============================================================================
# Run Endpoints (Main Chat API)
# ============================================================================

def convert_to_langchain_messages(messages: List[Dict[str, Any]]) -> List:
    """Convert API message format to LangChain messages."""
    result = []
    for msg in messages:
        # Handle different message formats
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


async def run_graph_stream(thread_id: str, input_data: Dict[str, Any], stream_mode: List[str]):
    """Run the graph and stream results."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Check existing state
        state = graph.get_state(config)
        
        # Convert messages
        messages = convert_to_langchain_messages(input_data.get("messages", []))
        
        # Build input
        if state.values and state.values.get("messages"):
            # Append to existing conversation
            existing_messages = state.values.get("messages", [])
            graph_input = {
                **state.values,
                "messages": existing_messages + messages,
            }
        else:
            # New conversation
            graph_input = {
                "messages": messages,
                "department_uuid": input_data.get("department_uuid", ""),
                "dealer_uuid": input_data.get("dealer_uuid", ""),
                "mkid": input_data.get("mkid", ""),
                "cached_data": input_data.get("cached_data"),
            }
        
        logger.info(f"Running graph for thread {thread_id}")
        
        # Run graph (invoke is synchronous, so use run_in_executor)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            lambda: graph.invoke(graph_input, config)
        )
        
        # Stream based on mode
        if "messages-tuple" in stream_mode:
            # Stream messages in tuple format
            for msg in result.get("messages", []):
                event = {
                    "event": "messages/partial",
                    "data": [serialize_message(msg), {}]
                }
                yield f"event: messages/partial\ndata: {json.dumps(event['data'])}\n\n"
        
        if "values" in stream_mode:
            # Stream final values
            final_values = {
                "messages": [serialize_message(m) for m in result.get("messages", [])]
            }
            yield f"event: values\ndata: {json.dumps(final_values)}\n\n"
        
        # Always send done event
        yield f"event: end\ndata: {json.dumps({'status': 'done'})}\n\n"
        
    except Exception as e:
        logger.exception(f"Error running graph: {e}")
        error_data = {"error": str(e)}
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"


@app.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(thread_id: str, request: RunRequest):
    """
    Create a run and stream results - main chat endpoint.
    
    This endpoint matches the LangGraph API format used by the UI client.
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


@app.post("/threads/{thread_id}/runs")
async def create_run(thread_id: str, request: RunRequest):
    """Create a run and return result (non-streaming)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Check existing state
        state = graph.get_state(config)
        
        # Convert messages
        messages = convert_to_langchain_messages(request.input.messages)
        
        # Build input
        if state.values and state.values.get("messages"):
            existing_messages = state.values.get("messages", [])
            graph_input = {
                **state.values,
                "messages": existing_messages + messages,
            }
        else:
            graph_input = {
                "messages": messages,
                "department_uuid": request.input.department_uuid or "",
                "dealer_uuid": request.input.dealer_uuid or "",
                "mkid": request.input.mkid or "",
                "cached_data": request.input.cached_data,
            }
        
        # Run graph
        result = graph.invoke(graph_input, config)
        
        # Return serialized result
        return {
            "thread_id": thread_id,
            "values": {
                "messages": [serialize_message(m) for m in result.get("messages", [])]
            },
        }
        
    except Exception as e:
        logger.exception(f"Error running graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Assistants Endpoint (for UI compatibility)
# ============================================================================

@app.get("/assistants")
async def get_assistants():
    """Return available assistants (graphs)."""
    return [
        {
            "assistant_id": "capacity_agent",
            "graph_id": "capacity_agent",
            "name": "Capacity Chatbot",
        }
    ]


@app.get("/assistants/search")
async def search_assistants():
    """Search assistants (returns all for simplicity)."""
    return [
        {
            "assistant_id": "capacity_agent",
            "graph_id": "capacity_agent", 
            "name": "Capacity Chatbot",
        }
    ]


# ============================================================================
# Startup Event
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize the graph on startup to establish DB connection early."""
    logger.info("Starting Capacity Chatbot API server...")
    try:
        graph = get_graph()
        logger.info("Graph initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize graph: {e}")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "3334"))
    uvicorn.run(app, host="0.0.0.0", port=port)
