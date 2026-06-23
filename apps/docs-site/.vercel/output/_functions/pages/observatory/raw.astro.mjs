import { c as createComponent, h as renderHead, f as renderScript, a as renderTemplate } from '../../chunks/astro/server_DpMYLMcY.mjs';
import 'piccolore';
import 'clsx';
/* empty css                                  */
export { renderers } from '../../renderers.mjs';

const prerender = false;
const $$Raw = createComponent(async ($$result, $$props, $$slots) => {
  return renderTemplate`<html lang="en"> <head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Raw events (debug) — Tapestry Observatory</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">${renderHead()}</head> <body> <header class="topbar"> <a class="wordmark" href="/">Tapestry</a> <nav class="topnav"><a href="/">Home</a><a href="/docs/">Docs</a><a href="/observatory">Observatory</a><a class="here" href="/observatory/raw">Raw events</a></nav> </header> <main> <section class="hero"> <p class="eyebrow mono" id="src">debug · raw telemetry</p> <h1 class="display">Raw events <span class="ac">(debug)</span></h1> <p class="lede">The unrolled hook telemetry — for debugging the feed. The meaningful view is the <a href="/observatory">Observatory</a>.</p> </section> <section class="summary" id="summary"></section> <section><div id="episodes" class="eplist"><p class="loading mono">loading…</p></div></section> </main> ${renderScript($$result, "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory/raw.astro?astro&type=script&index=0&lang.ts")}  </body> </html>`;
}, "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory/raw.astro", void 0);

const $$file = "C:/Users/Liz/tapestry-fd/apps/docs-site/src/pages/observatory/raw.astro";
const $$url = "/observatory/raw";

const _page = /*#__PURE__*/Object.freeze(/*#__PURE__*/Object.defineProperty({
  __proto__: null,
  default: $$Raw,
  file: $$file,
  prerender,
  url: $$url
}, Symbol.toStringTag, { value: 'Module' }));

const page = () => _page;

export { page };
