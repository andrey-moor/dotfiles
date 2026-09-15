// Page styles and behavior for the study page. Static-first: without JavaScript every
// section, step, and figure is visible; answers hide behind native <details>.
export const CSS = `
:root {
  --bg: #ffffff; --ink: #0e2841; --muted: #44546a; --soft: #7f8a9c; --rule: rgba(14,40,65,.14);
  --accent: #e97132; --accent-tint: rgba(233,113,50,.10); --link: #156082; --card: #f6f7f9; --code: #f2f2f2;
  --sans: system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; --mono: ui-monospace, "Cascadia Mono", Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #14181f; --ink: #e8ebf0; --muted: #b3bcc9; --soft: #8a95a6; --rule: rgba(232,235,240,.14);
    --accent: #f08a59; --accent-tint: rgba(240,138,89,.14); --link: #7fb3d6; --card: #1c222b; --code: #1f2630; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.55 var(--sans); }
a { color: var(--link); }
code { font: .9em var(--mono); background: var(--code); padding: .1em .3em; border-radius: 3px; }
pre { background: var(--code); padding: 12px 16px; overflow-x: auto; border-radius: 6px; }
pre code { background: none; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: .95em; }
th, td { border: 1px solid var(--rule); padding: 6px 10px; text-align: left; vertical-align: top; }
th { background: var(--card); }
.wrap { max-width: 860px; margin: 0 auto; padding: 32px 20px 96px; }
header.top { margin-bottom: 24px; }
.eyebrow { font: 500 12px/1.4 var(--mono); letter-spacing: .16em; text-transform: uppercase; color: var(--muted); margin: 0 0 8px; }
h1 { font-size: 2.1rem; line-height: 1.15; margin: 0 0 8px; letter-spacing: -.01em; }
.meta { color: var(--muted); margin: 0; }
h2 { font-size: 1.45rem; margin: 40px 0 12px; padding-top: 16px; border-top: 1px solid var(--rule); }
h3 { font-size: 1.1rem; margin: 20px 0 6px; }
p, li { max-width: 72ch; }
.depth-switch { position: sticky; top: 0; z-index: 5; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  background: var(--bg); padding: 10px 0; border-bottom: 1px solid var(--rule); }
.depth-switch[hidden] { display: none; }
.depth-switch span { color: var(--muted); font-size: .9em; margin-right: 6px; }
.depth-switch button, .stepper-controls button, .grade button {
  font: inherit; font-size: .9em; padding: 6px 12px; border: 1px solid var(--rule); border-radius: 6px;
  background: var(--card); color: var(--ink); cursor: pointer; min-height: 36px; }
.depth-switch button[aria-pressed="true"] { border-color: var(--accent); background: var(--accent-tint); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
html[data-depth="gist"] .depth-mechanism, html[data-depth="gist"] .depth-details { display: none; }
html[data-depth="mechanism"] .depth-details { display: none; }
.remember { border-left: 3px solid var(--accent); padding: 8px 14px; background: var(--accent-tint); border-radius: 0 6px 6px 0; }
.figure { margin: 20px 0; }
.figure img { max-width: 100%; height: auto; display: block; }
.figure figcaption { color: var(--muted); font-size: .9em; margin-top: 8px; }
.svg-scroll { overflow-x: auto; }
.figure-title { font-weight: 600; margin: 0 0 8px; }
.stepper-controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin: 8px 0 12px; }
.stepper-controls[hidden] { display: none; }
.stepper-status { color: var(--muted); font-size: .9em; }
.steps { list-style: none; padding: 0; margin: 0; counter-reset: step; }
.step { border: 1px solid var(--rule); border-radius: 8px; padding: 12px 16px; margin: 0 0 10px; background: var(--card); }
.step h3 { margin: 0 0 6px; display: flex; gap: 10px; align-items: baseline; }
.step-number { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%;
  background: var(--accent); color: #fff; font-size: .85em; font-weight: 600; }
.stepper[data-mode="one"] .step:not(.is-current) { display: none; }
.part { margin: 16px 0 24px; }
.part-facts { display: grid; grid-template-columns: max-content 1fr; gap: 6px 16px; margin: 8px 0 12px; }
.part-facts dt { font-weight: 600; color: var(--muted); }
.part-facts dd { margin: 0; max-width: 64ch; }
.part-facts dt.fact-remember { color: var(--accent); }
@media (max-width: 600px) { .part-facts { grid-template-columns: 1fr; gap: 2px; } .part-facts dd { margin-bottom: 8px; } }
.part-details summary, .card summary { cursor: pointer; font-weight: 600; }
.part-details { margin: 8px 0; padding: 6px 12px; border-left: 2px solid var(--rule); }
.card { border: 1px solid var(--rule); border-radius: 8px; padding: 12px 16px; margin: 0 0 10px; background: var(--card); }
.card[data-state="got"] { border-color: #4ea72e; }
.card[data-state="missed"] { border-color: var(--accent); }
.card .answer { margin-top: 8px; }
.grade { display: flex; gap: 8px; margin-top: 10px; }
.grade[hidden] { display: none; }
.progress { color: var(--muted); }
.review-toggle { display: inline-block; margin: 0 0 12px; color: var(--muted); }
.review-toggle[hidden] { display: none; }
.cards[data-review="missed"] .card:not([data-state="missed"]) { display: none; }
.glossary dt { font-weight: 600; margin-top: 10px; }
.glossary dd { margin: 2px 0 0; color: var(--muted); }
.term { border-bottom: 1px dotted var(--soft); cursor: help; position: relative; }
.term:hover::after, .term:focus::after { content: attr(data-def); position: absolute; left: 0; top: 1.5em; z-index: 10;
  width: min(360px, 80vw); background: var(--ink); color: var(--bg); padding: 8px 10px; border-radius: 6px;
  font-size: .85em; line-height: 1.4; font-weight: 400; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 600px) { body { font-size: 16px; } h1 { font-size: 1.7rem; } }
`;

