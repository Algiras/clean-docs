# Clean Docs

> CLI tool for cleaning up documentation repositories - detect broken links, find orphaned docs, and keep your docs in sync with your code.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## 🚀 Quick Start

```bash
# Install
pip install clean-docs

# Check if your system is ready
clean-docs doctor

# Scan your docs for broken links
clean-docs scan ./docs

# Fix links automatically
clean-docs scan ./docs --fix --yes
```

## 📦 Installation

### One-Line Install (Recommended)

```bash
# Quick install with curl
curl -fsSL https://raw.githubusercontent.com/yourusername/clean-docs/main/install.sh | bash

# Or with semantic analysis support
WITH_SEMANTIC=1 curl -fsSL https://raw.githubusercontent.com/yourusername/clean-docs/main/install.sh | bash
```

> **Note:** Replace `yourusername` with the actual GitHub username/org after publishing.

### Pip Install

```bash
# Basic install (link checking only)
pip install clean-docs

# With semantic analysis
pip install clean-docs[semantic]
```

### With Semantic Analysis (Optional)
```bash
pip install clean-docs[semantic]
```

This adds AI-powered features to match docs with code using embeddings.

## 🎯 Features

### Core Features (Always Available)

| Feature | Description |
|---------|-------------|
| **Link Checking** | Validates internal, external, and GitHub links |
| **Iterative Fixing** | Auto-fixes links in a loop until all resolved |
| **Smart Caching** | Caches link status for 24h to speed up re-runs |
| **GitHub Integration** | Checks repo/branch/file existence via `gh` CLI |
| **CI/CD Ready** | JSON output and exit codes for automation |

### Optional Features (When Installed)

| Feature | Install Command |
|---------|----------------|
| **Semantic Analysis** | `pip install clean-docs[semantic]` |
| **Agent Mode** | `gh extension install github/copilot-cli` |

## 📖 Usage Guide

### 1. Doctor Command - Check Your Setup

```bash
# Check required dependencies
clean-docs doctor

# Check everything including optional features
clean-docs doctor --all
```

**Checks include:**
- Python version (>= 3.10)
- GitHub CLI availability & auth
- Cache directory permissions
- Semantic analysis dependencies (optional)
- Copilot CLI (optional)

### 2. Scan Command - Find Issues

```bash
# Basic scan
clean-docs scan ./docs

# Scan with all options
clean-docs scan ./docs \
  --verbose \              # Show all links, not just broken
  --format json \          # JSON output for CI
  --config ./my-config.yaml # Custom config file
```

### 3. Fix Command - Repair Issues

```bash
# Dry run - preview what would be fixed (safe)
clean-docs scan ./docs --fix --dry-run

# Interactive mode - prompts for confirmation
clean-docs scan ./docs --fix

# Auto-fix everything without prompts
clean-docs scan ./docs --fix --yes
```

**What gets fixed:**
- Missing `.md` extensions (`./file` → `./file.md`)
- Anchor typos (`#sectin` → `#section`)
- Case sensitivity issues

### 4. Cache Management

```bash
# View cache statistics
clean-docs cache --stats

# Clear the cache
clean-docs cache --clear
```

## ⚙️ Configuration

Create `.clean-docs.yaml` in your project root:

```yaml
links:
  timeout: 10                    # HTTP request timeout (seconds)
  concurrency: 20                # Parallel link checks
  ignore_patterns:               # Skip these URLs
    - "localhost"
    - "127.0.0.1"
    - "example.com"
    - "*.local"

cache:
  ttl_hours: 24                  # Cache expiration
  max_size_mb: 100               # Max cache size
  # dir: ~/.cache/clean-docs     # Custom location (default: system temp)

output:
  show_progress: true            # Progress bars
  colors: auto                   # auto/always/never
```

### Generate Default Config

```bash
clean-docs scan ./docs --init
```

This creates `.clean-docs.yaml` with sensible defaults.

## 🔄 CI/CD Integration

### GitHub Actions Example

