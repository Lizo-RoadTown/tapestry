import { c as createComponent, h as renderHead, e as addAttribute, f as renderScript, a as renderTemplate } from '../chunks/astro/server_DpMYLMcY.mjs';
import 'piccolore';
import 'clsx';
/* empty css                                       */
export { renderers } from '../renderers.mjs';

const prerender = false;
const $$Observatory = createComponent(async ($$result, $$props, $$slots) => {
  const CANON = "https://github.com/Lizo-RoadTown/tapestry/blob/main/docs/canon/user-agent-coordination-reinforcement.md";
  return renderTemplate`<html lang="en"> <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>The Observatory — Tapestry</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">${renderHead()}</head> <body> <header class="topbar"> <a class="wordmark" href="/">Tapestry</a> <nav class="topnav"><a href="/">Home</a><a href="/docs/">Docs</a><a class="here" href="/observatory">Observatory</a><a href="/observatory/raw">Raw events</a></nav> </header> <main> <section class="hero"> <p class="eyebrow mono" id="src">pattern cockpit · loading…</p> <h1 class="display">The <span class="ac">Observatory</span></h1> <p class="lede">Choose variables, overlay them, and let the observer explain what patterns the view can expose.</p> </section> <section class="controls"> <label>Show <select id="y"></select></label> <label>over <span class="mono">time</span></label> <label>overlaid with <select id="overlay"></select></label> <label>as <select id="ctype"><option value="line">trend (line)</option><option value="scatter">relationship (scatter)</option></select></label> <span class="rec mono" id="rec"></span> </section> <section class="chartwrap"><div id="chart" class="chart"><p class="loading mono">loading…</p></div><div id="legend" class="legend"></div></section> <section class="interp" id="interp"></section> <footer class="foot"><p class="mono">Raw counters + events: <a href="/observatory/raw">Raw events (debug)</a>. Canon: <a${addAttribute(CANON, "href")}>user-agent-coordination-reinforcement</a>.</p></footer> </main> ${renderScript($$result, "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory.astro?astro&type=script&index=0&lang.ts")}  </body> </html>`;
}, "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory.astro", void 0);

const $$file = "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory.astro";
const $$url = "/observatory";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Observatory,
  file: $$file,
  prerender,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
