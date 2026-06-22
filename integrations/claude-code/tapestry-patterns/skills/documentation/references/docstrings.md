# Docstring conventions by language

A docstring answers four questions:

1. **What does this do?** (one sentence summary)
2. **What are the parameters?** (types and meaning)
3. **What does it return?** (type and meaning)
4. **What can go wrong?** (exceptions, edge cases)

It does **not** explain *how* — that's what readable code is for.

## Python

Standard: [PEP 257](https://peps.python.org/pep-0257/) for the basics.
Format: **Google style** or **NumPy style** for structured docstrings.
Both are supported by Sphinx via [napoleon](https://www.sphinx-doc.org/en/master/usage/extensions/napoleon.html).

### Google style (recommended for most projects)

```python
def extract_couplings(source_text: str, max_items: int = 10) -> list[Coupling]:
    """Extract coupling relationships from a source document.

    Args:
        source_text: Raw text of the source document. Must be UTF-8.
        max_items: Upper bound on returned couplings. Defaults to 10.

    Returns:
        A list of Coupling objects, ordered by extraction confidence
        (highest first). Empty if no couplings could be identified.

    Raises:
        ValueError: If source_text is empty or not valid UTF-8.
        ExtractionTimeout: If the underlying LLM call exceeds 60s.
    """
```

### NumPy style (preferred in scientific code)

```python
def extract_couplings(source_text, max_items=10):
    """
    Extract coupling relationships from a source document.

    Parameters
    ----------
    source_text : str
        Raw text of the source document. Must be UTF-8.
    max_items : int, optional
        Upper bound on returned couplings, by default 10.

    Returns
    -------
    list of Coupling
        Couplings ordered by extraction confidence (highest first).

    Raises
    ------
    ValueError
        If source_text is empty or not valid UTF-8.
    """
```

### Module docstrings

```python
"""Extraction pipeline.

This module implements the FRAMES coupling extraction agent. It reads
source documents, identifies coupling candidates, and emits validated
Coupling records to storage.
"""
```

### Rules

- One-sentence summary on the first line, ending with a period
- Blank line between summary and details
- Imperative mood ("Return the X", not "Returns the X")
- Don't restate the type signature in prose — the signature does that

## JavaScript / TypeScript

Standard: [JSDoc](https://jsdoc.app/) for JavaScript, [TSDoc](https://tsdoc.org/) for TypeScript.
TypeScript users: **types in the signature, not in JSDoc tags**. JSDoc tags duplicate the type system unnecessarily.

### TypeScript (TSDoc)

```typescript
/**
 * Extract coupling relationships from a source document.
 *
 * @param sourceText - Raw text of the source document. Must be UTF-8.
 * @param maxItems - Upper bound on returned couplings. Defaults to 10.
 * @returns Couplings ordered by extraction confidence (highest first).
 * @throws ValueError if `sourceText` is empty or not valid UTF-8.
 */
export function extractCouplings(
  sourceText: string,
  maxItems: number = 10,
): Coupling[] {
  ...
}
```

### JavaScript (JSDoc)

```javascript
/**
 * Extract coupling relationships from a source document.
 *
 * @param {string} sourceText - Raw text of the source document.
 * @param {number} [maxItems=10] - Upper bound on returned couplings.
 * @returns {Coupling[]} Couplings ordered by extraction confidence.
 * @throws {ValueError} If sourceText is empty or not valid UTF-8.
 */
function extractCouplings(sourceText, maxItems = 10) {
  ...
}
```

## Other languages

- **Go**: doc comment immediately above the declaration; first word is the symbol name. See [Go Doc Comments](https://go.dev/doc/comment).
- **Rust**: `///` doc comments, supports markdown, runs as doctests. See [rustdoc](https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html).
- **Java**: Javadoc with `@param`, `@return`, `@throws`.
- **C#**: XML documentation comments (`///`).

Whatever language: **find the idiomatic standard, follow it exactly**, and let the language's tooling generate reference docs from your docstrings.

## When to skip a docstring

- **Private helper functions** with self-evident names (`_format_row(row)` — fine without one)
- **Dunder methods** that just call into something documented (`__repr__` calling a helper)
- **Test functions** — descriptive names + assertions are usually enough

## Anti-patterns

- Docstring that just restates the function name: `"""Get user."""` on `get_user()` — write a real one or skip
- Docstring that explains the *implementation* — "Loops through the list and..." → wrong audience
- Outdated parameters — when you change the signature, update the docstring in the same commit
- Copy-paste from a similar function without updating types/names
- Multi-paragraph essay on a 3-line function — proportional to the surface
