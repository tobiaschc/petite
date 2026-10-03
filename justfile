# petite — recipes for following along or replicating a stage.
#
# Stage tags look like "08" or "stage-08-skills-level1" — `just list`
# shows the full names; `stage`/`diff` accept either the short number
# or the full tag.
#
# `just stage 4` puts that stage's code in .stages/04 (a git worktree), so
# this checkout stays on main and this justfile works from any stage.

# .env (OPENROUTER_API_KEY...) is exported to every recipe: early stages
# read the environment directly, they don't load .env themselves.
set dotenv-load

default:
    @just --list

# Install dependencies (uv sync) and create .env if it doesn't exist yet.
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    uv sync
    if [ ! -f .env ]; then
        cp .env.example .env
        echo "Created .env — fill in your OPENROUTER_API_KEY before running 'just run'."
    fi

# Run the agent: just run "What does this project do?" (inside .stages/NN: that stage's code)
run prompt:
    #!/usr/bin/env bash
    set -euo pipefail
    cd "{{invocation_directory()}}"
    [ -f main.py ] || cd "{{justfile_directory()}}"
    uv run main.py -p "{{prompt}}"

# List every stage tag, in order.
list:
    @git tag -l 'stage-*' --sort=v:refname

# A stage's exact snapshot in .stages/NN, main stays checked out: just stage 8
stage name:
    #!/usr/bin/env bash
    set -euo pipefail
    tag=$(just _resolve-tag "{{name}}")
    dir=".stages/$(echo "$tag" | cut -d- -f2)"
    if [ ! -d "$dir" ]; then
        git worktree add --quiet --detach "$dir" "$tag"
    fi
    echo "$tag is in $dir — cd $dir, then: just run \"...\""

# Remove every .stages/NN worktree.
clean-stages:
    #!/usr/bin/env bash
    set -euo pipefail
    for dir in .stages/*/; do
        [ -d "$dir" ] && git worktree remove --force "$dir"
    done
    rm -rf .stages
    git worktree prune

# Diff two stages: just diff 8 9  (or: just diff stage-08-skills-level1 stage-09-slash-commands)
diff a b:
    #!/usr/bin/env bash
    set -euo pipefail
    tag_a=$(just _resolve-tag "{{a}}")
    tag_b=$(just _resolve-tag "{{b}}")
    git diff "$tag_a" "$tag_b"

# Internal: resolve "8" or "08" or a full tag name to its exact tag.
_resolve-tag name:
    #!/usr/bin/env bash
    set -euo pipefail
    if git rev-parse -q --verify "refs/tags/{{name}}" >/dev/null; then
        echo "{{name}}"
        exit 0
    fi
    padded=$(printf "%02d" "{{name}}" 2>/dev/null || true)
    match=$(git tag -l "stage-${padded}-*" | head -1)
    if [ -z "$match" ]; then
        echo "no stage tag matches '{{name}}' — see 'just list'" >&2
        exit 1
    fi
    echo "$match"

# Regenerate the site's code-derived parts: per-stage diffs, the system map, the line count.
docs:
    python3 scripts/build_docs.py
