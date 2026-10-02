"""
Stage 6: extract a tools module

main.py is now just the agent loop — tool specs and implementations live
in tools.py (see that file for why this split happened).
"""

import argparse
import json
import os
import sys

from openai import OpenAI

from tools import TOOLS, execute_tool

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")
MAX_TURNS = 20


def main():
    parser = argparse.ArgumentParser(description="petite-harness: a tiny AI coding assistant")
    parser.add_argument("-p", "--prompt", required=True, help="the task to ask the model")
    args = parser.parse_args()

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    messages = [{"role": "user", "content": args.prompt}]

    for turn in range(1, MAX_TURNS + 1):
        print(f"[agent] turn {turn}: calling model with {len(messages)} message(s)", file=sys.stderr)

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )

        if not response.choices:
            raise RuntimeError("no choices in response")

        message = response.choices[0].message
        messages.append(message.model_dump())

        tool_calls = message.tool_calls

        if not tool_calls:
            print(message.content)
            return

        print(f"[agent] turn {turn}: {len(tool_calls)} tool call(s) requested", file=sys.stderr)

        for call in tool_calls:
            arguments = json.loads(call.function.arguments)
            print(f"[agent] executing {call.function.name}({arguments})", file=sys.stderr)

            result = execute_tool(call.function.name, arguments)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result,
                }
            )

    raise RuntimeError(f"exceeded {MAX_TURNS} turns without a final answer")


if __name__ == "__main__":
    main()
