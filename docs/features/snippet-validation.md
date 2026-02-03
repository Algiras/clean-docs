# Code Snippet Validation

Validate that code examples in your documentation actually match the source code they're supposed to represent.

## The Problem

Documentation code examples get outdated:

- APIs change but docs don't get updated
- Refactoring renames methods or changes signatures
- Copy-paste errors introduce bugs in examples
- Examples diverge from working code over time

## The Solution

Clean Docs parses your source code using [tree-sitter](https://tree-sitter.github.io/) to build an index of all symbols (functions, classes, methods). It then compares code blocks in your markdown files against this index to find:

- **Outdated snippets** - Code that partially matches but has drifted
- **Invalid examples** - Code that doesn't match anything in the codebase
- **Syntax errors** - Malformed code blocks

## Installation

```bash
pip install 'clean-docs[snippets]'
```

## Basic Usage

```bash
# Validate snippets in docs against source code
clean-docs validate-snippets ./docs --code-dir ./src

# Preview what would be fixed
clean-docs validate-snippets ./docs --fix --dry-run

# Auto-fix outdated snippets
clean-docs validate-snippets ./docs --fix

# Adjust similarity threshold (default: 0.8)
clean-docs validate-snippets . --threshold 0.7
```

## How Matching Works

Clean Docs uses multiple strategies to match documentation snippets to source code:

### 1. File Hints

If your code block contains a file path hint in a comment:

```python
# src/calculator.py
def add(a, b):
    return a + b
```

Clean Docs will look in that file first.

### 2. Symbol Names

Function and class names are extracted and matched:

```python
def calculate_total(items):  # Matches calculate_total in source
    ...
```

### 3. Code Similarity

For snippets without clear hints, clean-docs computes similarity scores using:

- Sequence matching (overall structure)
- Line-based matching (for partial snippets)
- Normalized comparison (ignoring whitespace/comments)

### 4. Semantic Embeddings (Optional)

With `clean-docs[semantic]` installed, you can use AI embeddings for fuzzy matching when exact matches fail.

## Output Formats

### Console (Default)

```bash
clean-docs validate-snippets ./docs
```

```
╭─────────────────────────────────────────╮
│ Code Snippet Validation                 │
│ Docs: ./docs                            │
│ Code: ./src                             │
╰─────────────────────────────────────────╯

Validating 12 code snippets...

✓ README.md:45 (python) - Valid
✗ README.md:78 (python) - Outdated
  Source: src/calculator.py:23
  Diff:
    - return a + b
    + return a * b

⚠ guide.md:112 (python) - No source match

Summary:
  Valid: 8
  Outdated: 3
  Not Found: 1
```

### JSON

```bash
clean-docs validate-snippets ./docs --format json
```

```json
{
  "total_snippets": 12,
  "valid": 8,
  "outdated": 3,
  "not_found": 1,
  "results": [...]
}
```

### Markdown

```bash
clean-docs validate-snippets ./docs --format markdown --output report.md
```

## Auto-Fix

When a snippet is outdated, clean-docs can automatically update it:

```bash
# Preview changes
clean-docs validate-snippets ./docs --fix --dry-run

# Apply fixes
clean-docs validate-snippets ./docs --fix
```

The fix preserves:

- Original fence markers and language hints
- Surrounding context and formatting
- Only updates the code content itself

## Configuration

### Similarity Threshold

The `--threshold` option controls how similar code must be to match:

| Threshold | Behavior |
|-----------|----------|
| 0.9+ | Very strict - nearly identical code only |
| 0.8 (default) | Balanced - allows minor differences |
| 0.7 | Lenient - more fuzzy matching |
| 0.5 | Very lenient - use with caution |

### Exclude Patterns

Skip certain files or directories:

```bash
clean-docs validate-snippets ./docs \
  --exclude "*.generated.md" \
  --exclude "archive/*"
```

## Supported Languages

| Language | File Extensions | Symbol Types |
|----------|-----------------|--------------|
| Python | `.py` | functions, classes, methods |
| Java | `.java` | methods, classes, interfaces |
| Scala | `.scala` | defs, classes, objects, traits |
| TypeScript | `.ts`, `.tsx` | functions, classes, interfaces |
| JavaScript | `.js`, `.jsx` | functions, classes |
| Go | `.go` | functions, methods, types |
| Rust | `.rs` | functions, structs, impls |
| Bazel | `BUILD`, `.bzl` | rules, macros |

## Best Practices

1. **Add file hints** to your code blocks when possible
2. **Use descriptive function names** that are unique
3. **Keep snippets focused** - smaller snippets match better
4. **Run in CI** to catch drift early
5. **Start with dry-run** before auto-fixing
