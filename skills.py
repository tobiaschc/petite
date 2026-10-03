"""
Stage 13: model-invoked skills (the Skill tool)

Every invocation so far needed the user to type "/name". Now the model
can invoke a skill itself: it sees the name + description of every skill
in the system prompt (level 1, unchanged), and when one matches the
user's request, it calls a "Skill" tool with that name — exactly like it
calls Read or Bash — and we hand back that skill's body as the tool
result, with the same folder-header + argument substitution as before.

This only works if descriptions say WHEN to use a skill, not just what
it does — "Database utilities" gives the model nothing to match a
request against; "Use this skill when the user asks about database
migration status" does.

Invocation control (Claude Code extension, not core to the open spec):
two optional frontmatter flags decide who's allowed to trigger a skill:

  disable-model-invocation: true   only "/name" can trigger it
  user-invocable: false            only the Skill tool can trigger it

Useful for a skill with side effects you don't want the model deciding
to run on its own (disable-model-invocation), or background knowledge
that isn't a meaningful "/command" for a user to type (user-invocable).
"""

import os
import re

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SKILLS_DIR = ".petite/skills"


class SkillMeta(BaseModel):
    """Validates a SKILL.md's frontmatter against the Agent Skills spec."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(max_length=64)
    description: str = Field(min_length=1, max_length=1024)
    license: str | None = None
    compatibility: str | None = Field(default=None, max_length=500)
    disable_model_invocation: bool = Field(
        default=False, alias="disable-model-invocation"
    )
    user_invocable: bool = Field(default=True, alias="user-invocable")

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


def _load_skill_meta(entry, skills_dir, warn=True):
    """Read and validate one skill folder's frontmatter.

    Returns a SkillMeta, or None if the folder/SKILL.md is missing or the
    frontmatter fails validation (optionally warning on stderr).
    """
    import sys

    skill_md_path = os.path.join(skills_dir, entry, "SKILL.md")
    if not os.path.isfile(skill_md_path):
        return None

    with open(skill_md_path) as f:
        frontmatter, _body = _split_frontmatter(f.read())

    try:
        meta = SkillMeta(**frontmatter)
    except Exception as e:
        if warn:
            print(
                f"[skills] skipping {entry!r}: invalid frontmatter ({e})",
                file=sys.stderr,
            )
        return None

    if meta.name != entry:
        if warn:
            print(
                f"[skills] skipping {entry!r}: name {meta.name!r} must match folder name",
                file=sys.stderr,
            )
        return None

    return meta


def discover_skills(skills_dir=SKILLS_DIR):
    """Level 1: scan skills_dir, return validated SkillMeta for each one.

    Folders that fail validation (bad frontmatter, name/folder mismatch)
    are skipped with a warning on stderr rather than crashing the agent.
    """
    skills = []

    if not os.path.isdir(skills_dir):
        return skills

    for entry in sorted(os.listdir(skills_dir)):
        meta = _load_skill_meta(entry, skills_dir)
        if meta is not None:
            skills.append(meta)

    return skills


def build_skills_system_prompt(skills):
    if not skills:
        return None

    lines = ["You have access to the following skills:", ""]
    for skill in skills:
        lines.append(f"- {skill.name}: {skill.description}")

    lines += [
        "",
        "If a skill matches the user's request, call the Skill tool with its name",
        "and follow the instructions it returns.",
    ]

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

    Expansion stops at the first token that isn't a real, user-invocable
    skill name; that token and everything after it becomes the shared
    $ARGUMENTS text.

    Returns None if the prompt doesn't start with a recognized skill
    invocation at all, so the caller falls back to the raw prompt.
    """
    tokens = prompt.split()

    expanded_names = []
    i = 0
    while i < len(tokens) and tokens[i].startswith("/"):
        candidate = tokens[i][1:]
        meta = _load_skill_meta(candidate, skills_dir, warn=False)
        if meta is None or not meta.user_invocable:
            break
        expanded_names.append(candidate)
        i += 1

    if not expanded_names:
        return None

    args = tokens[i:]

    return [
        _with_folder_header(
            name,
            substitute_arguments(load_skill_body(name, skills_dir), args),
            skills_dir,
        )
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


def resolve_skill_invocation(name, args_text="", skills_dir=SKILLS_DIR):
    """Resolve a skill by name with a raw argument string (as the Skill
    tool receives it), substitute placeholders, and add the folder header.

    Returns None if the skill doesn't exist. Raises ValueError if the
    skill exists but has disable-model-invocation: true, so the Skill
    tool can turn that into a clear message instead of leaking the body.
    """
    meta = _load_skill_meta(name, skills_dir, warn=False)
    if meta is None:
        return None

    if meta.disable_model_invocation:
        raise ValueError(
            f"skill {name!r} can only be invoked directly by the user (/{name}), not by the model"
        )

    body = load_skill_body(name, skills_dir)
    args = args_text.split() if args_text else []
    return _with_folder_header(name, substitute_arguments(body, args), skills_dir)


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
