"""
Stage 1: Talk to an LLM

The smallest possible version of an AI coding assistant: take a prompt
from the command line, send it to an LLM, print the response.

No tools yet. No loop. Just a single request/response round trip, using
the OpenAI SDK pointed at OpenRouter (any OpenAI-compatible API works the
same way).
"""

import argparse
import os
import sys

from openai import OpenAI

API_KEY = os.getenv("OPENROUTER_API_KEY")
BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("MODEL", "anthropic/claude-haiku-4.5")


def main():
    parser = argparse.ArgumentParser(description="petite-harness: a tiny AI coding assistant")
    parser.add_argument("-p", "--prompt", required=True, help="the task to ask the model")
    args = parser.parse_args()

    if not API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

    print(f"[main] sending prompt to {MODEL}", file=sys.stderr)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": args.prompt}],
    )

    if not response.choices:
        raise RuntimeError("no choices in response")

    print(response.choices[0].message.content)


if __name__ == "__main__":
    main()
