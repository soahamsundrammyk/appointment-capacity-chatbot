"""FastAPI server for the capacity chatbot.

This server provides LangGraph-compatible API endpoints for the UI client.
"""

import json
import logging
import os
from typing import Any

from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage

from capacity_chatbot.api.middleware.auth import get_authenticated_session
from capacity_chatbot.graph import get_graph
from capacity_chatbot.model.requests import RunRequest

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get mount prefix from environment (for HAProxy routing)
# Defaults to /capacity-chatbot for production
MOUNT_PREFIX = os.getenv("MOUNT_PREFIX", "/capacity-chatbot")

app = FastAPI(
    title="Capacity Chatbot API",
    description="AI-powered chatbot for capacity-related questions",
    version="1.0.0",
)


# Health check endpoint (will be available at /capacity-chatbot/ok when mounted)
@app.get("/ok")
async def health_check():
    return {"status": "ok"}


root_app = FastAPI(title="Capacity Chatbot")


@root_app.get("/ok")
async def root_health_check():
    """Health check on root app for K8s probes that hit /ok directly."""
    return {"status": "ok"}


root_app.mount(MOUNT_PREFIX, app)


def convert_to_langchain_messages(messages: list[dict[str, Any]]) -> list:
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


def serialize_message(msg) -> dict[str, Any]:
    """Convert a LangChain message to API format."""
    if hasattr(msg, "type"):
        return {
            "type": msg.type,
            "content": msg.content,
        }
    return {"type": "unknown", "content": str(msg)}


def build_graph_input(
    state, messages: list, input_data: dict[str, Any], session_info: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the graph input from state and new messages.

    Uses session info from mkid auth (preferred) or falls back to request body.
    Note: mkid is passed through config, not state.
    """
    session = session_info or {}
    updated_context = {
        "department_uuid": input_data.get("department_uuid") or session.get("departmentUuid", ""),
        "dealer_uuid": input_data.get("dealer_uuid") or session.get("dealerUuid", ""),
    }
    cd = input_data.get("cached_data") or {}
    if cd:
        updated_context["advisors"] = cd.get("advisors", [])
        updated_context["transport_options"] = cd.get("transport_options", [])
        updated_context["teams"] = cd.get("teams", [])

    if state.values and state.values.get("messages"):
        # Append to existing conversation
        existing_messages = state.values.get("messages", [])
        return {
            **state.values,
            **updated_context,
            "messages": existing_messages + messages,
        }
    else:
        # New conversation
        return {
            "messages": messages,
            **updated_context,
        }


async def run_graph_stream(
    thread_id: str, input_data: dict[str, Any], stream_mode: list[str], session_info: dict[str, Any]
):
    """Run the graph and stream results with real-time tool call events."""
    graph = await get_graph()

    # Extract mkid from session_info (from auth middleware)
    mkid = session_info.get("mkid", "")
    config = {
        "configurable": {
            "thread_id": thread_id,
            "mkid": mkid,
        }
    }

    try:
        state = await graph.aget_state(config)
        messages = convert_to_langchain_messages(input_data.get("messages", []))
        graph_input = build_graph_input(state, messages, input_data, session_info)

        final_messages = []

        async for event in graph.astream_events(graph_input, config, version="v2"):
            event_type = event.get("event", "")

            if event_type == "on_tool_start":
                tool_name = event.get("name", "unknown")
                event_data = {"event": "on_tool_start", "name": tool_name}
                yield f"event: on_tool_start\ndata: {json.dumps(event_data)}\n\n"

            elif event_type == "on_tool_end":
                tool_name = event.get("name", "unknown")
                event_data = {"event": "on_tool_end", "name": tool_name}
                yield f"event: on_tool_end\ndata: {json.dumps(event_data)}\n\n"

            elif event_type == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    event_data = {
                        "event": "on_chat_model_stream",
                        "data": {"chunk": {"content": chunk.content}},
                    }
                    yield f"event: on_chat_model_stream\ndata: {json.dumps(event_data)}\n\n"

            elif event_type == "on_chain_end" and event.get("name") == "LangGraph":
                output = event.get("data", {}).get("output", {})
                if "messages" in output:
                    final_messages = output["messages"]

        # Stream final values
        if "values" in stream_mode and final_messages:
            final_values = {"messages": [serialize_message(m) for m in final_messages]}
            yield f"event: values\ndata: {json.dumps(final_values)}\n\n"

        yield f"event: end\ndata: {json.dumps({'status': 'done'})}\n\n"

    except Exception as e:
        logger.exception(f"Error running graph for thread {thread_id}: {e}")
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


@app.post("/threads/{thread_id}/runs/stream")
async def create_run_stream(
    thread_id: str,
    request: RunRequest,
    session: dict[str, Any] = Depends(get_authenticated_session),
):
    """
    Stream a run with real-time SSE events.

    Requires valid mkid in Authorization header (Bearer token).
    """
    stream_mode = request.stream_mode or ["messages-tuple", "values"]
    return StreamingResponse(
        run_graph_stream(thread_id, request.input.model_dump(), stream_mode, session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.on_event("startup")
async def startup_event():
    """Initialize the graph on startup."""
    logger.info("Starting Capacity Chatbot API server...")
    try:
        await get_graph()
        logger.info("Graph initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize graph: {e}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "3334"))
    uvicorn.run(root_app, host="0.0.0.0", port=port)
