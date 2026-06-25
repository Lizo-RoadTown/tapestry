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
  // Front-door move: the front page now lives at / (src/pages/index.astro);
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
      // Brand fonts, matching the site front page (/):
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
      //
      // The outcome/positioning pages from the prior transitional Background
      // group have moved into Learn now that their front-page versions are live
      // on the site. Each carries a top-of-page banner pointing readers to its
      // front-page version, so the docs page reads as concept-only while the
      // front page carries the outcome / positioning framing.
      sidebar: [
        {
          label: "Learn",
          // What people actually need to understand Tapestry: what it is, how
          // it works, and the surface they watch it through. The deeper
          // implementation detail lives in Components + Reference for the
          // developers who need it; the former "Going deeper" theory pages were
          // archived to docs/archive/website-learn-pages/ on 2026-06-25.
          items: [
            { label: "What Tapestry is", slug: "start/what-stays-on-track" },
            { label: "The observer", slug: "explanation/the-observer" },
            { label: "The Observatory", slug: "observatory/about" },
            { label: "What Tapestry is not", slug: "start/what-tapestry-is-not" },
          ],
        },
        {
          label: "Docs",
          items: [
            { label: "Overview", slug: "docs" },
            { label: "Quickstart — VS Code", slug: "how-to/quickstart-vscode" },
            { label: "Connect VS Code (without Claude Code)", slug: "how-to/connect-vscode-mcp" },
            { label: "Your first project", slug: "start/your-first-project" },
            { label: "Verify it worked", slug: "start/verify-it-worked" },
            { label: "First Observatory visit", slug: "start/first-observatory-visit" },
            { label: "Set up a new project (comprehensive)", slug: "how-to/set-up-a-new-project" },
            { label: "Create your own plugin", slug: "how-to/create-your-own-plugin" },
            { label: "Recover from common failures", slug: "how-to/recover-from-common-failures" },
            // The Observatory's actionable pages. What it is + how to read it
            // lives in Learn ("The Observatory"); the feed contract is in Reference.
            { label: "Run the Observatory", slug: "observatory/run-it" },
            // The live console is a custom Astro page (src/pages/observatory.astro),
            // not a Starlight content doc, so it's a manual link.
            { label: "Open the console", link: "/observatory" },
          ],
        },
        {
          // What you stand up before (or alongside) using Tapestry — in
          // self-host, every operator runs their own backend + tooling.
          label: "Prerequisites",
          items: [
            { label: "Set up Claude Code", slug: "how-to/set-up-claude-code" },
            { label: "Set up GitHub", slug: "how-to/set-up-github" },
            { label: "Set up Render", slug: "how-to/set-up-render" },
            { label: "Set up Vercel", slug: "how-to/set-up-vercel" },
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
            { label: "Docs MCP", slug: "systems/docs-mcp" },
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
            { label: "The Observatory feed", slug: "observatory/feed" },
            { label: "Platform dependencies", slug: "reference/platform-dependencies" },
            { label: "Load-bearing files", slug: "reference/load-bearing-files" },
          ],
        },
      ],
    }),
  ],
});
