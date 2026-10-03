// petite's rabbit: walks along a page's Mermaid diagram, carrying in its paw
// what actually flows along each edge (the prompt, a tool call, the answer...).
//
// A page opts in with a tour, one step per edge, in order:
//   <script type="application/json" class="rabbit-tour">
//     [{"edge": "Msgs-M", "carry": "Find the expiry period..."}, ...]
//   </script>
// "edge" is "<from>-<to>" using the node ids in the Mermaid source.

const SVG_NS = "http://www.w3.org/2000/svg";
const SPEED = 0.09; // px per ms along an edge
const PAUSE = 900; // ms resting on each node
const LOOP_PAUSE = 2200; // ms before starting over

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A slim pink rabbit in a yellow outfit, walking upright like the Paris metro
// rabbit. Side view facing right, feet at y = 0.
const FUR = "#f5a3b5";
const FUR_LIGHT = "#fde3ea";
const LINE = "#8a3b52";
const SUIT = "#ffd23f";
const SUIT_SHADE = "#e9b81f";
const INK = "#2b1f24";
const BUNNY = `
<g stroke="${LINE}" stroke-width="1.1" stroke-linejoin="round" stroke-linecap="round">
  <!-- back arm, swinging -->
  <path d="M-1 -27 L-7 -22" stroke="${SUIT_SHADE}" stroke-width="3.4" fill="none"/>
  <circle cx="-7.8" cy="-21.4" r="1.9" fill="${FUR}"/>
  <!-- legs: two poses of the walk cycle -->
  <g class="legs-a">
    <path d="M-2 -14 L-6 -3" stroke="${SUIT_SHADE}" stroke-width="3.6" fill="none"/>
    <ellipse cx="-6.5" cy="-1.6" rx="3.4" ry="1.7" fill="${FUR}"/>
    <path d="M2 -14 L5 -3" stroke="${SUIT}" stroke-width="3.6" fill="none"/>
    <ellipse cx="6.8" cy="-1.6" rx="3.4" ry="1.7" fill="${FUR}"/>
  </g>
  <g class="legs-b">
    <path d="M-1 -14 L-1.5 -3" stroke="${SUIT_SHADE}" stroke-width="3.6" fill="none"/>
    <ellipse cx="-0.5" cy="-1.6" rx="3.4" ry="1.7" fill="${FUR}"/>
    <path d="M1.5 -14 L2.5 -3" stroke="${SUIT}" stroke-width="3.6" fill="none"/>
    <ellipse cx="3.8" cy="-1.6" rx="3.4" ry="1.7" fill="${FUR}"/>
  </g>
  <!-- tail -->
  <circle cx="-4.4" cy="-14.6" r="1.8" fill="${FUR_LIGHT}"/>
  <!-- body: yellow outfit -->
  <path d="M-3.5 -29 C-5 -24 -4.5 -17 -3 -13 L4 -13 C5 -18 5 -24 3.5 -29 Z" fill="${SUIT}"/>
  <!-- ears, long and upright -->
  <path d="M-1.5 -40 C-4 -48 -4 -57 -1.5 -58 C1 -59 1.5 -50 1 -40 Z" fill="${FUR}"/>
  <path d="M2.5 -40 C2 -49 4 -58 7 -58 C10 -58 8 -48 5.5 -40 Z" fill="${FUR}"/>
  <path d="M3.6 -42 C3.4 -49 5 -55 6.6 -55.2 C8 -55.3 6.8 -48 5 -42 Z" fill="${FUR_LIGHT}" stroke="none"/>
  <!-- head: a slim oval, muzzle forward -->
  <path d="M-4 -35 C-4.5 -41 0 -43.5 4 -42.5 C8.5 -41.5 11 -38 10.5 -34.5 C10 -31 6 -29.5 2 -29.8 C-1.5 -30 -3.8 -32 -4 -35 Z" fill="${FUR}"/>
  <ellipse cx="7.6" cy="-33.2" rx="3" ry="2.3" fill="${FUR_LIGHT}" stroke="none"/>
  <!-- front arm, holding the note out -->
  <path d="M1 -27 L8 -22.5" stroke="${SUIT}" stroke-width="3.4" fill="none"/>
  <circle cx="9" cy="-22" r="2" fill="${FUR}"/>
</g>
<!-- face: big surprised eye, nose, tiny mouth -->
<ellipse cx="5" cy="-37" rx="2.3" ry="2.8" fill="#fff" stroke="${LINE}" stroke-width="0.6"/>
<ellipse cx="5.8" cy="-36.8" rx="1.1" ry="1.5" fill="${INK}"/>
<ellipse cx="10.4" cy="-34.6" rx="1" ry="0.8" fill="${LINE}"/>
<path d="M8.4 -32 q0.8 0.7 1.6 0" fill="none" stroke="${LINE}" stroke-width="0.6" stroke-linecap="round"/>
`;
const SCALE = 0.85;
const NOTE_X = 9; // the note sits by the front paw
const NOTE_Y = -21;