```yaml
name: Docs Check

on:
  push:
    paths:
      - 'docs/**'
      - '*.md'
  pull_request:
    paths:
      - 'docs/**'
      - '*.md'

jobs:
  check-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Clean Docs
        run: pip install clean-docs
      
      - name: Check Documentation
        run: clean-docs scan . --format json
        continue-on-error: true
      
      - name: Comment PR with Results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            // Read results and post comment...
```

### Exit Codes

- `0`: All checks passed
- `1`: Broken links or errors found

## 🧠 Semantic Analysis (Optional)

When you install with `pip install clean-docs[semantic]`, you get:

```bash
# Find docs with no related code (orphaned docs)
clean-docs semantic --orphaned ./docs

# Find code with no docs (missing docs)
clean-docs semantic --missing-docs ./src

# Suggest related code for a doc file
clean-docs semantic --suggest ./docs/api.md ./src
```

Uses `mxbai-embed-large` model for 1024-dimensional embeddings.

## 📁 Cache Location

By default, cache is stored in your **system temp directory**:

| OS | Default Location |
|----|------------------|
| macOS | `/var/folders/.../T/clean-docs-cache/` |
| Linux | `/tmp/clean-docs-cache/` |
| Windows | `%TEMP%\clean-docs-cache\` |

**Why temp directory?**
- Automatically cleaned by OS
- No pollution of project directories
- Works across different projects
- Can be overridden in config

## 🤖 Agent Mode (Future)

Planned features for AI-powered fixes:
- Automatic PR creation with fixes
- Intelligent link suggestions
- Content rewriting assistance

Requirements: `gh copilot` CLI extension

## 🛠️ Development

```bash
# Clone the repo
git clone https://github.com/yourusername/clean-docs.git
cd clean-docs

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black clean_docs/
ruff clean_docs/
mypy clean_docs/

# Test CLI
clean-docs doctor
clean-docs scan ./test_docs --fix --dry-run
```

### Project Structure

```
clean-docs/
├── clean_docs/           # Main package
│   ├── cli.py           # Typer CLI commands
│   ├── config.py        # YAML configuration
│   ├── doctor.py        # Prerequisites checker
│   ├── cache.py         # SQLite link cache
│   ├── link_checker.py  # Link validation logic
│   ├── fixer.py         # Auto-fix engine
│   ├── semantic.py      # Embeddings (optional)
│   └── parsers/
│       └── markdown.py  # Markdown parser
├── tests/               # Test suite
├── pyproject.toml       # Package config
└── README.md           # This file
```

## 📝 Supported Link Types

| Type | Example | Checked |
|------|---------|---------|
| Internal relative | `./file.md` | ✅ File existence |
| Internal absolute | `/docs/file.md` | ✅ File existence |
| External HTTP | `https://example.com` | ✅ HTTP status |
| GitHub repo | `github.com/user/repo` | ✅ Repo/branch/file |
| Anchor | `#section-heading` | ✅ Heading existence |
| Reference-style | `[text][ref]` | ✅ Reference lookup |

## 🐛 Troubleshooting

### "Cannot connect to host" errors
Increase timeout in config:
```yaml
links:
  timeout: 30  # Increase from default 10s
```

### Too many GitHub API rate limits
- Ensure `gh` CLI is authenticated: `gh auth login`
- Or set `GITHUB_TOKEN` environment variable

### Cache issues
```bash
# Clear cache
clean-docs cache --clear

# Or use custom location
clean-docs scan ./docs --config ./no-cache-config.yaml
```

### Semantic analysis not working
```bash
# Reinstall with semantic dependencies
pip install --force-reinstall clean-docs[semantic]
```

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 💡 Roadmap

- [x] Core link checking
- [x] Iterative fix loop
- [x] Smart caching
- [x] Semantic analysis (optional)
- [ ] HTML documentation support
- [ ] Plugin system
- [ ] Web dashboard
- [ ] Agent-based auto-fixes

---

**Made with ❤️ for better documentation**