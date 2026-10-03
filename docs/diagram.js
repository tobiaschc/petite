// petite's lane diagrams: the LLM provider on top, your machine below, and the
// network in between. Every arrow that crosses the gap is a real HTTPS request
// or response; everything else happens on your machine.
//
// A page describes its diagram in JSON:
//   <div class="diagram"></div>
//   <script type="application/json" class="diagram-spec">
//     { "cols": 4,
//       "llm":   [{"id": "M", "label": "model writes the next message"}],
//       "local": [{"id": "U", "label": "your prompt", "col": 0, "row": 0}, ...],
//       "edges": [["U", "M", "request: ..."], ["M", "Chk", "response: ..."], ...] }
//   </script>
// Edges become <path data-id="L_from_to_0"> so rabbit.js can walk them.

const NS = "http://www.w3.org/2000/svg";
const W = 680; // viewBox width
const PAD = 16;
const LLM_TOP = 26; // band title above the nodes
const NODE_H = 40;
const ROW_GAP = 86;
const GAP = 112; // the network between the two bands
const C = {
  llmBand: "#fffaf0", llmBorder: "#e9b81f", llmNode: "#fff4c9",
  localBand: "#f6f1e4", localBorder: "#95BAFF", localNode: "#fffdf7",
  ink: "#1a1a1a", muted: "#6b675d", local: "#8aa6dc", cross: "#5b7fd4",
};

const el = (tag, attrs = {}, parent) => {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
};

function wrap(text, max) {
  const lines = [];
  for (const part of String(text).split("\n")) {
    let line = "";
    for (const word of part.split(" ")) {
      if (line && (line + " " + word).length > max) {
        lines.push(line);
        line = word;
      } else line = line ? line + " " + word : word;
    }
    lines.push(line);
  }
  return lines;
}

function textBlock(parent, x, y, lines, attrs) {
  const t = el("text", { x, y, "text-anchor": "middle", ...attrs }, parent);
  const lh = parseFloat(attrs["font-size"]) * 1.25;
  lines.forEach((line, i) => {
    const s = el("tspan", { x, dy: i === 0 ? -((lines.length - 1) * lh) / 2 + lh * 0.35 : lh }, t);
    s.textContent = line;
  });
  return t;
}

