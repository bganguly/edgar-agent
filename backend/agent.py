"""
Manual agent loop — no LangChain, no CrewAI.

Anthropic path: client.messages.create with tools; loop while stop_reason == "tool_use".
NVIDIA NIM path: openai.ChatCompletion-compatible interface with function_call.
"""

from typing import AsyncGenerator
import json
import anthropic
import openai as openai_lib

from config import (
    MODEL_PROVIDER,
    ANTHROPIC_MODEL,
    ANTHROPIC_API_KEY,
    NVIDIA_BASE_URL,
    NVIDIA_API_KEY,
    NVIDIA_MODEL,
)
from tools import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = (
    "You are a financial research assistant that answers questions about public companies "
    "using SEC EDGAR 10-K annual filings. When asked about a company, first search EDGAR "
    "for filings, then fetch the most relevant filing to extract information. "
    "Always cite the source filing in your answer."
)

_anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

_nvidia_client = openai_lib.OpenAI(
    base_url=NVIDIA_BASE_URL,
    api_key=NVIDIA_API_KEY,
) if MODEL_PROVIDER == "nvidia" else None


def _tools_as_openai_functions() -> list[dict]:
    """Convert Anthropic-style tool defs to OpenAI function-call format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOL_DEFINITIONS
    ]


async def run_agent_anthropic(messages: list[dict]) -> AsyncGenerator[str, None]:
    """Yield SSE-ready chunks. Runs the tool loop synchronously between yields."""
    current_messages = list(messages)

    while True:
        response = _anthropic_client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=current_messages,
        )

        if response.stop_reason == "tool_use":
            # Emit tool-call notification
            for block in response.content:
                if block.type == "tool_use":
                    yield json.dumps({"type": "tool_call", "tool": block.name, "input": block.input}) + "\n"

            # Append assistant message with tool_use blocks
            current_messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls and collect results
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            current_messages.append({"role": "user", "content": tool_results})

        else:
            # Final answer — stream it token by token using the streaming API
            with _anthropic_client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=current_messages,
            ) as stream:
                for text in stream.text_stream:
                    yield json.dumps({"type": "token", "text": text}) + "\n"

            final = stream.get_final_message()
            # Return updated messages so caller can persist them
            current_messages.append({"role": "assistant", "content": final.content})
            yield json.dumps({"type": "done", "messages": _serialize_messages(current_messages)}) + "\n"
            return


async def run_agent_nvidia(messages: list[dict]) -> AsyncGenerator[str, None]:
    """NVIDIA NIM / Nemotron via OpenAI-compatible interface."""
    current_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + _to_openai_messages(messages)
    functions = _tools_as_openai_functions()

    while True:
        response = _nvidia_client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=current_messages,
            tools=functions,
            tool_choice="auto",
        )

        choice = response.choices[0]

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_input = json.loads(tc.function.arguments)
                yield json.dumps({"type": "tool_call", "tool": tc.function.name, "input": tool_input}) + "\n"

            current_messages.append(choice.message.model_dump())

            for tc in choice.message.tool_calls:
                tool_input = json.loads(tc.function.arguments)
                result = execute_tool(tc.function.name, tool_input)
                current_messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        else:
            text = choice.message.content or ""
            # Yield token by token (NVIDIA NIM non-streaming for simplicity; emit whole response)
            for chunk in _split_into_chunks(text, size=20):
                yield json.dumps({"type": "token", "text": chunk}) + "\n"

            current_messages.append({"role": "assistant", "content": text})
            # Convert back to Anthropic-style for session storage
            yield json.dumps({"type": "done", "messages": _serialize_messages(messages + [{"role": "assistant", "content": text}])}) + "\n"
            return


async def run_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
    if MODEL_PROVIDER == "nvidia":
        async for chunk in run_agent_nvidia(messages):
            yield chunk
    else:
        async for chunk in run_agent_anthropic(messages):
            yield chunk


def _serialize_messages(messages: list) -> list[dict]:
    """Convert Anthropic SDK objects to plain dicts for JSON serialization."""
    result = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
        else:
            result.append(msg.model_dump() if hasattr(msg, "model_dump") else dict(msg))
    return result


def _to_openai_messages(messages: list[dict]) -> list[dict]:
    """Convert from Anthropic message format to OpenAI format."""
    out = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            out.append({"role": role, "content": content})
        elif isinstance(content, list):
            text_parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            out.append({"role": role, "content": " ".join(text_parts)})
    return out


def _split_into_chunks(text: str, size: int = 20) -> list[str]:
    words = text.split(" ")
    chunk, chunks = [], []
    for w in words:
        chunk.append(w)
        if len(chunk) >= size:
            chunks.append(" ".join(chunk) + " ")
            chunk = []
    if chunk:
        chunks.append(" ".join(chunk))
    return chunks
