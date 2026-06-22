# Docs as Code

> Source: [writethedocs.org/guide/docs-as-code](https://www.writethedocs.org/guide/docs-as-code/)

The philosophy: **treat documentation exactly like code.** Same repo, same
review process, same tools, same standards.

## The five rules

1. **Plain text source** — Markdown, reStructuredText, AsciiDoc. No Word, no Confluence (as primary source).
2. **Version control** — docs live in git, alongside the code they describe.
3. **Review** — doc changes go through pull requests, just like code changes.
4. **Test** — broken links, dead code samples, and outdated screenshots are bugs.
5. **Build** — generate the published site from the source on every commit (CI).

## Why it works

- **Drift**: when code changes, the doc PR is in the same review. Reviewers catch the gap before merge.
- **Authorship**: developers will write docs if it's `git commit && open PR`. They won't if it's "log into Confluence".
- **History**: `git blame` and `git log` apply to docs.
- **Citations**: file paths and line numbers are stable references.

## The trade-off

Docs as code expects readers to find docs through the repo or a generated
site, not through search-driven knowledge bases. If the audience needs a
search-first experience, you generate one (Hugo, MkDocs, Docusaurus, Sphinx),
but the **source of truth** stays in the repo.

## Practical workflow

### Folder layout

```
project/
├── README.md              # Top-level entry point
├── docs/
│   ├── tutorials/
│   ├── how-to/
│   ├── reference/
│   ├── explanation/
│   └── adr/
├── src/
└── ...
```

### PR rules

- Code change without doc update? **Reviewer asks for one.**
- Doc-only PR? **Treat it like a code PR — review, tests, merge.**
- New ADR? **Same PR as the code change it describes.**

### CI checks

- Lint markdown (`markdownlint`, `vale`)
- Check internal links (`lychee`, `markdown-link-check`)
- Spell-check (`cspell`)
- Run code samples (`pytest --doctest-modules`, `mdtest`)

### Publishing

Pick one static site generator that fits your stack:

| Generator | Strength |
|----|----|
| **MkDocs** + Material | Easiest. Markdown only. Great defaults |
| **Docusaurus** | React-based, versioning built in |
| **Sphinx** | Python projects, autodoc from docstrings |
| **Hugo** | Fastest builds, more themes |
| **Astro Starlight** | Modern, fast, content-focused |

## Anti-patterns

- **Docs in a separate repo from code**: drift is guaranteed
- **Docs as Confluence pages, code in git**: see above
- **Auto-generated reference is the only doc**: no tutorials, no explanation, no how-to
- **A README that's 4000 lines**: the README is a router, not the destination
- **PR template that doesn't ask about doc updates**: easy to miss
