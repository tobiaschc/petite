"""
Stage 14: subagents

A skill with `context: fork` in its frontmatter runs in a subagent — a
second, independent run of this same loop, seeded with only the skill's
body (not the question that triggered it), returning just its final
answer to the main conversation.

Pulling the loop out into run_agent_loop() is what makes that possible:
main() calls it once for the top-level conversation, and the Skill tool
(in tools.py) calls it again, on a brand new messages list, whenever it
resolves a context: fork skill. Both calls share the same model/tools —
a subagent isn't a different kind of agent, just a fresh conversation.
"""

import json
import os
import sys

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")
MAX_TURNS = 20

_client = None


def _get_client():
    global _client
    if _client is None:
        if not API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set")
        _client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    return _client


def run_agent_loop(messages, tools, execute_tool, label="agent"):
    """Run the agent loop to completion over `messages` (mutated in
    place: assistant/tool messages are appended as the loop runs) and
    return the model's final text answer.

    `tools` is the OpenAI tools spec list; `execute_tool(name, arguments)`
    runs one tool call and returns its result string. `label` only
    affects the stderr log prefix, so a subagent's logs are easy to tell
    apart from the main conversation's.
    """
    client = _get_client()

    for turn in range(1, MAX_TURNS + 1):
        print(
            f"[{label}] turn {turn}: calling model with {len(messages)} message(s)",
            file=sys.stderr,
        )

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
        )

        if not response.choices:
            raise RuntimeError("no choices in response")

        message = response.choices[0].message
        messages.append(message.model_dump())

        tool_calls = message.tool_calls

        if not tool_calls:
            return message.content

        print(
            f"[{label}] turn {turn}: {len(tool_calls)} tool call(s) requested",
            file=sys.stderr,
        )

        for call in tool_calls:
            arguments = json.loads(call.function.arguments)
            print(f"[{label}] executing {call.function.name}({arguments})", file=sys.stderr)

            result = execute_tool(call.function.name, arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    raise RuntimeError(f"[{label}] exceeded {MAX_TURNS} turns without a final answer")
