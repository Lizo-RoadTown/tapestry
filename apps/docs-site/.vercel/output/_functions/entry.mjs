import { renderers } from './renderers.mjs';
import { c as createExports, s as serverEntrypointModule } from './chunks/_@astrojs-ssr-adapter_CQujLP0r.mjs';
import { manifest } from './manifest_Du-mhiFi.mjs';

const serverIslandMap = new Map();;

const _page0 = () => import('./pages/_image.astro.mjs');
const _page1 = () => import('./pages/404.astro.mjs');
const _page2 = () => import('./pages/api/episodes.json.astro.mjs');
const _page3 = () => import('./pages/enterprise.astro.mjs');
const _page4 = () => import('./pages/how-it-works.astro.mjs');
const _page5 = () => import('./pages/observatory/raw.astro.mjs');
const _page6 = () => import('./pages/observatory.astro.mjs');
const _page7 = () => import('./pages/open-source.astro.mjs');
const _page8 = () => import('./pages/project-intelligence.astro.mjs');
const _page9 = () => import('./pages/project-shape.astro.mjs');
const _page10 = () => import('./pages/use-cases.astro.mjs');
const _page11 = () => import('./pages/index.astro.mjs');
const _page12 = () => import('./pages/_---slug_.astro.mjs');
const pageMap = new Map([
    ["node_modules/astro/dist/assets/endpoint/generic.js", _page0],
    ["node_modules/@astrojs/starlight/routes/static/404.astro", _page1],
    ["src/pages/api/episodes.json.ts", _page2],
    ["src/pages/enterprise.astro", _page3],
    ["src/pages/how-it-works.astro", _page4],
    ["src/pages/observatory/raw.astro", _page5],
    ["src/pages/observatory.astro", _page6],
    ["src/pages/open-source.astro", _page7],
    ["src/pages/project-intelligence.astro", _page8],
    ["src/pages/project-shape.astro", _page9],
    ["src/pages/use-cases.astro", _page10],
    ["src/pages/index.astro", _page11],
    ["node_modules/@astrojs/starlight/routes/static/index.astro", _page12]
]);

const _manifest = Object.assign(manifest, {
    pageMap,
    serverIslandMap,
    renderers,
    actions: () => import('./noop-entrypoint.mjs'),
    middleware: () => import('./_astro-internal_middleware.mjs')
});
const _args = {
    "middlewareSecret": "c3b94458-30e8-42fd-8dfe-261286360789",
    "skewProtection": false
};
const _exports = createExports(_manifest, _args);
const __astrojsSsrVirtualEntry = _exports.default;
const _start = 'start';
if (Object.prototype.hasOwnProperty.call(serverEntrypointModule, _start)) ;

export { __astrojsSsrVirtualEntry as default, pageMap };