function render(container, spec) {
  const cols = spec.cols;
  const colW = (W - 2 * PAD) / cols;
  const cx = (col) => PAD + (col + 0.5) * colW;
  const rows = Math.max(...spec.local.map((n) => n.row ?? 0)) + 1;

  const llmY = LLM_TOP + 8; // top of the LLM nodes
  const llmBottom = llmY + NODE_H + 14;
  const localTop = llmBottom + GAP;
  const rowY = (row) => localTop + 16 + row * ROW_GAP; // top of a local node
  const H = rowY(rows - 1) + NODE_H + 34;

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", class: "lanes" });
  svg.style.maxWidth = "100%";
  svg.style.height = "auto";
  container.replaceChildren(svg);
  const root = el("g", {}, svg);

  const defs = el("defs", {}, root);
  for (const [id, color] of [["arr-local", C.local], ["arr-cross", C.cross]]) {
    const size = id === "arr-cross" ? 9 : 7; // fixed size, not scaled by the stroke width
    const m = el("marker", { id, viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: size, markerHeight: size, markerUnits: "userSpaceOnUse", orient: "auto-start-reverse" }, defs);
    el("path", { d: "M0,0 L10,5 L0,10 z", fill: color }, m);
  }

  // bands
  el("rect", { x: 2, y: 2, width: W - 4, height: llmBottom - 2, rx: 10, fill: C.llmBand, stroke: C.llmBorder, "stroke-dasharray": "6 4" }, root);
  el("rect", { x: 2, y: localTop, width: W - 4, height: H - localTop - 2, rx: 10, fill: C.localBand, stroke: C.localBorder }, root);
  const title = (x, y, s) => (el("text", { x, y, "font-size": 11, "font-weight": 600, "letter-spacing": "0.06em", fill: C.muted }, root).textContent = s);
  title(14, 19, "LLM PROVIDER · OpenRouter → Claude");
  title(14, H - 12, "YOUR MACHINE · petite");
  // legend, top right, on the LLM band's title line: what a bold arrow means
  const legend = el("g", {}, root);
  const lt = el("text", { x: W - 14, y: 19, "text-anchor": "end", "font-size": 10.5, fill: C.muted, "font-style": "italic" }, legend);
  lt.textContent = "= over the internet (HTTPS)";
  const lw = lt.getComputedTextLength();
  el("line", { x1: W - 14 - lw - 30, y1: 15.5, x2: W - 14 - lw - 6, y2: 15.5, stroke: C.cross, "stroke-width": 2.4 }, legend);

  // nodes
  const nodes = {};
  const drawNode = (n, x, y, w, kind) => {
    const g = el("g", {}, root);
    const lines = wrap(n.label, Math.max(10, Math.floor(w / 7.2)));
    const fill = kind === "llm" ? C.llmNode : C.localNode;
    const stroke = kind === "llm" ? C.llmBorder : C.localBorder;
    const rx = n.shape === "decision" ? NODE_H / 2 : 6;
    el("rect", { x, y, width: w, height: NODE_H, rx, fill, stroke }, g);
    if (n.shape === "file") el("path", { d: `M${x + w - 12},${y} l12,12`, stroke, fill: "none" }, g);
    textBlock(g, x + w / 2, y + NODE_H / 2, lines, { "font-size": lines.length > 1 ? 11.5 : 12.5, fill: C.ink });
    nodes[n.id] = { x, y, w, h: NODE_H, kind, cx: x + w / 2 };
  };
  for (const n of spec.llm) {
    const [a, b] = n.span ?? [0, cols - 1];
    const x = cx(a) - colW / 2 + 10;
    drawNode(n, x, llmY, cx(b) + colW / 2 - 10 - x, "llm");
  }
  for (const n of spec.local) {
    const w = n.w ?? colW - 18; // a node may ask to be wider than its column
    drawNode(n, cx(n.col) - w / 2, rowY(n.row ?? 0), w, "local");
  }

  // edges: spread several arrows that share a node side, so they don't overlap
  const usage = {};
  const slot = (id, side) => {
    const k = id + side;
    usage[k] = (usage[k] ?? 0) + 1;
    return usage[k] - 1;
  };
  const edges = spec.edges.map(([from, to, label]) => ({ from, to, label, a: nodes[from], b: nodes[to] }));
  const crossCount = {};
  for (const e of edges) if (e.a.kind !== e.b.kind) {
    const local = e.a.kind === "local" ? e.from : e.to;
    crossCount[local] = (crossCount[local] ?? 0) + 1;
  }
  const seen = {};
  let crossIndex = 0;

  for (const e of edges) {
    const key = `${e.from}_${e.to}`;
    const n = (seen[key] = (seen[key] ?? -1) + 1);
    const cross = e.a.kind !== e.b.kind;
    let d, lx, ly;
    if (cross) {
      const local = e.a.kind === "local" ? e.a : e.b;
      const llm = e.a.kind === "llm" ? e.a : e.b;
      const localId = e.a.kind === "local" ? e.from : e.to;
      const k = crossCount[localId];
      const i = slot(localId, "top");
      const off = k > 1 ? (i - (k - 1) / 2) * 44 : 0;
      const x1 = local.cx + off;
      const x2 = Math.min(llm.x + llm.w - 14, Math.max(llm.x + 14, x1));
      const yl = local.y, yt = llm.y + llm.h;
      const up = e.a.kind === "local";
      const [sx, sy, ex, ey] = up ? [x1, yl, x2, yt] : [x2, yt, x1, yl];
      const my = (sy + ey) / 2;
      d = `M${sx},${sy} C${sx},${my} ${ex},${my} ${ex},${ey}`;
      lx = (x1 + x2) / 2;
      ly = (yt + yl) / 2 + (crossIndex++ % 2 ? 15 : -15);
    } else if (e.a.y === e.b.y) {
      const right = e.b.cx > e.a.cx;
      const sx = right ? e.a.x + e.a.w : e.a.x;
      const ex = right ? e.b.x : e.b.x + e.b.w;
      const y = e.a.y + NODE_H / 2 + slot(e.from, right ? "r" : "l") * 6;
      d = `M${sx},${y} L${ex},${y}`;
      lx = (sx + ex) / 2;
      ly = y - 9;
    } else {
      const down = e.b.y > e.a.y;
      const sx = e.a.cx, sy = down ? e.a.y + NODE_H : e.a.y;
      const ex = e.b.cx, ey = down ? e.b.y : e.b.y + NODE_H;
      const my = (sy + ey) / 2;
      d = `M${sx},${sy} C${sx},${my} ${ex},${my} ${ex},${ey}`;
      lx = (sx + ex) / 2;
      ly = my;
    }
    const path = el("path", {
      d, fill: "none", "data-id": `L_${e.from}_${e.to}_${n}`,
      stroke: cross ? C.cross : C.local, "stroke-width": cross ? 2.4 : 1.3,
      "marker-end": `url(#${cross ? "arr-cross" : "arr-local"})`,
    }, root);
    path.classList.add(cross ? "edge-cross" : "edge-local");
    if (e.label) {
      const lines = wrap(e.label, cross ? 22 : 16);
      const g = el("g", {}, root);
      const t = textBlock(g, lx, ly, lines, { "font-size": cross ? 11 : 10.5, fill: cross ? C.ink : C.muted });
      const b = t.getBBox();
      const r = el("rect", { x: b.x - 4, y: b.y - 2, width: b.width + 8, height: b.height + 4, rx: 4, fill: cross ? "#ffffff" : C.localBand, opacity: 0.92 });
      g.insertBefore(r, t); // label background behind its text
    }
  }
}

for (const container of document.querySelectorAll(".diagram")) {
  const spec = container.nextElementSibling;
  if (spec?.classList.contains("diagram-spec")) render(container, JSON.parse(spec.textContent));
}
