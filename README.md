<p align="center">
  <img src="assets/banner.svg" alt="petite" width="100%">
</p>

# petite

A tiny AI coding agent, built from scratch, one commit per concept.

**[tobiaschc.github.io/petite](https://tobiaschc.github.io/petite/)** — stage-by-stage walkthrough, diagrams, and how to replicate it yourself.

## Quick start

Needs [uv](https://docs.astral.sh/uv/) and [just](https://github.com/casey/just), plus an
[OpenRouter](https://openrouter.ai/) API key (any OpenAI-compatible endpoint works: set
`OPENROUTER_BASE_URL` and `MODEL` in `.env`).

```bash
git clone https://github.com/tobiaschc/petite && cd petite
just setup                          # installs dependencies, creates .env: fill in OPENROUTER_API_KEY
just run "What does this project do?"
```

## The stages

Every stage is a tagged commit that runs on its own. `just stage N` checks it out into
`.stages/NN` (a git worktree, so this checkout stays on `main`); `just run "..."` inside that
folder runs that stage's code. `just diff 3 4` shows what a stage changed.

| # | Stage |
|---|-------|
| 1 | [Talk to an LLM](https://tobiaschc.github.io/petite/stages/01-talk-to-llm.html) |
| 2 | [Read tool](https://tobiaschc.github.io/petite/stages/02-read-tool.html) |
| 3 | [Write tool](https://tobiaschc.github.io/petite/stages/03-write-tool.html) |
| 4 | [Agent loop](https://tobiaschc.github.io/petite/stages/04-agent-loop.html) |
| 5 | [Bash tool](https://tobiaschc.github.io/petite/stages/05-bash-tool.html) |
| 6 | [Extract tools module](https://tobiaschc.github.io/petite/stages/06-extract-tools.html) |
| 7 | [Tool classes with Pydantic](https://tobiaschc.github.io/petite/stages/07-pydantic-tools.html) |
| 8 | [Skills (level 1)](https://tobiaschc.github.io/petite/stages/08-skills-level1.html) |
| 9 | [Slash commands (level 2)](https://tobiaschc.github.io/petite/stages/09-slash-commands.html) |
| 10 | [Skill arguments](https://tobiaschc.github.io/petite/stages/10-skill-arguments.html) |
| 11 | [Stack multiple skills](https://tobiaschc.github.io/petite/stages/11-stack-skills.html) |
| 12 | [Bundled scripts (level 3)](https://tobiaschc.github.io/petite/stages/12-bundled-scripts.html) |
| 13 | [Model-invoked skills](https://tobiaschc.github.io/petite/stages/13-skill-tool.html) |
| 14 | [Subagents](https://tobiaschc.github.io/petite/stages/14-subagents.html) |

## License

[MIT](LICENSE)