function findEdge(svg, from, to) {
  return svg.querySelector(`path[data-id^="L_${from}_${to}_"]`);
}

/** Point `at` along `path`, in the coordinate system of `layer`. */
function pointIn(layer, path, at) {
  const p = path.getPointAtLength(at);
  const pt = new DOMPoint(p.x, p.y).matrixTransform(path.getCTM()).matrixTransform(layer.getCTM().inverse());
  return pt;
}

function buildRabbit(layer) {
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "rabbit");
  g.setAttribute("pointer-events", "none");

  const body = document.createElementNS(SVG_NS, "g");
  body.innerHTML = BUNNY;

  // the note in its paw
  const note = document.createElementNS(SVG_NS, "g");
  note.setAttribute("class", "rabbit-note");
  // inline styles, not style.css or presentation attributes: a stale cached
  // stylesheet, or Mermaid's own CSS inside the SVG, must not turn it into a
  // black box with black text
  const box = document.createElementNS(SVG_NS, "rect");
  box.setAttribute("rx", "4");
  Object.assign(box.style, { fill: "#fffdf7", stroke: "#95BAFF", strokeWidth: "1px" });
  const text = document.createElementNS(SVG_NS, "text");
  Object.assign(text.style, {
    fill: "#1a1a1a",
    fontSize: "11px",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  });
  text.setAttribute("x", "0");
  text.setAttribute("y", "0");
  note.append(box, text);

  g.append(body, note);
  layer.appendChild(g);
  return { g, body, note, box, text, legsA: body.querySelector(".legs-a"), legsB: body.querySelector(".legs-b") };
}

function setNote(r, label) {
  r.text.textContent = label;
  const b = r.text.getBBox();
  const padX = 5, padY = 3;
  // anchor the note at the rabbit's front paw, a little below and to the right
  r.text.setAttribute("x", NOTE_X + padX);
  r.text.setAttribute("y", NOTE_Y + padY + b.height * 0.78);
  r.box.setAttribute("x", NOTE_X);
  r.box.setAttribute("y", NOTE_Y);
  r.box.setAttribute("width", b.width + padX * 2);
  r.box.setAttribute("height", b.height + padY * 2);
  r.noteWidth = b.width + padX * 2;
  r.note.animate([{ opacity: 0, transform: "scale(0.85)" }, { opacity: 1, transform: "scale(1)" }], {
    duration: 220,
    easing: "ease-out",
  });
}

