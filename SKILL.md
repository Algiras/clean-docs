---
name: clean-docs
description: Validate documentation quality - check for broken links, validate code snippets against source code, and auto-fix issues. Use when working with markdown documentation, README files, or when the user wants to check documentation for broken links or outdated code examples.
license: MIT
metadata:
  author: Algiras
  version: "0.1.0"
  homepage: https://github.com/Algiras/clean-docs
  docs: https://algiras.github.io/clean-docs
compatibility: Requires Python 3.10+. Optional: tree-sitter for code snippet validation.
---

# Clean Docs

A CLI tool for documentation quality - validate code snippets, detect broken links, auto-fix issues.

## Installation

```bash
# Quick install
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# Or via pip
pip install clean-docs

# With code snippet validation
pip install 'clean-docs[snippets]'
```

## Core Commands

### Check Setup

```bash
clean-docs doctor
```

Verifies Python version, GitHub CLI, and other prerequisites.

### Scan for Broken Links

```bash
# Scan documentation directory
clean-docs scan ./docs

# Internal links only (fast, no HTTP requests)
clean-docs scan ./docs --internal-only

# Output as JSON
clean-docs scan ./docs --format json

# With verbose output
clean-docs scan ./docs --verbose
```

### Validate Code Snippets

Checks that code examples in documentation match actual source code:

```bash
# Basic validation
clean-docs validate-snippets ./docs --code-dir ./src

# Preview fixes
clean-docs validate-snippets ./docs --fix --dry-run

# Auto-fix outdated snippets
clean-docs validate-snippets ./docs --fix

# Adjust similarity threshold (default: 0.8)
clean-docs validate-snippets ./docs --threshold 0.7
```

### Auto-Fix Issues

```bash
# Preview what would be fixed
clean-docs scan ./docs --fix --dry-run

# Interactive mode (prompts for each fix)
clean-docs scan ./docs --fix

# Auto-fix all without prompting
clean-docs scan ./docs --fix --yes
```

### Cache Management

```bash
# View cache statistics
clean-docs cache --stats

# Show cached broken links
clean-docs cache --broken

# Clear cache
clean-docs cache --clear
```

## Supported Link Types

| Type | Example |
|------|---------|
| Internal | `./file.md`, `../docs/guide.md` |
| Anchors | `#section`, `./file.md#anchor` |
| External | `https://example.com` |
| GitHub | `github.com/user/repo/blob/main/file.md` |

## Supported Languages for Snippet Validation

Python, Java, Scala, TypeScript, JavaScript, Go, Rust, Bazel

## What Gets Auto-Fixed

- Outdated code snippets (updates to match source)
- Missing file extensions (`./file` → `./file.md`)
- Anchor normalization (`#My-Section` → `#my-section`)
- Case sensitivity issues (`./File.md` → `./file.md`)

## CI/CD Integration

### GitHub Actions

```yaml
- name: Check documentation
  run: |
    pip install clean-docs
    clean-docs scan . --internal-only --github-annotations
```

### Exit Codes

- `0`: All checks passed
- `1`: Issues found

## Examples

### Check documentation before committing

```bash
clean-docs scan . --internal-only
clean-docs validate-snippets ./docs --code-dir ./src
```

### Generate a report

```bash
clean-docs scan ./docs --format markdown > report.md
```

### Fix all issues automatically

```bash
clean-docs scan ./docs --fix --yes
clean-docs validate-snippets ./docs --fix
```

## More Information

- Documentation: https://algiras.github.io/clean-docs
- GitHub: https://github.com/Algiras/clean-docs
