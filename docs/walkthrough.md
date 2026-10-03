# Walkthrough

One paragraph per stage: the problem it solves and why the solution looks the way it does. The code itself is the real documentation — each heading links to that stage's exact snapshot — this page is the narration that goes with it.

## Base agent

### [1. Talk to an LLM](https://github.com/tobiaschc/petite/tree/stage-01-talk-to-llm)

The smallest possible agent isn't an agent at all: one prompt in, one response out, no memory, no tools. Before adding any of that, there has to be something that talks to an LLM API at all. Everything else in this project is this call, wrapped in more structure.

### [2. Read tool](https://github.com/tobiaschc/petite/tree/stage-02-read-tool)

An LLM can't touch a filesystem by default — it only produces text. A "tool" is just a JSON schema describing a function, sent alongside the prompt, that the model can ask to have called. This stage advertises exactly one: `Read`. Still a single round trip — the model asks, you call it, you print the result and exit. No loop yet, because the point here is purely "the model can ask for something it doesn't have."

### [3. Write tool](https://github.com/tobiaschc/petite/tree/stage-03-write-tool)

Same idea as Read, mirrored for writing: one more entry in the tools list, one more branch in the dispatcher. Adding a second tool before building the loop is deliberate — it proves the tool-calling mechanism generalizes before anything more complex sits on top of it.

### [4. Agent loop](https://github.com/tobiaschc/petite/tree/stage-04-agent-loop)

A single round trip can't do "read a file and fix a bug in it" — that needs the model to see a tool's result and decide what to do next. The loop is what makes that possible: keep a running `messages` list, append the assistant's reply (including any tool calls) and one `role: tool` message per call executed, then call the API again with the growing conversation. It stops when the model answers without requesting a tool, or after `MAX_TURNS` as a guard against a runaway loop that never converges.

### [5. Bash tool](https://github.com/tobiaschc/petite/tree/stage-05-bash-tool)

Read and Write cover files; Bash covers everything else — `ls`, `rm`, running a test suite, whatever the model decides to try. It's the one tool that converts "the model composed a shell command" into "it actually happened," which is as much power as it is risk: `subprocess.run` with `shell=True` executes literally what the model wrote.

### [6. Extract tools module](https://github.com/tobiaschc/petite/tree/stage-06-extract-tools)

Three tools and `main.py` already has a growing `if/elif` chain mixing agent-loop logic with tool-dispatch logic. This stage is pure refactor, no new behavior: `tools.py` now owns the three tool functions, their JSON specs, and a `TOOL_FUNCTIONS` dict that `execute_tool` looks up by name. Every tool added from here on touches one file, not two.

### [7. Tool classes with Pydantic](https://github.com/tobiaschc/petite/tree/stage-07-pydantic-tools)

Hand-written JSON Schema and `fn(**arguments)` can silently drift apart — nothing forces the schema a model sees to match what the function actually accepts, and a missing argument surfaces as a raw `TypeError` from inside the tool. A Pydantic model per tool fixes both at once: `model_json_schema()` generates the schema from the same class that validates the arguments, so there's one source of truth, and a bad call fails with a clear Pydantic error *before* `execute()` ever runs.

## Skills

### [8. Skills (level 1)](https://github.com/tobiaschc/petite/tree/stage-08-skills-level1)

A skill is a folder of instructions the model can load into context on demand instead of always — pasting every skill's full instructions into every prompt would blow the context window past a handful of skills. The fix is progressive disclosure: level 1 only ever loads a skill's *name* and *description* into the system prompt, nothing else, no matter how large the skill's actual instructions are. `.petite/skills/` deliberately isn't `.claude/skills/` — the `SKILL.md` *format* follows the open [Agent Skills](https://agentskills.io/specification) standard, but the folder convention here is this project's own.

### [9. Slash commands (level 2)](https://github.com/tobiaschc/petite/tree/stage-09-slash-commands)

Level 1 tells the model a skill exists; level 2 is the first way to actually load one. When a prompt starts with `/name`, that's resolved directly to a folder and its `SKILL.md` body replaces the raw prompt as the user message — no model judgment involved, the user named the skill explicitly. Every other skill stays at level 1, which matters: if two full bodies land in context at once with conflicting instructions, the model has no way to know which one to follow.

### [10. Skill arguments](https://github.com/tobiaschc/petite/tree/stage-10-skill-arguments)

A skill that always says the same thing isn't very useful — `/deploy` needs to know *which* environment. `$ARGUMENTS` captures everything typed after the skill name as one string; `$ARGUMENTS[n]`/`$n` pull out one positional argument by index. The substitution order matters more than it looks: `$ARGUMENTS[0]` is replaced before the bare `$ARGUMENTS`, because doing it the other way round would mangle `$ARGUMENTS[0]` into `"<everything>[0]"` the moment the bare pattern matched first.

### [11. Stack multiple skills](https://github.com/tobiaschc/petite/tree/stage-11-stack-skills)

Claude Code lets a prompt invoke several skills at once — `/rabbit /fox 4127` — so this project does too. The expansion rule is simple to say and easy to get subtly wrong: walk the leading `/name` tokens, keep expanding while each one resolves to a real skill, and stop at the first token that doesn't — that token and everything after becomes the shared argument text for every skill that *was* expanded. Getting this right means building a small table of cases (`/a /b 4127` vs `/a 4127 /b` vs `/a /nonexistent 4127`) and checking each one explicitly, because the three look almost identical.

### [12. Bundled scripts (level 3)](https://github.com/tobiaschc/petite/tree/stage-12-bundled-scripts)

A skill folder can hold more than `SKILL.md` — `scripts/`, `references/`, `assets/` — and none of it costs any context until the body explicitly points at it. That's level 3: a two-line body can reference a two-hundred-line script, and neither the script nor its output enters the conversation until the model actually runs it. The one wrinkle is that the body names its files with paths *relative to its own folder* (`scripts/checksum.sh`), while the agent runs from the project root — so every invoked body gets a one-line header prepended naming its folder, and the model joins the two itself when it calls Bash.

### [13. Model-invoked skills](https://github.com/tobiaschc/petite/tree/stage-13-skill-tool)

Every invocation so far needed a human to type `/name`. This stage lets the model decide: a `Skill` tool, advertised like any other, that the model calls with a name it matched against the descriptions already sitting in the system prompt. The one thing this depends on is description quality — "Database utilities" gives the model nothing to match a request against, while "use this skill when the user asks about database migration status" does. Two frontmatter flags control who's allowed to trigger a skill this way: `disable-model-invocation: true` (user only, e.g. for anything with side effects you don't want the model deciding to run) and `user-invocable: false` (model only).

### [14. Subagents](https://github.com/tobiaschc/petite/tree/stage-14-subagents)

`context: fork` runs a skill in a second, fully independent call of the same agent loop — its own empty conversation, seeded with only the skill's body, with just its final answer crossing back into the main conversation. Pulling `run_agent_loop()` out into its own function (`agent.py`) is what makes a "subagent" possible at all: it isn't a different kind of agent, just this same loop called again on a new messages list. The one real trap: a subagent must *not* get the `Skill` tool itself, or a forked skill's own folder header ("Skill: owl (located at ...)") reads to the model as an instruction to call `Skill` again — recursing forever instead of just answering.
