"""Corpus loader for the Tapestry docs MCP.

Walks the Astro Starlight content tree (default: `apps/docs-site/src/content/docs/`)
and produces:

  - a list of Doc records (slug, title, description, body) for the in-memory
    index in indexer.py
  - a flattened llms.txt string per the llmstxt.org convention

Frontmatter parsing is intentionally minimal (regex over the first `---`-fenced
block, not a full YAML parser) so this package has no extra dependencies beyond
the `mcp` SDK itself.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


# Tolerate both LF and CRLF — Windows working trees get CRLF after Git checkout
# with core.autocrlf=true. The non-greedy (.+?) + \r?$ pattern strips any
# trailing \r without consuming it into the capture group.
_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_TITLE_RE = re.compile(r"^title:\s*(.+?)\r?$", re.MULTILINE)
_DESC_RE = re.compile(r"^description:\s*(.+?)\r?$", re.MULTILINE)


@dataclass(frozen=True)
class Doc:
    """One docs page. `slug` matches the URL path Astro Starlight produces:
    `systems/observer` for `apps/docs-site/src/content/docs/systems/observer.md`.
    """
    slug: str
    title: str
    description: str
    body: str         # body content with frontmatter stripped
    section: str      # top-level directory: "start", "explanation", "how-to", "reference", "systems", "observatory", or "" for root index
    file_path: str    # absolute path on disk — included for debugging, not for client consumption


def _parse_frontmatter(text: str) -> tuple[str, str, str]:
    """Return (title, description, body_without_frontmatter)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return ("", "", text)
    fm = m.group(1)
    body = text[m.end():]
    t = _TITLE_RE.search(fm)
    d = _DESC_RE.search(fm)
    title = t.group(1).strip().strip('"').strip("'") if t else ""
    desc = d.group(1).strip().strip('"').strip("'") if d else ""
    return (title, desc, body)


def load_corpus(docs_root: str | Path) -> list[Doc]:
    """Walk docs_root and return all .md / .mdx files as Doc records.

    Sorted by slug for stable ordering (matters for llms.txt determinism).
    """
    root = Path(docs_root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"DOCS_ROOT does not exist or is not a directory: {root}")

    docs: list[Doc] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix not in (".md", ".mdx"):
            continue
        rel = path.relative_to(root)
        # Slug: strip extension, use forward slashes regardless of OS.
        slug_parts = list(rel.with_suffix("").parts)
        # Astro convention: `index.md` at the root maps to slug `index`.
        slug = "/".join(slug_parts)
        section = slug_parts[0] if len(slug_parts) > 1 else ""

        text = path.read_text(encoding="utf-8")
        title, desc, body = _parse_frontmatter(text)
        docs.append(Doc(
            slug=slug,
            title=title or slug,
            description=desc,
            body=body,
            section=section,
            file_path=str(path),
        ))
    return docs


def build_llms_txt(docs: list[Doc], site_base_url: str) -> str:
    """Render a llms.txt-style flattened corpus from the loaded docs.

    Format follows the llmstxt.org convention: a top H1 with site identity,
    then per-section H2s listing pages as bullets with absolute URLs +
    one-line descriptions. Page bodies are NOT inlined here — clients that
    want full bodies call tapestry_docs_read or fetch the URL.
    """
    base = site_base_url.rstrip("/")
    lines: list[str] = []
    lines.append("# Tapestry")
    lines.append("")
    lines.append(
        "Tapestry is a user/agent support and reinforcement system. "
        "These docs describe how the platform observes coordination between "
        "operators and agents and how durable structure is produced from that observation."
    )
    lines.append("")

    by_section: dict[str, list[Doc]] = {}
    for d in docs:
        by_section.setdefault(d.section, []).append(d)

    section_order = ["", "start", "how-to", "explanation", "systems", "observatory", "reference"]
    seen: set[str] = set()
    for sec in section_order + sorted(set(by_section.keys()) - set(section_order)):
        if sec in seen or sec not in by_section:
            continue
        seen.add(sec)
        label = "Overview" if sec == "" else sec.replace("-", " ").title()
        lines.append(f"## {label}")
        lines.append("")
        for d in by_section[sec]:
            url = f"{base}/{d.slug}/" if d.slug != "index" else f"{base}/"
            desc = f": {d.description}" if d.description else ""
            lines.append(f"- [{d.title}]({url}){desc}")
        lines.append("")

    return "\n".join(lines)


def default_docs_root() -> str:
    """Resolve the corpus location in this order:

      1. DOCS_ROOT env var (operator override).
      2. Bundled corpus next to the package (docs_mcp/_corpus/) — what
         `pip install tapestry-docs-mcp` ships when scripts/bundle-corpus.py
         has been run before the wheel build.
      3. In-repo path (../../apps/docs-site/src/content/docs/) — the
         dev path when running from a tapestry clone with no bundle.

    The bundled-corpus tier is what makes plugin.json wiring portable:
    a consumer who runs `pip install tapestry-docs-mcp` then
    `python -m docs_mcp` gets a working server with no env var needed.
    """
    env = os.environ.get("DOCS_ROOT")
    if env:
        return env

    here = Path(__file__).resolve().parent

    bundled = here / "_corpus"
    if bundled.is_dir() and any(bundled.rglob("*.md")):
        return str(bundled)

    return str((here / ".." / ".." / "apps" / "docs-site" / "src" / "content" / "docs").resolve())
