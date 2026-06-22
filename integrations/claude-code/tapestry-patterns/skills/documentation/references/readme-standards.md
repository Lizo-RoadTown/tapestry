# README standards

> Sources: [makeareadme.com](https://www.makeareadme.com/), [standard-readme](https://github.com/RichardLitt/standard-readme).

A top-level README is a **router**, not a destination. It answers four
questions and points to deeper docs for everything else:

1. **What is this?**
2. **Who is it for?**
3. **How do I get started?**
4. **Where do I go for more?**

If a section can't be answered in a paragraph or a short list, it belongs in
`docs/`, not in the README.

## Minimal skeleton

```markdown
# Project Name

One-sentence pitch. What is this thing.

A second sentence describing who it's for and the problem it solves.

[![License](badge)](LICENSE)
[![Build](badge)](ci-link)

---

## Quick start

The shortest path to a working result. Three to five commands max.

```bash
git clone <repo>
cd <repo>
<setup-command>
<run-command>
```

## Documentation

- [Tutorials](docs/tutorials/) — learning by doing
- [How-to guides](docs/how-to/) — task recipes
- [Reference](docs/reference/) — API and config details
- [Explanation](docs/explanation/) — the why

## Contributing

Link to `CONTRIBUTING.md` if substantial; otherwise inline:
> PRs welcome. Run `<test-command>` before submitting.

## License

[License name](LICENSE)
```

## Common sections (use only if relevant)

- **Background** — one paragraph, only if the project name doesn't tell the reader what it does
- **Install** — if the install is non-trivial
- **Usage** — link to tutorials/how-to instead, don't duplicate
- **API** — link to reference, don't inline
- **Maintainers** — for shared projects
- **Contributing** — link to `CONTRIBUTING.md`
- **License** — always

## Anti-patterns

- **README as the only documentation** — at some scale, that's a router, not a destination
- **Five paragraphs of marketing before "Install"** — readers want to act
- **"Coming soon" sections** — delete them; they look unfinished
- **Out-of-date Quick Start** — test it on a clean clone before committing
- **Badges that are broken or stale** — broken badges look worse than no badges
- **Embedded code samples that don't run** — make them executable or remove them
- **Mixing audiences** — separate "for users" and "for contributors" content

## When the README needs to be longer

If the project is **single-purpose and small** (a CLI tool, a library function),
a longer README that doubles as the reference is fine.

If the project is **multi-component** (an app + a library + an API), the
README must stay short and route to per-component docs.

The threshold: if a reader has to scroll past 2-3 screens to find what they
need, split it.

## Suggested files alongside the README

| File | Purpose |
|------|---------|
| `LICENSE` | Always |
| `CONTRIBUTING.md` | If accepting contributions |
| `CODE_OF_CONDUCT.md` | If running a community |
| `CHANGELOG.md` | If you publish releases |
| `SECURITY.md` | If reporting vulnerabilities matters |
| `CITATION.cff` | If the project should be cited (research) |
