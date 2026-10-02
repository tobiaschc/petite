"""
Stage 6: extract a tools module

Three tools in and the `if/elif` in execute_tool, plus the hand-written
TOOLS list, are two places that have to stay in sync by hand. That's the
signal to extract: one module owns both the specs the model sees and the
functions that back them, with a dict instead of a growing if/elif chain.

Adding a fourth tool from here on is: write the function, add its spec to
TOOLS, add one line to TOOL_FUNCTIONS. Nothing in main.py changes.
"""

import subprocess


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

TOOL_FUNCTIONS = {
    "Read": Read,
    "Write": Write,
    "Bash": Bash,
}


def execute_tool(name, arguments):
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        raise RuntimeError(f"unknown tool: {name}")
    return fn(**arguments)
