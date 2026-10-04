"""Generate the parts of the site that come from the code itself, so they never drift:

- each stage page's diff ("The code"), straight from the stage tags
- the system map on the landing page and on every stage page (its own part highlighted)
- the line count on the landing page

Run from a checkout of main: `just docs`. Generated blocks sit between
<!-- generated:NAME --> ... <!-- /generated:NAME --> markers; everything else is hand-written.
"""

import html
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SITE = "https://tobiaschc.github.io/petite/"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CODE_PATHS = ["*.py", ".petite"]


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def stage_tags():
    return git("tag", "-l", "stage-*", "--sort=v:refname").split()


# ---- the system map: one picture of the whole agent, each part labelled with its stages ----

MAP = {
    "cols": 5,
    "rowGap": 118,
    "llm": [
        {"id": "M", "label": "the model", "span": [0, 3]},
        {"id": "M2", "label": "a subagent's model", "span": [4, 4]},
    ],
    "local": [
        {"id": "P", "label": "your prompt", "col": 0, "row": 0, "badge": "1", "href": "01-talk-to-llm.html"},
        {"id": "Slash", "label": "expand /slash commands", "col": 1, "row": 0, "badge": "9–11", "href": "09-slash-commands.html"},
        {"id": "Msgs", "label": "messages + system prompt", "col": 2, "row": 0, "badge": "4", "href": "04-agent-loop.html"},
        {"id": "Val", "label": "validate the tool call", "col": 3, "row": 0, "badge": "7", "href": "07-pydantic-tools.html"},
        {"id": "Fork", "label": "fresh conversation", "col": 4, "row": 0, "badge": "14", "href": "14-subagents.html"},
        {"id": "Disc", "label": "discover skills", "col": 1, "row": 1, "badge": "8", "href": "08-skills-level1.html"},
        {"id": "Scripts", "label": "bundled scripts (via Bash)", "col": 2, "row": 1, "badge": "12", "href": "12-bundled-scripts.html"},
        {"id": "Tools", "label": "Read · Write · Bash · Skill", "col": 3, "row": 1, "badge": "2–6 · 13", "href": "02-read-tool.html"},
    ],
    "edges": [
        ["P", "Slash"],
        ["Slash", "Msgs"],
        ["Disc", "Msgs", "skill list"],
        ["Msgs", "M", "request"],
        ["M", "Val", "text or a tool call"],
        ["Val", "Tools", "run it"],
        ["Tools", "Msgs", "result"],
        ["Tools", "Scripts"],
        ["Tools", "Fork", "Skill (fork)"],
        ["Fork", "M2", "request"],
        ["M2", "Fork", "final answer"],
        ["Fork", "Tools"],
    ],
}
HIGHLIGHT = {1: ["P"], 2: ["Tools"], 3: ["Tools"], 4: ["Msgs"], 5: ["Tools"], 6: ["Tools"], 7: ["Val"],
             8: ["Disc"], 9: ["Slash"], 10: ["Slash"], 11: ["Slash"], 12: ["Scripts"], 13: ["Tools"], 14: ["Fork"]}


def map_block(highlight=None, href_prefix=""):
    spec = json.loads(json.dumps(MAP))
    for n in spec["local"]:
        n["href"] = href_prefix + n["href"]
    if highlight:
        spec["highlight"] = highlight
    return ('<div class="diagram map"></div>\n  <script type="application/json" class="diagram-spec">\n'
            + json.dumps(spec, ensure_ascii=False) + "\n  </script>")


# ---- diffs ----

def render_diff(diff):
    files, cur = [], None
    for line in diff.splitlines():
        if line.startswith("diff --git"):
            cur = {"name": line.split(" b/", 1)[1], "lines": [], "add": 0, "del": 0}
            files.append(cur)
        elif cur is None or line.startswith(("index ", "--- ", "+++ ", "new file", "deleted file", "similarity", "rename ")):
            continue
        elif line.startswith("@@"):
            cur["lines"].append(("hunk", "⋯ " + line.split("@@")[2].strip()))
        elif line.startswith("+"):
            cur["add"] += 1
            cur["lines"].append(("add", line[1:]))
        elif line.startswith("-"):
            cur["del"] += 1
            cur["lines"].append(("del", line[1:]))
        elif line.startswith("\\"):
            continue
        else:
            cur["lines"].append(("ctx", line[1:]))
    out = []
    for f in files:
        rows = "".join(
            f'<span class="d-{kind}">{html.escape(text) or " "}</span>' for kind, text in f["lines"]
        )
        out.append(
            f'<details class="diff" open><summary><code>{html.escape(f["name"])}</code>'
            f'<span class="d-stat"><span class="d-plus">+{f["add"]}</span> <span class="d-minus">−{f["del"]}</span></span></summary>'
            f'<pre class="diff-body">{rows}</pre></details>'
        )
    return files, "\n  ".join(out)


