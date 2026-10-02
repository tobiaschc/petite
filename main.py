"""
Stage 2: the Read tool

The model can't touch your filesystem on its own — it can only ask. This
stage adds one tool, Read, and a single round trip: send the prompt and
the tool's spec, check if the model asked to call it, execute it if so,
print the result (no loop yet, that's the next stage).
"""

import argparse
import json
import os
import sys

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read and return the contents of a file",
            "parameters": {
                "type": "object",
                "required": ["file_path"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path to the file to read",
                    }
                },
            },
        },
    }
]


def Read(file_path):
    with open(file_path) as f:
        return f.read()


def main():
    parser = argparse.ArgumentParser(description="petite-harness: a tiny AI coding assistant")
    parser.add_argument("-p", "--prompt", required=True, help="the task to ask the model")
    args = parser.parse_args()

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    print(f"[main] sending prompt to {MODEL}", file=sys.stderr)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": args.prompt}],
        tools=TOOLS,
    )

    if not response.choices:
        raise RuntimeError("no choices in response")

    message = response.choices[0].message

    if message.tool_calls:
        call = message.tool_calls[0]
        print(f"[main] model requested tool call: {call.function.name}", file=sys.stderr)

        if call.function.name != "Read":
            raise RuntimeError(f"unknown tool: {call.function.name}")

        arguments = json.loads(call.function.arguments)
        print(Read(arguments["file_path"]))
        return

    print(message.content)


if __name__ == "__main__":
    main()
