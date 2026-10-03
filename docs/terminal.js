// Replays a recorded petite session in the landing page's terminal: types the
// command, then reveals each recorded line with roughly its real pacing.
// The transcript itself is plain HTML in the page, so it reads fine without JS.

const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function play(term) {
  const cmd = term.querySelector(".t-cmd");
  const lines = [...term.querySelectorAll(".t-line")];
  const full = cmd.textContent;
  for (;;) {
    cmd.textContent = "";
    lines.forEach((l) => (l.hidden = true));
    term.classList.add("typing");
    await sleep(600);
    for (const ch of full) {
      cmd.textContent += ch;
      await sleep(28 + Math.random() * 40);
    }
    term.classList.remove("typing");
    await sleep(400);
    for (const line of lines) {
      await sleep(Number(line.dataset.wait ?? 120));
      line.hidden = false;
      term.scrollTop = term.scrollHeight;
    }
    await sleep(9000);
  }
}

for (const term of document.querySelectorAll(".terminal")) {
  if (!reduceMotion) play(term);
}