def diff_block(n, tags):
    tag = tags[n - 1]
    base = tags[n - 2] if n > 1 else EMPTY_TREE
    diff = git("diff", "--no-color", "-U3", base, tag, "--", *CODE_PATHS)
    files, body = render_diff(diff)
    add = sum(f["add"] for f in files)
    rem = sum(f["del"] for f in files)
    what = "the whole program at this stage" if n == 1 else f"what changed since stage {n - 1}"
    return (
        "<h2>The solution</h2>\n  "
        '<p class="diff-intro">Try the task above first. When you want to compare, this is '
        f"exactly {what} (<code>just diff {max(n - 1, 1)} {n}</code> shows the same).</p>\n  "
        '<details class="solution"><summary><span class="show">Show the solution</span>'
        '<span class="hide">Hide the solution</span> '
        f'<span class="d-stat"><span class="d-plus">+{add}</span> <span class="d-minus">−{rem}</span> lines</span>'
        f"</summary>\n  {body}\n  </details>"
    )


# ---- link previews (Open Graph / Twitter cards), from each page's own title and description ----

def clean_description(desc):
    """Descriptions were cut at a fixed length, sometimes mid-word: end them on a word, with an ellipsis."""
    desc = re.sub(r"<[^>]+>", "", desc).strip()  # some had inline <code> tags
    if desc.endswith((".", "!", "?", "…")):
        return desc
    cut = desc[: desc.rfind(" ")].rstrip(" ,;:—-")
    return cut if cut.endswith((".", "!", "?")) else cut + "…"


def og_block(page, url):
    title = html.unescape(re.search(r"<title>(.*?)</title>", page, re.S).group(1).strip())
    desc = clean_description(html.unescape(re.search(r'<meta name="description" content="(.*?)">', page, re.S).group(1).strip()))
    tags = [
        ("property", "og:type", "website"),
        ("property", "og:site_name", "petite"),
        ("property", "og:title", title),
        ("property", "og:description", desc),
        ("property", "og:url", url),
        ("property", "og:image", SITE + "assets/og.png"),
        ("property", "og:image:width", "1200"),
        ("property", "og:image:height", "630"),
        ("name", "twitter:card", "summary_large_image"),
    ]
    return "\n".join(f'<meta {k}="{v}" content="{html.escape(c, quote=True)}">' for k, v, c in tags)


def fix_description(page):
    m = re.search(r'<meta name="description" content="(.*?)">', page, re.S)
    fixed = html.escape(clean_description(html.unescape(m.group(1))), quote=False).replace('"', "&quot;")
    return page.replace(m.group(0), f'<meta name="description" content="{fixed}">')


# ---- page plumbing ----

def put(page, name, content, before):
    """Replace the generated block `name`, or insert it right before the first `before` match."""
    start, end = f"<!-- generated:{name} -->", f"<!-- /generated:{name} -->"
    block = f"{start}\n  {content}\n  {end}"
    if start in page:
        return re.sub(re.escape(start) + r".*?" + re.escape(end), lambda _m: block, page, flags=re.S)
    for marker in before:
        if marker in page:
            return page.replace(marker, f"{block}\n\n  {marker}", 1)
    raise SystemExit(f"no place for {name}")


def main():
    tags = stage_tags()
    for path in sorted((DOCS / "stages").glob("*.html")):
        n = int(path.name[:2])
        page = path.read_text()
        page = put(page, "diff", diff_block(n, tags), ["<h2>Try it</h2>"])
        fits = ('<h2>Where this fits</h2>\n  <p class="map-intro">The whole agent; this stage builds the highlighted part. '
                'Click any part to jump to its stage.</p>\n  ' + map_block(HIGHLIGHT[n]))
        page = put(page, "map", fits, ["<h2>References</h2>", '<div class="stage-nav">'])
        page = fix_description(page)
        page = put(page, "og", og_block(page, f"{SITE}stages/{path.name}"), ['<link rel="stylesheet"'])
        path.write_text(page)
        print(f"stage {n:2}: diff + map")

    index = DOCS / "index.html"
    page = index.read_text()
    agent_files = [f for f in git("ls-files", "*.py").split() if "/" not in f]  # the agent, not scripts/
    loc = sum(git("show", f"HEAD:{f}").count("\n") for f in agent_files)
    page = re.sub(r'(<span class="loc">)\d+(</span>)', rf"\g<1>{loc}\g<2>", page)
    overview = ('<h2 id="map">How it works</h2>\n  <p class="map-intro">One run of the agent: your prompt becomes messages, '
                "the model answers with text or a tool call, petite runs the tool on your machine and feeds the result "
                "back, until the model just answers. The badge on each part is the stage that builds it; click to jump "
                "there.</p>\n  " + map_block(href_prefix="stages/"))
    page = put(page, "map", overview, ["<h2>Setup</h2>"])
    page = put(page, "og", og_block(page, SITE), ['<link rel="stylesheet"'])
    index.write_text(page)
    print(f"index: {loc} lines of Python, map")


if __name__ == "__main__":
    main()
