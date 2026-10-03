<p align="center">
  <img src="assets/banner.svg" alt="petite" width="100%">
</p>

# petite

A tiny AI coding agent, built from scratch, one commit per concept.

Read the git history top to bottom to see a Claude-Code-like assistant emerge from a 40-line script: LLM calls, tool calling, the agent loop, skills. For the story behind each stage, see [docs/walkthrough.md](docs/walkthrough.md).

## Stages

### Base agent

- [x] 1. [Talk to an LLM](https://github.com/tobiaschc/petite/tree/stage-01-talk-to-llm) — prompt in, response out, no tools, no loop
- [x] 2. [Read tool](https://github.com/tobiaschc/petite/tree/stage-02-read-tool) — model requests a file, you execute and return it
- [x] 3. [Write tool](https://github.com/tobiaschc/petite/tree/stage-03-write-tool) — same, for writing files
- [x] 4. [Agent loop](https://github.com/tobiaschc/petite/tree/stage-04-agent-loop) — keep looping until the model stops requesting tools
- [x] 5. [Bash tool](https://github.com/tobiaschc/petite/tree/stage-05-bash-tool) — same, for shell commands
- [x] 6. [Extract tools module](https://github.com/tobiaschc/petite/tree/stage-06-extract-tools) — dispatch table instead of `if/elif` soup
- [x] 7. [Tool classes with Pydantic](https://github.com/tobiaschc/petite/tree/stage-07-pydantic-tools) — schema + validation from one model per tool

### Skills

- [x] 8. [Skills (level 1)](https://github.com/tobiaschc/petite/tree/stage-08-skills-level1) — `.petite/skills/*/SKILL.md`, validated with Pydantic, advertised as name + description
- [x] 9. [Slash commands (level 2)](https://github.com/tobiaschc/petite/tree/stage-09-slash-commands) — load a skill's full body on demand
- [x] 10. [Skill arguments](https://github.com/tobiaschc/petite/tree/stage-10-skill-arguments) — `$ARGUMENTS`, `$ARGUMENTS[n]`, `$n` placeholders substituted in the body
- [x] 11. [Stack multiple skills](https://github.com/tobiaschc/petite/tree/stage-11-stack-skills) — `/rabbit /fox 4127` expands both, sharing trailing args
- [x] 12. [Bundled scripts (level 3)](https://github.com/tobiaschc/petite/tree/stage-12-bundled-scripts) — `scripts/` loaded only when the body points at them, via a folder-path header
- [x] 13. [Model-invoked skills](https://github.com/tobiaschc/petite/tree/stage-13-skill-tool) — the `Skill` tool, plus `disable-model-invocation` / `user-invocable` controls
- [x] 14. [Subagents](https://github.com/tobiaschc/petite/tree/stage-14-subagents) — `context: fork` runs a skill in its own isolated conversation

## Running it

```bash
uv sync
export OPENROUTER_API_KEY=sk-or-v1-...
uv run main.py -p "What does this project do?"
```

Any OpenAI-compatible endpoint works — override `OPENROUTER_BASE_URL` / `MODEL`.

Free models: https://openrouter.ai/models?q=free&output_modalities=text (slugs change — a 404 means pick a new one).

## Why

Most "build your own agent" content either hides the hard parts behind a framework, or dumps a finished repo on you. Here every commit is small enough to read in two minutes.

## References

- [Claude Code tools reference](https://code.claude.com/docs/en/tools-reference) — the real tool set (`Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`...) this project is inspired by, scaled down to teachable size.
- [OpenRouter quickstart](https://openrouter.ai/docs/quickstart#using-the-openrouter-api) — the OpenAI-compatible API this project talks to by default.
- [Agent Skills specification](https://agentskills.io/specification) — the open, vendor-neutral SKILL.md format this project implements (own folder convention, standard file format).
- [Claude Code: pass arguments to skills](https://code.claude.com/docs/en/skills#pass-arguments-to-skills) — the `$ARGUMENTS` / `$0` placeholders and multi-skill stacking convention these stages implement.
- [Agent Skills: optional directories](https://agentskills.io/specification#optional-directories) — the `scripts/` / `references/` / `assets/` convention for level-3 disclosure.
- [Agent Skills: file references](https://agentskills.io/specification#file-references) — relative-path convention for files a skill body points at.
- [Claude Code: control who invokes a skill](https://code.claude.com/docs/en/skills#control-who-invokes-a-skill) — the `disable-model-invocation` / `user-invocable` frontmatter fields this stage implements.
- [Claude Code: run skills in a subagent](https://code.claude.com/docs/en/skills#run-skills-in-a-subagent) — the `context: fork` field this stage implements.
