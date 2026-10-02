"""
Stage 5: the Bash tool

Shell access: subprocess.run captures stdout and stderr, and the combined
output goes back to the model as the tool's result (empty on a silent
success, like `rm file` with no output).
"""

import argparse
import json
import os
import subprocess
import sys

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")
MAX_TURNS = 20

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
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Execute a shell command",
            "parameters": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute",
                    }
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


def Bash(command):
    completed = subprocess.run(command, shell=True, capture_output=True, text=True)
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        output += f"\n(exit code {completed.returncode})"
    return output


def execute_tool(name, arguments):
    if name == "Read":
        return Read(arguments["file_path"])
    if name == "Write":
        return Write(arguments["file_path"], arguments["content"])
    if name == "Bash":
        return Bash(arguments["command"])
    raise RuntimeError(f"unknown tool: {name}")


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