function place(r, pt, facingLeft, hop, stride) {
  r.g.setAttribute("transform", `translate(${pt.x}, ${pt.y - hop}) scale(${r.zoom})`);
  r.body.setAttribute("transform", `scale(${facingLeft ? -SCALE : SCALE}, ${SCALE})`);
  // run cycle: alternate the two leg poses
  r.legsA.style.display = stride ? "" : "none";
  r.legsB.style.display = stride ? "none" : "";
  // the note stays in the front paw: mirror its position when the rabbit turns around,
  // or when it would stick out of the diagram's right edge
  const w = (NOTE_X + (r.noteWidth || 0)) * r.zoom;
  const onLeft = facingLeft ? pt.x - w >= r.left : pt.x + w > r.right && pt.x - w >= r.left;
  r.note.setAttribute("transform", onLeft ? `translate(${-2 * NOTE_X - (r.noteWidth || 0)}, 0)` : "");
}

function walk(r, layer, path, state) {
  const len = path.getTotalLength();
  const duration = Math.max(700, len / SPEED);
  return new Promise((resolve) => {
    let start = null;
    let last = pointIn(layer, path, 0);
    const frame = (now) => {
      if (state.paused) {
        start = start === null ? null : start + 16;
        return requestAnimationFrame(frame);
      }
      start ??= now;
      const t = Math.min(1, (now - start) / duration);
      const pt = pointIn(layer, path, t * len);
      const hop = Math.abs(Math.sin((t * len) / 9)) * 1.6; // a light bounce in each step
      const facingLeft = pt.x < last.x - 0.01 ? true : pt.x > last.x + 0.01 ? false : state.facingLeft;
      state.facingLeft = facingLeft;
      place(r, pt, facingLeft, hop, Math.floor((t * len) / 9) % 2 === 0); // alternate steps
      last = pt;
      if (t < 1) requestAnimationFrame(frame);
      else resolve();
    };
    requestAnimationFrame(frame);
  });
}

async function run(container, tour) {
  const svg = container.querySelector("svg");
  svg.style.overflow = "visible";
  const layer = svg.querySelector("g") || svg; // top-level group: drawn above nodes once appended last
  const steps = tour
    .map((s) => {
      const [from, to] = s.edge.split("-");
      return { ...s, path: findEdge(svg, from, to) };
    })
    .filter((s) => s.path || console.warn("rabbit: no edge", s.edge));
  if (!steps.length) return;

  const r = buildRabbit(layer);
  // Wide diagrams are shrunk to fit small screens; keep the rabbit and its note
  // about the same size on screen by undoing (part of) that shrink.
  const fit = () => {
    const shown = svg.getBoundingClientRect().width / svg.viewBox.baseVal.width || 1;
    r.zoom = Math.min(1.7, Math.max(1, 0.8 / shown));
    r.right = svg.viewBox.baseVal.x + svg.viewBox.baseVal.width;
    r.left = svg.viewBox.baseVal.x;
  };
  fit();
  window.addEventListener("resize", fit);
  const state = { paused: false, facingLeft: false };
  container.addEventListener("click", () => (state.paused = !state.paused));
  container.title = "Click to pause / resume the rabbit";

  if (reduceMotion) {
    place(r, pointIn(layer, steps[0].path, 0), false, 0, false);
    setNote(r, steps[0].carry);
    return;
  }

  for (;;) {
    for (const step of steps) {
      setNote(r, step.carry);
      await walk(r, layer, step.path, state);
      await sleep(PAUSE);
    }
    await sleep(LOOP_PAUSE);
  }
}

function start() {
  const tourEl = document.querySelector("script.rabbit-tour");
  const container = document.querySelector(".diagram, .mermaid");
  if (!tourEl || !container) return;
  const tour = JSON.parse(tourEl.textContent);
  // Mermaid renders asynchronously: wait until the diagram's edges exist.
  const ready = () => container.querySelector("svg path[data-id]");
  const go = () => {
    if (!ready()) return false;
    observer.disconnect();
    requestAnimationFrame(() => run(container, tour)); // after layout, so lengths and CTMs are final
    return true;
  };
  const observer = new MutationObserver(go);
  if (!go()) observer.observe(container, { childList: true, subtree: true, attributes: true });
}

start();
