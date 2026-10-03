"""
Stage 12: level 3 — bundled scripts

A skill folder can hold more than SKILL.md: scripts/, references/,
assets/ — level 3 of progressive disclosure. These never enter context
on their own; the body has to point at them, and only then does the
model load/run them (here, scripts/, via the Bash tool).

A body says "Run `scripts/sha256.sh`" using a path relative to its OWN
skill folder — but the agent runs from the project root. Only telling
the model which folder that is isn't enough: models often run the
relative path as-is and get "file not found". So before the body
reaches the model, its bundled paths (scripts/, references/, assets/)
are rewritten to project-root paths, e.g. "scripts/sha256.sh" becomes
".petite/skills/badger/scripts/sha256.sh".
"""

import os
import re

import yaml
from pydantic import BaseModel, Field, field_validator

SKILLS_DIR = ".petite/skills"


class SkillMeta(BaseModel):
    """Validates a SKILL.md's frontmatter against the Agent Skills spec."""

    name: str = Field(max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = None
    compatibility: str | None = Field(default=None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        import re

        if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value):
            raise ValueError(
                f"name {value!r} must be lowercase alphanumeric with single hyphens, "
                "no leading/trailing/consecutive hyphens"
            )
        return value


def _split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            frontmatter_text = "\n".join(lines[1:i])
            body = "\n".join(lines[i + 1 :]).lstrip("\n")
            return yaml.safe_load(frontmatter_text) or {}, body

    return {}, text


def discover_skills(skills_dir=SKILLS_DIR):
    """Level 1: scan skills_dir, return validated SkillMeta for each one.

    Folders that fail validation (bad frontmatter, name/folder mismatch)
    are skipped with a warning on stderr rather than crashing the agent.
    """
    import sys

    skills = []

    if not os.path.isdir(skills_dir):
        return skills

    for entry in sorted(os.listdir(skills_dir)):
        skill_md_path = os.path.join(skills_dir, entry, "SKILL.md")
        if not os.path.isfile(skill_md_path):
            continue

        with open(skill_md_path) as f:
            frontmatter, _body = _split_frontmatter(f.read())

        try:
            meta = SkillMeta(**frontmatter)
        except Exception as e:
            print(f"[skills] skipping {entry!r}: invalid frontmatter ({e})", file=sys.stderr)
            continue

        if meta.name != entry:
            print(
                f"[skills] skipping {entry!r}: name {meta.name!r} must match folder name",
                file=sys.stderr,
            )
            continue

        skills.append(meta)

    return skills


def build_skills_system_prompt(skills):
    if not skills:
        return None

    lines = ["You have access to the following skills:", ""]
    for skill in skills:
        lines.append(f"- {skill.name}: {skill.description}")

    return "\n".join(lines)


def load_skill_body(name, skills_dir=SKILLS_DIR):
    """Level 2: resolve a skill by folder name and return its SKILL.md body.

    Returns None if the skill doesn't exist. Only this skill's body is
    ever read — the other skills stay at level 1 (name + description).
    """
    skill_md_path = os.path.join(skills_dir, name, "SKILL.md")
    if not os.path.isfile(skill_md_path):
        return None

    with open(skill_md_path) as f:
        _frontmatter, body = _split_frontmatter(f.read())

    return body.strip()


def resolve_slash_command(prompt, skills_dir=SKILLS_DIR):
    """If prompt starts with one or more "/skill-name" tokens, expand them
    all and return a list of substituted bodies, one per skill — in the
    order they appeared, each with the same trailing argument text.

    Expansion stops at the first token that isn't a real skill name; that
    token and everything after it becomes the shared $ARGUMENTS text.

    Returns None if the prompt doesn't start with a recognized skill
    invocation at all, so the caller falls back to the raw prompt.
    """
    tokens = prompt.split()

    expanded_names = []
    i = 0
    while i < len(tokens) and tokens[i].startswith("/"):
        candidate = tokens[i][1:]
        if load_skill_body(candidate, skills_dir) is None:
            break
        expanded_names.append(candidate)
        i += 1

    if not expanded_names:
        return None

    args = tokens[i:]

    return [
        _with_folder_header(name, substitute_arguments(load_skill_body(name, skills_dir), args), skills_dir)
        for name in expanded_names
    ]


def _with_folder_header(name, body, skills_dir=SKILLS_DIR):
    """Prefix a skill's (already-substituted) body with a header naming
    its own folder, and rewrite the body's bundled paths (scripts/,
    references/, assets/) to paths from the project root, where the
    agent, and so every Bash/Read call, actually runs.
    """
    folder = os.path.join(skills_dir, name)
    body = re.sub(
        r"(?<![\w./-])((?:scripts|references|assets)/[\w./-]+)",
        lambda m: os.path.join(folder, m.group(1)),
        body,
    )
    return f"Skill: {name} (located at {folder})\n\n{body}"


def substitute_arguments(body, args):
    """Replace $ARGUMENTS, $ARGUMENTS[n] and $n placeholders in a skill
    body with the given positional arguments.

    Missing indices substitute to an empty string rather than raising.
    """

    def arg_at(index):
        return args[index] if 0 <= index < len(args) else ""

    # $ARGUMENTS[n] first — a bare $ARGUMENTS replace would otherwise
    # mangle "$ARGUMENTS[0]" into "<joined args>[0]".
    body = re.sub(r"\$ARGUMENTS\[(\d+)\]", lambda m: arg_at(int(m.group(1))), body)
    body = body.replace("$ARGUMENTS", " ".join(args))
    body = re.sub(r"\$(\d+)", lambda m: arg_at(int(m.group(1))), body)

    return body
