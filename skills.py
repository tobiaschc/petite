"""
Stage 9: slash commands, level 2 (invoke)

A prompt starting with "/" invokes a skill by name: the first word after
the slash resolves to .petite/skills/<name>/SKILL.md, and that skill's
body (everything after the closing "---") replaces the raw prompt as the
user message. Only the invoked skill's body is ever loaded — every other
skill stays at level 1 (name + description in the system prompt), so the
model never sees two conflicting sets of instructions at once.
"""

import os

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
    """If prompt starts with '/', resolve the first word as a skill name
    and return that skill's body to use as the user message content.

    Returns None if the prompt isn't a slash command or the named skill
    can't be found, so the caller falls back to the raw prompt.
    """
    if not prompt.startswith("/"):
        return None

    rest = prompt[1:].strip()
    if not rest:
        return None

    skill_name = rest.split()[0]
    return load_skill_body(skill_name, skills_dir)
