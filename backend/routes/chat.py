import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent import run_agent
from sessions import append_message, get_history

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


@router.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    messages = get_history(session_id)

    append_message(session_id, {"role": "user", "content": req.message})
    messages = get_history(session_id)

    async def event_stream() -> AsyncGenerator[dict, None]:
        final_messages = None
        async for chunk in run_agent(messages):
            data = json.loads(chunk)
            if data["type"] == "done":
                final_messages = data.get("messages", [])
            else:
                yield {"data": chunk}

        if final_messages:
            for msg in final_messages[len(messages):]:
                append_message(session_id, msg)

        yield {"data": json.dumps({"type": "session_id", "session_id": session_id}) + "\n"}

    return EventSourceResponse(event_stream())


@router.get("/sessions/{session_id}/history")
async def history(session_id: str):
    msgs = get_history(session_id)
    if not msgs:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "messages": msgs}
