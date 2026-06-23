// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mermaid from "astro-mermaid";

// Tapestry documentation (Astro Starlight). Public site for an operator setting up a
// project that plugs into the Tapestry platform. Explains the discipline stack (plugins,
// MCP, hooks, project-intelligence) so that nothing breaks silently when a load-bearing
// piece goes missing.
export default defineConfig({
  site: "https://tapestry-docs.vercel.app",
  integrations: [
    // astro-mermaid must precede starlight so ```mermaid blocks render as diagrams.
    mermaid({ theme: "dark" }),
    starlight({
      title: "Tapestry",
      description:
        "What keeps a project on track when it plugs into the Tapestry platform: the discipline stack of plugins, MCP wiring, hooks, and project intelligence — and how to recover when one piece goes missing.",
      customCss: ["./src/styles/custom.css"],
      social: [
        {
          icon: "github",
          label: "GitHub",
          href: "https://github.com/Lizo-RoadTown/tapestry",
        },
      ],
      // Explicit sidebar. The full v1 scope is visible.
      // Ordering reflects the recommended reading sequence: primary object
      // (user-agent interface) before substrate (project shape) before
      // anti-frame (what Tapestry is not) before the loop's mechanics
      // (signal hierarchy + the observer) before specifics (plugins, memory,
      // discipline stack, architecture snapshots).
      sidebar: [
        {
          label: "Start here",
          items: [
            { label: "Overview", slug: "index" },
            { label: "User-agent interface", slug: "start/user-agent-interface" },
            { label: "Project shape", slug: "start/project-shape" },
            { label: "What Tapestry is not", slug: "start/what-tapestry-is-not" },
            { label: "Names you'll see in these docs", slug: "start/names-you-will-see" },
            { label: "What keeps a project on track", slug: "start/what-stays-on-track" },
          ],
        },
        {
          label: "How it works",
          items: [
            { label: "The signal hierarchy", slug: "explanation/signal-hierarchy" },
            { label: "The observer", slug: "explanation/the-observer" },
            { label: "Observer-derived intent", slug: "explanation/observer-derived-intent" },
            { label: "How the platform upskills itself", slug: "explanation/upskilling" },
            { label: "Sharing intelligence across projects", slug: "explanation/sharing-intelligence-across-projects" },
            { label: "The memory MCP", slug: "explanation/memory-mcp" },
            { label: "The plugins", slug: "explanation/plugins" },
            { label: "The discipline stack (orientation)", slug: "explanation/discipline-stack" },
            { label: "Architecture snapshots", slug: "explanation/architecture-snapshots" },
          ],
        },
        {
          label: "Use it",
          items: [
            { label: "Quickstart — VS Code", slug: "how-to/quickstart-vscode" },
            { label: "Set up a new project (comprehensive)", slug: "how-to/set-up-a-new-project" },
            { label: "Recover from common failures", slug: "how-to/recover-from-common-failures" },
          ],
        },
        {
          label: "Reference",
          items: [
            { label: "Load-bearing files", slug: "reference/load-bearing-files" },
            { label: "OTel coordination contract", slug: "reference/otel-coordination-contract" },
            // Observatory console lives at src/pages/observatory.astro (custom Astro page,
            // not a Starlight content doc), so it's wired as a manual link, not a slug.
            { label: "Observatory console", link: "/observatory" },
          ],
        },
      ],
    }),
  ],
});
