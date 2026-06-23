// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mermaid from "astro-mermaid";
import vercel from "@astrojs/vercel";

// Tapestry documentation (Astro Starlight). Public site for an operator setting up a
// project that plugs into the Tapestry platform. Explains the discipline stack (plugins,
// MCP, hooks, project-intelligence) so that nothing breaks silently when a load-bearing
// piece goes missing.
export default defineConfig({
  site: "https://tapestry-khaki.vercel.app",
  // Adapter enables on-demand routes (the Observatory console + /api/episodes.json)
  // while all doc pages stay static (prerendered by default).
  adapter: vercel(),
  // Front-door move: the marketing page now lives at / (src/pages/index.astro);
  // the docs landing moved to /docs/ (src/content/docs/docs.mdx). /home is kept
  // as a redirect to / so older links and bookmarks still resolve.
  redirects: {
    "/home": "/",
  },
  integrations: [
    // astro-mermaid must precede starlight so ```mermaid blocks render as diagrams.
    mermaid({ theme: "dark" }),
    starlight({
      title: "Tapestry",
      description:
        "What keeps a project on track when it plugs into the Tapestry platform: the discipline stack of plugins, MCP wiring, hooks, and project intelligence — and how to recover when one piece goes missing.",
      customCss: ["./src/styles/custom.css"],
      // Component overrides — Tapestry-specific.
      components: {
        // Adds a "Copy page" dropdown to the right of every page's <h1>.
        // Items: Copy page as Markdown / View as Markdown / llms.txt.
        // Backed by /llms.txt + /raw/<slug>.md, both produced by
        // scripts/generate-static-docs.mjs as a prebuild step.
        PageTitle: "./src/components/PageActions.astro",
      },
      // Brand fonts, matching the marketing front page (/home):
      // Instrument Serif (display) / Inter (body) / JetBrains Mono (code).
      head: [
        { tag: "link", attrs: { rel: "preconnect", href: "https://fonts.googleapis.com" } },
        { tag: "link", attrs: { rel: "preconnect", href: "https://fonts.gstatic.com", crossorigin: true } },
        {
          tag: "link",
          attrs: {
            rel: "stylesheet",
            href: "https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap",
          },
        },
      ],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/Lizo-RoadTown/tapestry",
        },
      ],
      // Sidebar grouped by reader intent per Tapestry-agent's IA decision
      // (tapestry-docs-ia-split-by-reader-intent-2026-06-23 in shared loom-memory).
      //   Learn:        helps the reader understand the model
      //   Docs:         helps the reader perform an action
      //   Components:   how the platform is built
      //   Reference:    what each contract / file does exactly
      //   Background:   transitional — pages reclassified as marketing.
      //                 Stay sidebar-visible until Tapestry-agent memos
      //                 that each one's marketing version has shipped on
      //                 the marketing website (apps/docs-site/src/pages/),
      //                 at which point they're either slimmed to
      //                 concept-only or removed.
      sidebar: [
        {
          label: "Learn",
          items: [
            { label: "User-agent interface", slug: "start/user-agent-interface" },
            { label: "The signal hierarchy", slug: "explanation/signal-hierarchy" },
            { label: "Signal → Interpretation → Pattern", slug: "explanation/signal-interpretation-pattern" },
            { label: "The observer", slug: "explanation/the-observer" },
            { label: "Observer-derived intent", slug: "explanation/observer-derived-intent" },
            { label: "Observatory lenses", slug: "explanation/observatory-lenses" },
            { label: "Names you'll see in these docs", slug: "start/names-you-will-see" },
          ],
        },
        {
          label: "Docs",
          items: [
            { label: "Overview", slug: "docs" },
            { label: "Quickstart — VS Code", slug: "how-to/quickstart-vscode" },
            { label: "Your first project", slug: "start/your-first-project" },
            { label: "Verify it worked", slug: "start/verify-it-worked" },
            { label: "First Observatory visit", slug: "start/first-observatory-visit" },
            { label: "Set up a new project (comprehensive)", slug: "how-to/set-up-a-new-project" },
            { label: "Recover from common failures", slug: "how-to/recover-from-common-failures" },
            // The Observatory's own usage pages — operational, not architectural.
            { label: "About the Observatory", slug: "observatory/about" },
            { label: "Reading the Observatory", slug: "observatory/reading-it" },
            { label: "Run the Observatory", slug: "observatory/run-it" },
            { label: "The Observatory feed", slug: "observatory/feed" },
            // The live console is a custom Astro page (src/pages/observatory.astro),
            // not a Starlight content doc, so it's a manual link.
            { label: "Open the console", link: "/observatory" },
            // Platform-owner provisioning walkthroughs — not needed by consuming projects.
            { label: "Set up Render (platform owner)", slug: "how-to/set-up-render" },
            { label: "Set up Vercel (platform owner)", slug: "how-to/set-up-vercel" },
            { label: "Set up Grafana Cloud + OTel", slug: "how-to/set-up-grafana-cloud" },
          ],
        },
        {
          label: "Components",
          items: [
            { label: "Observer", slug: "systems/observer" },
            { label: "Memory", slug: "systems/memory" },
            { label: "Telemetry", slug: "systems/telemetry" },
            { label: "Registry", slug: "systems/registry" },
            { label: "Observatory", slug: "systems/observatory" },
            { label: "Docs MCP (planned)", slug: "systems/docs-mcp" },
            { label: "The plugins", slug: "explanation/plugins" },
            { label: "The memory MCP", slug: "explanation/memory-mcp" },
            { label: "The discipline stack (orientation)", slug: "explanation/discipline-stack" },
            { label: "Architecture snapshots", slug: "explanation/architecture-snapshots" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "OTel coordination contract", slug: "reference/otel-coordination-contract" },
            { label: "Platform dependencies", slug: "reference/platform-dependencies" },
            { label: "Load-bearing files", slug: "reference/load-bearing-files" },
          ],
        },
        {
          // Transitional. Pages reclassified as marketing in Tapestry-agent's
          // IA memo; staying sidebar-visible until each one's marketing version
          // ships on the marketing website. Tapestry-agent will memo as each
          // page's marketing version lands; then these get slimmed to
          // concept-only or removed.
          label: "Background (migrating to marketing site)",
          items: [
            { label: "Project shape", slug: "start/project-shape" },
            { label: "What Tapestry is not", slug: "start/what-tapestry-is-not" },
            { label: "What keeps a project on track", slug: "start/what-stays-on-track" },
            { label: "Project Intelligence vs Observatory", slug: "explanation/project-intelligence-vs-observatory" },
            { label: "How the platform upskills itself", slug: "explanation/upskilling" },
            { label: "Sharing intelligence across projects", slug: "explanation/sharing-intelligence-across-projects" },
          ],
        },
      ],
    }),
  ],
});
