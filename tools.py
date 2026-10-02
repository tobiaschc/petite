"""
Stage 7: Tool classes with Pydantic validation

Two problems with the previous stage's TOOLS list:

1. The JSON Schema for each tool's parameters was hand-written and could
   drift from what execute() actually accepts.
2. execute_tool did `fn(**arguments)` on whatever JSON the model sent —
   a missing or mistyped argument surfaced as a raw Python TypeError deep
   inside the tool, not a clear validation error.

A Pydantic model per tool fixes both: the schema comes from
`model_json_schema()` (one source of truth), and arguments are validated
and coerced through that model *before* execute() ever runs.
"""

import subprocess

from pydantic import BaseModel, Field, ValidationError


class ReadArgs(BaseModel):
    file_path: str = Field(description="The path to the file to read")


class WriteArgs(BaseModel):
    file_path: str = Field(description="The path of the file to write to")
    content: str = Field(description="The content to write to the file")


class BashArgs(BaseModel):
    command: str = Field(description="The command to execute")


class Tool:
    name: str
    description: str
    args_model: type[BaseModel]

    def parameters(self):
        return self.args_model.model_json_schema()

    def spec(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters(),
            },
        }

    def execute(self, **kwargs):
        raise NotImplementedError


class ReadTool(Tool):
    name = "Read"
    description = "Read and return the contents of a file"
    args_model = ReadArgs

    def execute(self, file_path):
        with open(file_path) as f:
            return f.read()


class WriteTool(Tool):
    name = "Write"
    description = "Write content to a file, creating it if needed or overwriting it if it exists"
    args_model = WriteArgs

    def execute(self, file_path, content):
        with open(file_path, "w") as f:
            f.write(content)
        return f"Wrote to {file_path}"


class BashTool(Tool):
    name = "Bash"
    description = "Execute a shell command"
    args_model = BashArgs

    def execute(self, command):
        completed = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            output += f"\n(exit code {completed.returncode})"
        return output


ALL_TOOLS = [ReadTool(), WriteTool(), BashTool()]

TOOLS = [tool.spec() for tool in ALL_TOOLS]

TOOLS_BY_NAME = {tool.name: tool for tool in ALL_TOOLS}


def execute_tool(name, arguments):
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise RuntimeError(f"unknown tool: {name}")

    # Validates and coerces `arguments` against the tool's Pydantic model
    # before execute() runs — a missing/mistyped field fails here with a
    # clear error, returned as the tool result rather than crashing the
    # agent, so the model can see what's wrong and retry.
    try:
        validated = tool.args_model(**arguments)
    except ValidationError as e:
        return f"Invalid arguments for {name}: {e}"
    return tool.execute(**validated.model_dump())
