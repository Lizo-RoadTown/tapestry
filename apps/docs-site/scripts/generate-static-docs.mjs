#!/usr/bin/env node
/**
 * generate-static-docs.mjs
 *
 * Walks src/content/docs/ and emits two artifacts to public/:
 *   - public/llms.txt — flattened corpus per the llmstxt.org convention
 *   - public/raw/<slug>.md — raw markdown body for each docs page
 *
 * Run as a pre-build step (see package.json `prebuild`). The output is
 * picked up by Astro's static asset pipeline and served at the site root
 * (so /llms.txt and /raw/<slug>.md resolve once the site is deployed).
 *
 * Frontmatter parsing is intentionally minimal — regex over the first
 * `---`-fenced block. Matches docs_mcp/corpus.py so both produce
 * identical output. No extra dependencies.
 */
import { promises as fs } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DOCS_ROOT = path.resolve(__dirname, "..", "src", "content", "docs");
const PUBLIC_ROOT = path.resolve(__dirname, "..", "public");
const SITE_BASE_URL = process.env.SITE_BASE_URL || "https://tapestry-khaki.vercel.app";

// Tolerate both LF and CRLF — Windows working trees get CRLF after Git checkout.
const FRONTMATTER_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/;
const TITLE_RE = /^title:\s*(.+?)\r?$/m;
const DESC_RE = /^description:\s*(.+?)\r?$/m;

const SECTION_ORDER = ["", "start", "how-to", "explanation", "systems", "observatory", "reference"];

function stripQuotes(s) {
  return s.replace(/^["']|["']$/g, "").trim();
}

function parseFrontmatter(text) {
  const m = text.match(FRONTMATTER_RE);
  if (!m) return { title: "", description: "", body: text };
  const fm = m[1];
  const body = text.slice(m[0].length);
  const t = fm.match(TITLE_RE);
  const d = fm.match(DESC_RE);
  return {
    title: t ? stripQuotes(t[1].trim()) : "",
    description: d ? stripQuotes(d[1].trim()) : "",
    body,
  };
}

async function walk(dir) {
  const out = [];
  for (const entry of await fs.readdir(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await walk(p)));
    } else if (entry.isFile() && (entry.name.endsWith(".md") || entry.name.endsWith(".mdx"))) {
      out.push(p);
    }
  }
  return out;
}

function fileToSlug(absPath) {
  const rel = path.relative(DOCS_ROOT, absPath);
  const noExt = rel.replace(/\.(md|mdx)$/, "");
  return noExt.split(path.sep).join("/");
}

async function loadCorpus() {
  const files = (await walk(DOCS_ROOT)).sort();
  const docs = [];
  for (const file of files) {
    const text = await fs.readFile(file, "utf-8");
    const { title, description, body } = parseFrontmatter(text);
    const slug = fileToSlug(file);
    const section = slug.includes("/") ? slug.split("/")[0] : "";
    docs.push({
      slug,
      title: title || slug,
      description,
      body,
      section,
      filePath: file,
    });
  }
  return docs;
}

function buildLlmsTxt(docs) {
  const base = SITE_BASE_URL.replace(/\/$/, "");
  const lines = [];
  lines.push("# Tapestry");
  lines.push("");
  lines.push(
    "Tapestry is a user/agent support and reinforcement system. " +
      "These docs describe how the platform observes coordination between " +
      "operators and agents and how durable structure is produced from that observation.",
  );
  lines.push("");

  const bySection = new Map();
  for (const d of docs) {
    if (!bySection.has(d.section)) bySection.set(d.section, []);
    bySection.get(d.section).push(d);
  }

  const seen = new Set();
  const ordered = [...SECTION_ORDER, ...[...bySection.keys()].filter((k) => !SECTION_ORDER.includes(k)).sort()];
  for (const sec of ordered) {
    if (seen.has(sec) || !bySection.has(sec)) continue;
    seen.add(sec);
    const label = sec === ""
      ? "Overview"
      : sec.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
    lines.push(`## ${label}`);
    lines.push("");
    for (const d of bySection.get(sec)) {
      const url = d.slug === "index" ? `${base}/` : `${base}/${d.slug}/`;
      const desc = d.description ? `: ${d.description}` : "";
      lines.push(`- [${d.title}](${url})${desc}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

async function writeRawMarkdown(docs) {
  const rawRoot = path.join(PUBLIC_ROOT, "raw");
  await fs.mkdir(rawRoot, { recursive: true });
  for (const d of docs) {
    const outFile = path.join(rawRoot, `${d.slug}.md`);
    await fs.mkdir(path.dirname(outFile), { recursive: true });
    // Keep the frontmatter in the raw output — readers expect title/description
    // visible; this also makes a copied page paste cleanly into another doc.
    const original = await fs.readFile(d.filePath, "utf-8");
    await fs.writeFile(outFile, original, "utf-8");
  }
}

async function main() {
  const docs = await loadCorpus();
  await fs.mkdir(PUBLIC_ROOT, { recursive: true });
  await fs.writeFile(path.join(PUBLIC_ROOT, "llms.txt"), buildLlmsTxt(docs), "utf-8");
  await writeRawMarkdown(docs);
  console.log(
    `[generate-static-docs] wrote public/llms.txt + public/raw/<slug>.md for ${docs.length} pages`,
  );
}

main().catch((err) => {
  console.error("[generate-static-docs] failed:", err);
  process.exit(1);
});
