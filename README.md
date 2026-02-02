# Clean Docs

> CLI tool for documentation quality - detect broken links, auto-fix issues, and integrate with CI/CD.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://github.com/Algiras/clean-docs/actions/workflows/tests.yml/badge.svg)](https://github.com/Algiras/clean-docs/actions/workflows/tests.yml)

<p align="center">
  <img src="demo.gif" alt="clean-docs demo" width="700">
</p>

## Features

- **Link Checking** - Internal files, external URLs, GitHub repos, anchors
- **Auto-fixing** - Missing extensions, anchor typos, case issues
- **Smart Caching** - SQLite-based with 24h TTL, batch operations
- **CODEOWNERS Support** - Group issues by team, create PRs per owner
- **CI/CD Ready** - JSON/Markdown output, GitHub annotations, exit codes

## Quick Start

```bash
# Install
pip install -e .  # or: pip install clean-docs (when published)

# Check setup
clean-docs doctor

# Scan documentation
clean-docs scan ./docs

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
| `1` | Broken links found |

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
| Missing extension | `./file` → `./file.md` |
| Anchor normalization | `#My-Section` → `#my-section` |
| Case sensitivity | `./File.md` → `./file.md` |

**Manual review needed:**
- External 404s
- Deleted files with no redirect
- Semantic anchor changes

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
