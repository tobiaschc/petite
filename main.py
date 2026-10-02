"""
Stage 3: the Write tool

Same pattern as Read: advertise the spec, dispatch by name when the model
calls it. Still one round trip, still no loop — just a second tool.
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
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file, creating it if needed or overwriting it if it exists",
            "parameters": {
                "type": "object",
                "required": ["file_path", "content"],
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The path of the file to write to",
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to write to the file",
                    },
                },
            },
        },
    },
]


def Read(file_path):
    with open(file_path) as f:
        return f.read()


def Write(file_path, content):
    with open(file_path, "w") as f:
        f.write(content)
    return f"Wrote to {file_path}"


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

        arguments = json.loads(call.function.arguments)

        if call.function.name == "Read":
            result = Read(arguments["file_path"])
        elif call.function.name == "Write":
            result = Write(arguments["file_path"], arguments["content"])
        else:
            raise RuntimeError(f"unknown tool: {call.function.name}")

        print(result)
        return

    print(message.content)


if __name__ == "__main__":
    main()
