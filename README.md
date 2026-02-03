# Clean Docs

> CLI tool for documentation quality - validate code snippets, detect broken links, auto-fix issues, and integrate with CI/CD.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/Algiras/clean-docs/actions/workflows/tests.yml/badge.svg)](https://github.com/Algiras/clean-docs/actions/workflows/tests.yml)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://algiras.github.io/clean-docs)
[![PyPI](https://img.shields.io/pypi/v/clean-docs)](https://pypi.org/project/clean-docs/)

<p align="center">
  <img src="demo.gif" alt="clean-docs demo" width="700">
</p>

**[Documentation](https://algiras.github.io/clean-docs)** | **[Installation](#installation)** | **[Quick Start](#quick-start)** | **[CI/CD Integration](https://algiras.github.io/clean-docs/guides/ci-cd/)**

## Features

- **🔍 Code Snippet Validation** - Validate code examples against actual source code using [tree-sitter](https://tree-sitter.github.io/)
- **🔗 Link Checking** - Internal files, external URLs, GitHub repos, anchors
- **🔧 Auto-fixing** - Outdated snippets, missing extensions, anchor typos, case issues
- **💾 Smart Caching** - SQLite-based with 24h TTL, batch operations
- **👥 CODEOWNERS Support** - Group issues by team, create PRs per owner
- **🚀 CI/CD Ready** - JSON/Markdown output, GitHub annotations, exit codes

## Installation

```bash
# Quick install (curl)
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# With snippet validation
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash -s -- --snippets

# With all features
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash -s -- --all

# Or via pip
pip install clean-docs                    # Core features
pip install 'clean-docs[snippets]'        # + Code snippet validation
pip install 'clean-docs[semantic]'        # + AI-powered analysis
pip install 'clean-docs[snippets,semantic]'  # All features
```

## Quick Start

```bash
# Check setup
clean-docs doctor

# Scan documentation for broken links
clean-docs scan ./docs

# Validate code snippets against source
clean-docs validate-snippets ./docs --code-dir ./src

# Auto-fix issues
clean-docs scan ./docs --fix --yes
```

## Usage

### Scan for Issues

```bash
# Basic scan
clean-docs scan ./docs

# Fast mode (internal links only)
clean-docs scan ./docs --internal-only

# With options
clean-docs scan ./docs \
  --verbose \
  --timeout 30 \
  --retry 3 \
  --fail-fast
```

### Output Formats

```bash
# Console (default)
clean-docs scan ./docs

# JSON
clean-docs scan ./docs --format json

# Markdown report
clean-docs scan ./docs --format markdown --output report.md

# GitHub Actions annotations
clean-docs scan ./docs --github-annotations
```

### Fix Issues

```bash
# Preview fixes
clean-docs scan ./docs --fix --dry-run

# Interactive (prompts for each fix)
clean-docs scan ./docs --fix

# Auto-fix all
clean-docs scan ./docs --fix --yes
```

### CODEOWNERS Integration

For monorepos, group issues by team and create separate PRs:

```bash
# View ownership
clean-docs owners ./docs/api.md

# Scan grouped by owner
clean-docs scan . --group-by-owner

# Create PRs per team
clean-docs fix-prs . --codeowners CODEOWNERS

# Only for specific team
clean-docs fix-prs . --only-owner @myteam/docs
```

### Code Snippet Validation

Validate that code examples in documentation match actual source code:

```bash
# Install with snippet validation support
pip install 'clean-docs[snippets]'

# Validate snippets against source code
clean-docs validate-snippets ./docs --code-dir ./src

# Preview what would be fixed
clean-docs validate-snippets README.md --fix --dry-run

# Auto-fix outdated snippets
clean-docs validate-snippets ./docs --fix

# Adjust similarity threshold (default: 0.8)
clean-docs validate-snippets . --threshold 0.7

# Output as JSON for CI
clean-docs validate-snippets . --format json
```

**Supported languages:** Java, Python, Scala, TypeScript, JavaScript, Go, Rust, Bazel

**How it works:**
1. Extracts code blocks from markdown files
2. Parses source code using [tree-sitter](https://tree-sitter.github.io/) to index symbols
3. Matches snippets to source using file hints, symbol names, and code similarity
4. Reports outdated examples with diffs and suggested fixes

### Semantic Analysis (AI-Powered)

Find orphaned docs and missing documentation using embeddings:

```bash
# Install with semantic support
pip install 'clean-docs[semantic]'

# Find docs with no related code
clean-docs semantic . --orphaned

# Find code without documentation
clean-docs semantic . --missing

# Both with custom threshold
clean-docs semantic . --orphaned --missing --threshold 0.6

# Specify directories
clean-docs semantic . --docs ./docs --code ./src
```

### Cache Management

```bash
# View stats
clean-docs cache --stats

# Show broken links
clean-docs cache --broken

# Clear expired
clean-docs cache --cleanup

# Clear all
clean-docs cache --clear
```

## Configuration

Create `.clean-docs.yaml`:

```yaml
links:
  timeout: 10           # HTTP timeout (seconds)
  concurrency: 20       # Parallel checks
  ignore_patterns:
    - "localhost"
    - "127.0.0.1"
    - "example.com"

cache:
  ttl_hours: 24
```

## CI/CD

### GitHub Actions

```yaml
name: Docs Check

on: [push, pull_request]

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install and check
        run: |
          pip install -e .
          clean-docs scan . --github-annotations --internal-only
      
      - name: Report on failure
        if: failure()
        run: |
          clean-docs scan . --format markdown >> $GITHUB_STEP_SUMMARY || true
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | Issues found (broken links, outdated snippets) |

## Link Types Supported

| Type | Example |
|------|---------|
| Internal | `./file.md`, `../docs/guide.md` |
| Anchors | `#section`, `./file.md#anchor` |
| External | `https://example.com` |
| GitHub | `github.com/user/repo/blob/main/file.md` |

## Auto-Fix Capabilities

| Fixable | Example |
|---------|---------|
| Outdated code snippets | Updates examples to match current source |
| Missing extension | `./file` → `./file.md` |
| Anchor normalization | `#My-Section` → `#my-section` |
| Case sensitivity | `./File.md` → `./file.md` |

**Manual review needed:**
- External 404s
- Deleted files with no redirect
- Semantic anchor changes
- Code snippets with no source match

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run specific test
pytest tests/test_clean_docs.py::TestCache -v
```

## License

MIT License - see [LICENSE](LICENSE).
