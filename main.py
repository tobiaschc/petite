"""
Stage 14: subagents

The loop that used to live here moved to agent.py's run_agent_loop(), so
the Skill tool can call it again for a context: fork skill's own,
separate conversation. main() is now just: build the initial messages,
run the loop once, print the answer.
"""

import argparse
import sys

from agent import run_agent_loop
from skills import build_skills_system_prompt, discover_skills, resolve_slash_command
from tools import TOOLS, execute_tool


def main():
    parser = argparse.ArgumentParser(description="petite: a tiny AI coding assistant")
    parser.add_argument(
        "-p", "--prompt", required=True, help="the task to ask the model"
    )
    args = parser.parse_args()

    skill_bodies = resolve_slash_command(args.prompt)
    if skill_bodies is not None:
        print(
            f"[agent] resolved {len(skill_bodies)} skill invocation(s)", file=sys.stderr
        )
        messages = [{"role": "user", "content": body} for body in skill_bodies]
    else:
        messages = [{"role": "user", "content": args.prompt}]

    skills = discover_skills()
    system_prompt = build_skills_system_prompt(skills)
    if system_prompt:
        print(f"[agent] advertising {len(skills)} skill(s)", file=sys.stderr)
        messages.insert(0, {"role": "system", "content": system_prompt})

    answer = run_agent_loop(messages, TOOLS, execute_tool, label="agent")
    print(answer)


if __name__ == "__main__":
    main()
