"""
Stage 10: skill arguments ($ARGUMENTS, $0, $1, ...)

A slash command can pass arguments after the skill name:
"/feed rabbit carrots" invokes "feed" with args ["rabbit", "carrots"].
The body can reference them with placeholders, substituted before the
body is sent to the model:

  $ARGUMENTS         everything after the skill name, joined by spaces
  $ARGUMENTS[0], [1] a single argument, by position
  $0, $1, ...        shorthand for the same thing

Order matters when substituting: $ARGUMENTS[0] must be handled before the
bare $ARGUMENTS, or a naive string replace would mangle it into
"rabbit carrots[0]".
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
    """If prompt starts with '/', resolve the first word as a skill name,
    substitute any argument placeholders in its body, and return that as
    the user message content.

    Returns None if the prompt isn't a slash command or the named skill
    can't be found, so the caller falls back to the raw prompt.
    """
    if not prompt.startswith("/"):
        return None

    rest = prompt[1:].strip()
    if not rest:
        return None

    parts = rest.split()
    skill_name, args = parts[0], parts[1:]

    body = load_skill_body(skill_name, skills_dir)
    if body is None:
        return None

    return substitute_arguments(body, args)


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
