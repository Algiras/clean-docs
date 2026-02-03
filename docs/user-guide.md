# User Guide

Complete guide to using Clean Docs CLI for documentation maintenance.

## Table of Contents

- [Getting Started](#getting-started)
- [Core Commands](#core-commands)
- [Configuration](#configuration)
- [Link Checking](#link-checking)
- [Fixing Links](#fixing-links)
- [CI/CD Integration](#cicd-integration)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

## Getting Started

### Installation

Choose your installation method:

```bash
# Quick install (recommended)
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# With semantic analysis support
WITH_SEMANTIC=1 curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# Or via pip
pip install clean-docs
# With semantic analysis
pip install clean-docs[semantic]
```

### Verify Installation

```bash
# Check if everything is working
clean-docs doctor

# Show help
clean-docs --help
```

## Core Commands

### 1. Doctor Command

Check your system setup:

```bash
# Basic check
clean-docs doctor

# Include optional features check
clean-docs doctor --all
```

**What it checks:**
- Python version (>= 3.10 required)
- GitHub CLI installation & authentication
- GITHUB_TOKEN environment variable
- Cache directory permissions
- Optional: Semantic analysis dependencies
- Optional: Copilot CLI availability

### 2. Scan Command

Find broken links in your documentation:

```bash
# Scan current directory
clean-docs scan .

# Scan specific directory
clean-docs scan ./docs

# Scan single file
clean-docs scan ./README.md

# Verbose mode (shows all links)
clean-docs scan ./docs --verbose

# JSON output for automation
clean-docs scan ./docs --format json

# Use custom config
clean-docs scan ./docs --config ./my-config.yaml
```

### 3. Cache Command

Manage the link status cache:

```bash
# View cache statistics
clean-docs cache --stats

# Clear the cache
clean-docs cache --clear
```

## Configuration

Create `.clean-docs.yaml` in your project root:

```yaml
# Basic configuration
links:
  timeout: 10                    # HTTP timeout in seconds
  concurrency: 20                # Parallel checks
  ignore_patterns:               # URLs to skip
    - "localhost"
    - "127.0.0.1"
    - "example.com"
    - "*.local"
    - "file://"

cache:
  ttl_hours: 24                  # Cache expiration
  max_size_mb: 100              # Max cache size
  # dir: ~/.cache/clean-docs    # Custom cache location

output:
  show_progress: true           # Show progress bars
  colors: auto                  # auto/always/never
```

### Generate Default Config

```bash
clean-docs scan . --init
```

This creates `.clean-docs.yaml` with sensible defaults.

## Link Checking

### Supported Link Types

| Link Type | Example | Validation |
|-----------|---------|------------|
| Internal (relative) | `./file.md` | File exists? |
| Internal (absolute) | `/docs/file.md` | File exists? |
| External (HTTP) | `https://example.com` | HTTP 200? |
| GitHub | `github.com/user/repo` | Repo/branch/file exists? |
| Anchor | `#section-name` | Heading exists? |
| Reference | `[text][ref]` | Reference defined? |

### Checking GitHub Links

Clean Docs can verify GitHub repository links:

1. **Using `gh` CLI** (recommended):
   ```bash
   # Authenticate
   gh auth login
   
   # Check GitHub links
   clean-docs scan . --verbose
   ```

2. **Using GITHUB_TOKEN**:
   ```bash
   # Set token
   export GITHUB_TOKEN=your_token_here
   
   # Run scan
   clean-docs scan .
   ```

### Performance Tips

- **First run**: Takes longer (no cache)
- **Subsequent runs**: Fast (cached results)
- **Cache location**: System temp directory
- **Cache TTL**: 24 hours by default

## Fixing Links

### Dry Run (Preview)

See what would be fixed without making changes:

```bash
clean-docs scan ./docs --fix --dry-run
```

### Interactive Mode

Review and approve each fix:

```bash
clean-docs scan ./docs --fix
```

You'll be prompted to confirm each iteration of fixes.

### Auto-Fix Mode

Apply all auto-fixable changes without prompting:

```bash
clean-docs scan ./docs --fix --yes
```

### What Gets Fixed

- ✅ Missing `.md` extensions (`./file` → `./file.md`)
- ✅ Anchor typos (suggestions like `#sectin` → `#section`)
- ✅ Case sensitivity issues (`File.md` → `file.md`)

### What Needs Manual Review

- ❌ External broken URLs
- ❌ Missing files without clear suggestions
- ❌ Non-existent GitHub repos

## CI/CD Integration

### GitHub Actions

```yaml
name: Documentation Check

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Clean Docs
        run: pip install clean-docs
      
      - name: Check documentation
        run: clean-docs scan . --format json
        continue-on-error: true
      
      - name: Comment PR with results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('link-check-results.json', 'utf8'));
            
            let body = '## 🔗 Link Check Results\n\n';
            body += `**Status:** ${results.summary.broken_links === 0 ? '✅ All good' : '❌ Issues found'}\n\n`;
            body += `- Files: ${results.summary.files_checked}\n`;
            body += `- Links: ${results.summary.total_links}\n`;
            body += `- Broken: ${results.summary.broken_links}\n`;
            
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
```

### GitLab CI

```yaml
# .gitlab-ci.yml
docs-check:
  image: python:3.12
  script:
    - pip install clean-docs
    - clean-docs scan . --format json > results.json
  artifacts:
    reports:
      junit: results.xml
  allow_failure: true
```

### Exit Codes

- `0`: All checks passed
- `1`: Broken links or errors found

Use for CI gates:

```bash
# Strict mode (fail CI on broken links)
clean-docs scan . || exit 1

# Lenient mode (report but don't fail)
clean-docs scan . || true
```

## Advanced Features

### Semantic Analysis (Optional)

When installed with `pip install clean-docs[semantic]`:

```bash
# Find docs without related code
clean-docs semantic --orphaned ./docs

# Find code without documentation
clean-docs semantic --missing-docs ./src

# Suggest related code
clean-docs semantic --suggest ./docs/api.md ./src
```

**Use case:** Identify orphaned documentation or code that needs documentation.

### Working with Monorepos

```bash
# Scan specific packages
for pkg in packages/*/; do
  echo "Checking $pkg..."
  clean-docs scan "$pkg/docs" --config "$pkg/.clean-docs.yaml" || true
done
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: clean-docs
        name: Check documentation links
        entry: clean-docs scan .
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Issues

**"clean-docs: command not found"**
```bash
# Add to PATH (see install.sh output)
export PATH="$HOME/.local/bin:$PATH"

# Or reinstall with proper permissions
pip install --force-reinstall clean-docs
```

**"Cannot connect to host" errors**
```yaml
# Increase timeout in .clean-docs.yaml
links:
  timeout: 30  # Default is 10
```

**"Rate limit exceeded" for GitHub**
- Authenticate with `gh auth login`
- Or set `GITHUB_TOKEN` environment variable

**Cache issues**
```bash
# Clear cache
clean-docs cache --clear

# Or use custom location
clean-docs scan . --config ./no-cache-config.yaml
```

### Debug Mode

```bash
# Verbose output
clean-docs scan . --verbose

# Check specific file
clean-docs scan ./problematic.md --verbose

# Dry run to see what's happening
clean-docs scan . --fix --dry-run --verbose
```

### Getting Help

```bash
# General help
clean-docs --help

# Command-specific help
clean-docs scan --help
clean-docs doctor --help
clean-docs cache --help
```

## Best Practices

1. **Run regularly**: Add to CI/CD pipeline
2. **Fix incrementally**: Use `--fix` in interactive mode first
3. **Cache wisely**: Default cache location is fine for most use cases
4. **Ignore wisely**: Use `ignore_patterns` for known exceptions
5. **Version control**: Commit `.clean-docs.yaml` to share settings

## Examples

### Example 1: Fix all internal links

```bash
# Preview
clean-docs scan ./docs --fix --dry-run

# Apply fixes
clean-docs scan ./docs --fix --yes

# Verify
clean-docs scan ./docs
```

### Example 2: Check before release

```bash
# Full check
clean-docs doctor
clean-docs scan . --verbose

# Export results
clean-docs scan . --format json > link-report.json
```

### Example 3: Daily cron job

```bash
#!/bin/bash
# daily-check.sh

cd /path/to/docs
if ! clean-docs scan . --format json > /tmp/daily-check.json; then
  echo "Broken links detected!"
  cat /tmp/daily-check.json | jq '.summary'
  exit 1
fi
```

---

**Next:** Check the [CI/CD Integration guide](guides/ci-cd.md) for automation setup.