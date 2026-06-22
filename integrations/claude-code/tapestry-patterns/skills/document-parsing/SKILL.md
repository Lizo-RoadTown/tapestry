---
name: document-parsing
description: Convert PDFs, Word docs, PowerPoint, Excel, and scanned images into LLM-friendly markdown. Use when the agent needs to read source documents — research papers, reports, slide decks, financial filings — that aren't already in plain text.
---

# Document parsing

Three viable parsers, ordered by how often you'll reach for each:

## Decision tree

```
Is the source a plain-text PDF (no complex tables/charts/scans)?
  → Use Claude API native PDF support. No extra dep, no extra cost beyond tokens.

Otherwise — does it have:
  - complex tables, charts, multi-column academic layouts, or scanned pages?
  - financial filings, regulatory docs, slide decks?
  - need for structured markdown output reusable across agents?
  → Use LlamaParse. Hosted, has a free tier, best-in-class for layout-heavy docs.

Need fully local / air-gapped / unlimited-volume?
  → Use Marker or Docling (both open source, run locally).
```

## 1. Claude native PDF (default for simple PDFs)

Already available — Claude API accepts PDFs as content blocks alongside text. No SDK install. Best for: plain-text papers, simple reports, anything the model can read directly.

Limit: ~32 MB / 100 pages per document. Tables and charts are extracted but with less fidelity than LlamaParse.

## 2. LlamaParse (default for complex docs)

Hosted service from LlamaIndex. Free tier (check current limits at [cloud.llamaindex.ai](https://cloud.llamaindex.ai)). Produces structured markdown that preserves tables, headers, and ordering.

### Setup

```bash
pip install llama-parse
export LLAMA_CLOUD_API_KEY=llx-...   # from cloud.llamaindex.ai
```

The **LlamaIndex docs MCP** is also wired into this repo via [`.mcp.json`](../../.mcp.json) — Claude Code (and any other client per [`MCP.md`](../../MCP.md)) can search LlamaIndex/LlamaParse documentation directly, no extra setup. Use it when you need current API details that the model's training data may have missed.

### Use from the agent (Python)

```python
from llama_parse import LlamaParse

parser = LlamaParse(
    result_type="markdown",          # "markdown" | "text" | "json"
    parsing_instruction="""
        Extract tables as markdown tables.
        Preserve section headings.
        Include page numbers as footnotes.
    """,
)

docs = parser.load_data("./paper.pdf")
markdown = docs[0].text
```

### Output contract

LlamaParse returns markdown where:
- Tables are real markdown tables (not flattened text)
- Headers preserve hierarchy (`#`, `##`, etc.)
- Lists, bold, italic preserved
- Images/charts get a `[Figure N: caption]` placeholder unless multimodal mode is enabled

### Cost / limits

- Free tier: ~1000 pages/day (verify current at LlamaCloud — they change)
- Paid tier: per-page pricing
- Caching: results are cached on their side for ~48h by document hash, so re-parsing the same doc is free

### Modes

- **Default mode** — fast, cheap, good for ~95% of docs
- **Premium mode** — slower, better for academic papers with equations and complex multi-column layouts
- **Multimodal mode** — uses a vision LLM; best for scanned docs, handwritten notes, chart-heavy presentations

Pick mode per document, not globally.

## 3. Local / open-source alternatives

When LlamaParse won't work (offline, regulatory, unlimited volume):

| Tool | Strength | Install |
|------|----------|---------|
| [Marker](https://github.com/datalab-to/marker) | Best open-source quality on academic PDFs | `pip install marker-pdf` |
| [Docling](https://github.com/docling-project/docling) | IBM, fast, good table detection | `pip install docling` |
| [Unstructured](https://github.com/Unstructured-IO/unstructured) | Broadest format support (DOCX, PPTX, EML, ...) | `pip install "unstructured[all-docs]"` |

All three run locally on CPU; Marker and Docling can use GPU if available.

## Wiring into the deepagents researcher

The researcher subagent gets document parsing as a tool. Add to [`subagents/researcher/deepagents.toml`](../../subagents/researcher/deepagents.toml):

```toml
# Uncomment to enable LlamaParse as a researcher tool.
# [tools.parse_document]
# module = "tools.parse_document"
# function = "parse_pdf"
```

And ship a thin wrapper at `platform/api/tools/parse_document.py`:

```python
from llama_parse import LlamaParse

def parse_pdf(path: str, mode: str = "default") -> str:
    """Parse a PDF/DOCX/PPTX/XLSX into markdown. Returns the parsed text."""
    parser = LlamaParse(result_type="markdown", premium_mode=(mode == "premium"))
    docs = parser.load_data(path)
    return "\n\n".join(d.text for d in docs)
```

The researcher then calls `parse_document.parse_pdf("./paper.pdf")` when it encounters a source it needs to read.

## When NOT to parse

- **Source is already markdown / plain text** — just read it
- **Source is a webpage** — use a web fetch tool with HTML→markdown (Tavily, Firecrawl, or `trafilatura`); LlamaParse is for binary docs
- **Source is too large to parse upfront** — fetch a sample first, decide if the whole doc warrants the cost
- **You need verbatim citations with page numbers** — LlamaParse loses some positional fidelity. Use `pypdf` or `pdfplumber` to grab the exact page span for citation, then LlamaParse for content extraction

## Pair with the public stack

PDFs / Office docs are covered here. For other input classes, hand off:

- **`firecrawl:firecrawl-scrape`** — single JS-rendered webpage to markdown
- **`firecrawl:firecrawl-crawl`** — multi-page sites, documentation, full crawls
- **`firecrawl:firecrawl-search`** — when the source needs to be *found* first
- **`huggingface-skills:huggingface-datasets`** — when the source is on the HF hub as a dataset
- **`huggingface-skills:huggingface-papers`** — arXiv / HF paper IDs (skip parsing — pulls structured content)
