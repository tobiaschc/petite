"""
Stage 13: the Skill tool (model-invoked skills)

Every tool so far was self-contained. This one depends on skills.py: it
looks up a skill the model names, substitutes its arguments, and returns
the body as the tool result — the same mechanism slash commands use,
just triggered by a tool call instead of a "/name" prefix.
"""

import subprocess

from pydantic import BaseModel, Field, ValidationError

from agent import run_agent_loop
from skills import get_skill_meta, resolve_skill_invocation


class ReadArgs(BaseModel):
    file_path: str = Field(description="The path to the file to read")


class WriteArgs(BaseModel):
    file_path: str = Field(description="The path of the file to write to")
    content: str = Field(description="The content to write to the file")


class BashArgs(BaseModel):
    command: str = Field(description="The command to execute")


class SkillArgs(BaseModel):
    name: str = Field(description="The name of the skill to use")
    args: str = Field(default="", description="Optional arguments for the skill")


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
        try:
            with open(file_path) as f:
                return f.read()
        except Exception as e:
            return f"Error reading {file_path}: {e}"


class WriteTool(Tool):
    name = "Write"
    description = (
        "Write content to a file, creating it if needed or overwriting it if it exists"
    )
    args_model = WriteArgs

    def execute(self, file_path, content):
        try:
            with open(file_path, "w") as f:
                f.write(content)
            return f"Wrote to {file_path}"
        except Exception as e:
            return f"Error writing {file_path}: {e}"


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


class SkillTool(Tool):
    name = "Skill"
    description = "Load a skill's instructions into the conversation"
    args_model = SkillArgs

    def execute(self, name, args=""):
        try:
            body = resolve_skill_invocation(name, args)
        except ValueError as e:
            return str(e)
        if body is None:
            return f"Unknown skill: {name}"

        meta = get_skill_meta(name)
        if meta is not None and meta.context == "fork":
            # Run in a subagent: a brand new conversation that only ever
            # sees this body, not the question that triggered it. Only
            # its final answer crosses back into the main conversation.
            subagent_messages = [{"role": "user", "content": body}]
            answer = run_agent_loop(
                subagent_messages, SUBAGENT_TOOLS, execute_tool, label=f"subagent:{name}"
            )
            return f"Skill {name} ran in a separate context and returned: {answer}"

        return body


ALL_TOOLS = [ReadTool(), WriteTool(), BashTool()]
SKILL_TOOL = SkillTool()

# Subagents get Read/Write/Bash but never the Skill tool itself — without
# this, a forked skill's folder header ("Skill: owl (located at ...)")
# reads to a model as an instruction to call Skill again, recursing
# forever instead of just following the body it was already given.
SUBAGENT_TOOLS = [tool.spec() for tool in ALL_TOOLS]

MAIN_TOOLS = ALL_TOOLS + [SKILL_TOOL]
TOOLS = [tool.spec() for tool in MAIN_TOOLS]

TOOLS_BY_NAME = {tool.name: tool for tool in MAIN_TOOLS}


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
