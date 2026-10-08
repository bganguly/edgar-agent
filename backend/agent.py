"""
Manual agent loop — no LangChain, no CrewAI.
Anthropic path only: client.messages.create with tools; loop while stop_reason == "tool_use".
"""

from typing import AsyncGenerator
import json
import anthropic

from config import ANTHROPIC_MODEL, ANTHROPIC_API_KEY
from tools import TOOL_DEFINITIONS, execute_tool

SYSTEM_PROMPT = (
    "You are a financial research assistant that answers questions about public companies "
    "using SEC EDGAR 10-K annual filings. When asked about a company, first search EDGAR "
    "for filings, then fetch the most relevant filing to extract information. "
    "Always cite the source filing in your answer."
)

_anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


async def run_agent(messages: list[dict]) -> AsyncGenerator[str, None]:
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
            for block in response.content:
                if block.type == "tool_use":
                    yield json.dumps({"type": "tool_call", "tool": block.name, "input": block.input}) + "\n"

            current_messages.append({"role": "assistant", "content": response.content})

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
            current_messages.append({"role": "assistant", "content": final.content})
            yield json.dumps({"type": "done", "messages": _serialize_messages(current_messages)}) + "\n"
            return


def _serialize_messages(messages: list) -> list[dict]:
    """Convert Anthropic SDK objects to plain dicts for JSON serialization."""
    result = []
    for msg in messages:
        if isinstance(msg, dict):
            result.append(msg)
        else:
            result.append(msg.model_dump() if hasattr(msg, "model_dump") else dict(msg))
    return result