export const JS = `
(() => {
  const store = (key, value) => { try { if (value === undefined) return JSON.parse(localStorage.getItem(key)); localStorage.setItem(key, JSON.stringify(value)); } catch { return undefined; } };
  const title = document.documentElement.dataset.study || location.pathname;
  const key = (name) => 'study:' + title + ':' + name;

  // Depth switch: gist -> mechanism -> details. Remembered per page.
  const depthSwitch = document.querySelector('[data-depth-switch]');
  if (depthSwitch) {
    const setDepth = (depth) => {
      document.documentElement.dataset.depth = depth;
      depthSwitch.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.depth === depth)));
      store(key('depth'), depth);
    };
    depthSwitch.addEventListener('click', (e) => { const b = e.target.closest('button[data-depth]'); if (b) setDepth(b.dataset.depth); });
    depthSwitch.hidden = false;
    setDepth(store(key('depth')) || 'gist');
  }

  // Stepper: one step at a time, kept in step with the first step-mode figure both ways.
  document.querySelectorAll('[data-stepper]').forEach((stepper) => {
    const steps = [...stepper.querySelectorAll('.step')];
    const controls = stepper.querySelector('[data-stepper-controls]');
    const status = stepper.querySelector('[data-stepper-status]');
    const prev = controls.querySelector('[data-stepper-action="prev"]');
    const next = controls.querySelector('[data-stepper-action="next"]');
    const toggle = controls.querySelector('[data-stepper-action="all"]');
    const label = stepper.dataset.label || 'Step';
    const figure = document.querySelector('.figure-stepped [data-motion-root]');
    let current = 1;
    const isOne = () => stepper.dataset.mode === 'one';
    const reduced = () => Boolean(figure) && figure.dataset.motionState === 'reduced';
    const figureStep = () => Math.min(steps.length, Number(figure.dataset.stepCurrent) || 0);
    const driveFigure = () => {
      if (!figure) return;
      const target = Math.min(current, Number(figure.dataset.stepCount) || current);
      for (let guard = 0; guard < 16 && Number(figure.dataset.stepCurrent) !== target; guard += 1) {
        const dir = Number(figure.dataset.stepCurrent) < target ? 'next' : 'prev';
        const button = figure.querySelector('[data-motion-action="' + dir + '"]');
        if (!button || button.disabled) break;
        button.click();
      }
    };
    const renderText = () => {
      steps.forEach((s, i) => s.classList.toggle('is-current', i + 1 === current));
      status.textContent = isOne() ? label + ' ' + current + ' of ' + steps.length : 'All shown';
      prev.disabled = !isOne() || current === 1;
      next.disabled = !isOne() || current === steps.length;
    };
    controls.addEventListener('click', (e) => {
      const b = e.target.closest('button[data-stepper-action]'); if (!b) return;
      if (b === prev && isOne()) current = Math.max(1, current - 1);
      if (b === next && isOne()) current = Math.min(steps.length, current + 1);
      if (b === toggle) {
        stepper.dataset.mode = isOne() ? 'all' : 'one';
        toggle.textContent = isOne() ? 'Show all' : 'One at a time';
        // Coming back to one at a time, continue from wherever the figure was moved meanwhile.
        if (isOne() && figure && !reduced() && figureStep() > 0) current = figureStep();
      }
      renderText();
      if (isOne()) driveFigure();
    });
    if (figure) {
      let wasReduced = reduced();
      new MutationObserver(() => {
        const nowReduced = reduced();
        const leftReduced = wasReduced && !nowReduced;
        wasReduced = nowReduced;
        // Under reduced motion the figure shows every step at once, and the text keeps its own place.
        if (!isOne() || nowReduced) return;
        if (leftReduced) { driveFigure(); return; }
        const step = figureStep();
        // Step 0 is an empty frame. Unless the figure is about to play from there, start again at step 1.
        if (step === 0) {
          if (figure.classList.contains('is-playing')) return;
          current = 1; renderText(); driveFigure(); return;
        }
        if (step === current) return;
        current = step;
        renderText();
      }).observe(figure, { attributes: true, attributeFilter: ['data-step-current', 'data-motion-state', 'class'] });
    }
    stepper.dataset.mode = 'one';
    controls.hidden = false;
    renderText();
    driveFigure();
  });

  // Check-yourself cards: grade, remember, review missed only.
  const cards = [...document.querySelectorAll('.card')];
  if (cards.length) {
    const saved = store(key('cards')) || {};
    const progress = document.querySelector('[data-progress]');
    const toggle = document.querySelector('[data-review-toggle]');
    const wrap = document.querySelector('.cards');
    const update = () => {
      const got = cards.filter((c) => c.dataset.state === 'got').length;
      const missed = cards.filter((c) => c.dataset.state === 'missed').length;
      progress.textContent = got + ' of ' + cards.length + ' got it' + (missed ? ', ' + missed + ' to review' : '') + '.';
      store(key('cards'), Object.fromEntries(cards.map((c) => [c.dataset.card, c.dataset.state || ''])));
    };
    cards.forEach((card) => {
      if (saved[card.dataset.card]) card.dataset.state = saved[card.dataset.card];
      const grade = card.querySelector('[data-grade-controls]');
      grade.hidden = false;
      grade.addEventListener('click', (e) => { const b = e.target.closest('button[data-grade]'); if (!b) return; card.dataset.state = b.dataset.grade; update(); });
    });
    progress.hidden = false; toggle.hidden = false;
    toggle.querySelector('input').addEventListener('change', (e) => { wrap.dataset.review = e.target.checked ? 'missed' : ''; });
    update();
  }

  // Term tooltips: first occurrence of each glossary term per section gets its definition.
  const terms = JSON.parse(document.getElementById('glossary-data')?.textContent || '[]');
  if (terms.length) {
    const skip = (el) => el.closest('.glossary, code, pre, a, .term, h1, h2, h3, summary, dt, button, .diagram-embed, figcaption, [data-stepper-controls], [data-grade-controls], [data-progress], .review-toggle, .depth-switch, .step-number');
    document.querySelectorAll('section[data-section]:not([data-section="glossary"])').forEach((section) => {
      terms.forEach(({ term, definition }) => {
        const re = new RegExp('(?<!\\\\w)(' + term.replace(/[.*+?^\${}()|[\\]\\\\]/g, '\\\\$&') + ')(?:s|es)?(?!\\\\w)', 'i');
        const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
        let node;
        while ((node = walker.nextNode())) {
          if (skip(node.parentElement)) continue;
          const m = node.nodeValue.match(re);
          if (!m) continue;
          const span = document.createElement('span');
          span.className = 'term'; span.tabIndex = 0; span.dataset.def = definition; span.textContent = m[0];
          const after = node.splitText(m.index); after.nodeValue = after.nodeValue.slice(m[0].length);
          node.parentNode.insertBefore(span, after);
          break;
        }
      });
    });
  }
})();
`;
