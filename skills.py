"""
Stage 11: stacking multiple skills in one prompt

A prompt can invoke more than one skill at once: "/rabbit /fox 4127"
loads both bodies, and the trailing "4127" reaches each of them as
$ARGUMENTS. Expansion runs left to right from the start of the prompt —
every token that names a real skill gets expanded; the first token that
doesn't name a skill ends the run, and it (plus everything after it)
becomes the shared argument text for every skill that WAS expanded.

  "/rabbit /fox 4127"        -> expands [rabbit, fox], args = "4127"
  "/rabbit 4127 /fox"        -> expands [rabbit],       args = "4127 /fox"
  "/rabbit /owl 4127" (no owl skill) -> expands [rabbit], args = "/owl 4127"
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

    return [substitute_arguments(load_skill_body(name, skills_dir), args) for name in expanded_names]


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
