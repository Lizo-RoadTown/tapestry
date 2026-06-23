const __vite__mapDeps=(i,m=__vite__mapDeps,d=(m.f||(m.f=["_astro/mermaid.core.CDKtdRN3.js","_astro/preload-helper.BlTxHScW.js"])))=>i.map(i=>d[i]);
import{_ as A}from"./preload-helper.BlTxHScW.js";const S={},b=new Set,m=new WeakSet;let f=!0,v,p=!1;function T(e){p||(p=!0,f??=!1,v??="hover",M(),C(),O(),I())}function M(){for(const e of["touchstart","mousedown"])document.addEventListener(e,r=>{c(r.target,"tap")&&u(r.target.href,{ignoreSlowConnection:!0})},{passive:!0})}function C(){let e;document.body.addEventListener("focusin",t=>{c(t.target,"hover")&&r(t)},{passive:!0}),document.body.addEventListener("focusout",a,{passive:!0}),g(()=>{for(const t of document.getElementsByTagName("a"))m.has(t)||c(t,"hover")&&(m.add(t),t.addEventListener("mouseenter",r,{passive:!0}),t.addEventListener("mouseleave",a,{passive:!0}))});function r(t){const n=t.target.href;e&&clearTimeout(e),e=setTimeout(()=>{u(n)},80)}function a(){e&&(clearTimeout(e),e=0)}}function O(){let e;g(()=>{for(const r of document.getElementsByTagName("a"))m.has(r)||c(r,"viewport")&&(m.add(r),e??=P(),e.observe(r))})}function P(){const e=new WeakMap;return new IntersectionObserver((r,a)=>{for(const t of r){const n=t.target,o=e.get(n);t.isIntersecting?(o&&clearTimeout(o),e.set(n,setTimeout(()=>{a.unobserve(n),e.delete(n),u(n.href)},300))):o&&(clearTimeout(o),e.delete(n))}})}function I(){g(()=>{for(const e of document.getElementsByTagName("a"))c(e,"load")&&u(e.href)})}function u(e,r){e=e.replace(/#.*/,"");const a=r?.ignoreSlowConnection??!1;if(_(e,a))if(b.add(e),document.createElement("link").relList?.supports?.("prefetch")&&r?.with!=="fetch"){const t=document.createElement("link");t.rel="prefetch",t.setAttribute("href",e),document.head.append(t)}else{const t=new Headers;for(const[n,o]of Object.entries(S))t.set(n,o);fetch(e,{priority:"low",headers:t})}}function _(e,r){if(!navigator.onLine||!r&&y())return!1;try{const a=new URL(e,location.href);return location.origin===a.origin&&(location.pathname!==a.pathname||location.search!==a.search)&&!b.has(e)}catch{}return!1}function c(e,r){if(e?.tagName!=="A")return!1;const a=e.dataset.astroPrefetch;return a==="false"?!1:r==="tap"&&(a!=null||f)&&y()?!0:a==null&&f||a===""?r===v:a===r}function y(){if("connection"in navigator){const e=navigator.connection;return e.saveData||/2g/.test(e.effectiveType)}return!1}function g(e){e();let r=!1;document.addEventListener("astro:page-load",()=>{if(!r){r=!0;return}e()})}const i=(...e)=>console.log("[astro-mermaid]",...e),k=(...e)=>console.error("[astro-mermaid]",...e),w=()=>document.querySelectorAll("pre.mermaid").length>0;let d=null;async function x(){return d||(i("Loading mermaid.js..."),d=A(()=>import("./mermaid.core.CDKtdRN3.js").then(e=>e.bn),__vite__mapDeps([0,1])).then(async({default:e})=>{const r=[];if(r&&r.length>0){i("Registering",r.length,"icon packs");const a=r.map(t=>({name:t.name,loader:new Function("return "+t.loader)()}));await e.registerIconPacks(a)}return e}).catch(e=>{throw k("Failed to load mermaid:",e),d=null,e}),d)}const l={startOnLoad:!1,theme:"dark"},H={light:"default",dark:"dark"};async function h(){i("Initializing mermaid diagrams...");const e=document.querySelectorAll("pre.mermaid");if(i("Found",e.length,"mermaid diagrams"),e.length===0)return;const r=await x();let a=l.theme;{const t=document.documentElement.getAttribute("data-theme"),n=document.body.getAttribute("data-theme");a=H[t||n]||l.theme,i("Using theme:",a,"from",t?"html":"body")}r.initialize({...l,theme:a,gitGraph:{mainBranchName:"main",showCommitLabel:!0,showBranches:!0,rotateCommitLabel:!0}});for(const t of e){if(t.hasAttribute("data-processed"))continue;t.hasAttribute("data-diagram")||t.setAttribute("data-diagram",t.textContent||"");const n=t.getAttribute("data-diagram")||"",o="mermaid-"+Math.random().toString(36).slice(2,11);i("Rendering diagram:",o);try{const s=document.getElementById(o);s&&s.remove();const{svg:L}=await r.render(o,n);t.innerHTML=L,t.setAttribute("data-processed","true"),i("Successfully rendered diagram:",o)}catch(s){k("Mermaid rendering error for diagram:",o,s),t.innerHTML=`<div style="color: red; padding: 1rem; border: 1px solid red; border-radius: 0.5rem;">
        <strong>Error rendering diagram:</strong><br/>
        ${s.message||"Unknown error"}
      </div>`,t.setAttribute("data-processed","true")}}}w()?(i("Mermaid diagrams detected on initial load"),h()):i("No mermaid diagrams found on initial load");{const e=new MutationObserver(r=>{for(const a of r)a.type==="attributes"&&a.attributeName==="data-theme"&&(document.querySelectorAll("pre.mermaid[data-processed]").forEach(t=>{t.removeAttribute("data-processed")}),h())});e.observe(document.documentElement,{attributes:!0,attributeFilter:["data-theme"]}),e.observe(document.body,{attributes:!0,attributeFilter:["data-theme"]})}document.addEventListener("astro:after-swap",()=>{i("View transition detected"),w()&&h()});const E=document.createElement("style");E.textContent=`
            /* Prevent layout shifts by setting minimum height */
            pre.mermaid {
              display: flex;
              justify-content: center;
              align-items: center;
              margin: 2rem 0;
              padding: 1rem;
              background-color: transparent;
              border: none;
              overflow: auto;
              min-height: 200px; /* Prevent layout shift */
              position: relative;
            }
            
            /* Loading state with skeleton loader */
            pre.mermaid:not([data-processed]) {
              background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
              background-size: 200% 100%;
              animation: shimmer 1.5s infinite;
            }
            
            /* Dark mode skeleton loader */
            [data-theme="dark"] pre.mermaid:not([data-processed]) {
              background: linear-gradient(90deg, #2a2a2a 25%, #3a3a3a 50%, #2a2a2a 75%);
              background-size: 200% 100%;
            }
            
            @keyframes shimmer {
              0% {
                background-position: -200% 0;
              }
              100% {
                background-position: 200% 0;
              }
            }
            
            /* Show processed diagrams with smooth transition */
            pre.mermaid[data-processed] {
              animation: none;
              background: transparent;
              min-height: auto; /* Allow natural height after render */
            }
            
            /* Ensure responsive sizing for mermaid SVGs */
            pre.mermaid svg {
              max-width: 100%;
              height: auto;
            }
            
            /* Optional: Add subtle background for better visibility */
            @media (prefers-color-scheme: dark) {
              pre.mermaid[data-processed] {
                background-color: rgba(255, 255, 255, 0.02);
                border-radius: 0.5rem;
              }
            }
            
            @media (prefers-color-scheme: light) {
              pre.mermaid[data-processed] {
                background-color: rgba(0, 0, 0, 0.02);
                border-radius: 0.5rem;
              }
            }
            
            /* Respect user's color scheme preference */
            [data-theme="dark"] pre.mermaid[data-processed] {
              background-color: rgba(255, 255, 255, 0.02);
              border-radius: 0.5rem;
            }
            
            [data-theme="light"] pre.mermaid[data-processed] {
              background-color: rgba(0, 0, 0, 0.02);
              border-radius: 0.5rem;
            }
          `;document.head.appendChild(E);T();
