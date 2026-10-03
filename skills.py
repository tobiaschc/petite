"""
Stage 8: skills, level 1 (advertise)

A "skill" is a folder of instructions an agent loads on demand instead of
always keeping in context — the Agent Skills open standard:
https://agentskills.io/specification

Skills live under .petite/skills/<name>/SKILL.md (petite-harness's own
folder, not Claude Code's .claude/skills/ — the SKILL.md *format* is the
generic open standard, the directory convention is implementation-specific
and this project uses its own).

Progressive disclosure has three levels; this stage implements level 1
only: scan every skill folder, parse just the YAML frontmatter (name +
description), and put that list in a system prompt so the model knows
what exists — without ever loading a SKILL.md body into context.
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
