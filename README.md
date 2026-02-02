# Clean Docs

> CLI tool for cleaning up documentation repositories - detect broken links, find orphaned docs, and keep your docs in sync with your code.

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

<p align="center">
  <img src="demo.gif" alt="clean-docs demo" width="700">
</p>

## 🎯 What is Clean Docs?

Clean Docs is a documentation maintenance tool that automatically finds and fixes common documentation issues:

- 🔗 **Broken links** (internal, external, GitHub repos)
- 📊 **Stale documentation** (outdated docs vs fresh code)
- 💡 **Missing README sections** (Installation, Usage, Contributing)
- 🧪 **Invalid code examples** (syntax errors in documentation)
- 📦 **Outdated dependencies** (security & maintenance issues)

## 🚀 Quick Start

```bash
# One-line install
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# Check your setup
clean-docs doctor

# Scan your docs
clean-docs scan ./docs

# Fix issues automatically
clean-docs scan ./docs --fix --yes
```

## 📊 How It Works

### Before vs After

```
BEFORE: Documentation Chaos
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ docs/api.md → 404 errors on 12 links
❌ README.md → Missing quickstart section  
❌ ./guide.md → Links to deleted file
❌ examples/ → Code doesn't compile
❌ Last updated: 8 months ago
❌ No CI checks

Running: clean-docs scan . --fix

AFTER: Documentation Excellence
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ docs/api.md → All 15 links working
✅ README.md → Complete with badges
✅ ./guide.md → Fixed broken links
✅ examples/ → All code validated
✅ Freshness tracking enabled
✅ CI/CD automated checks
```

### The Clean Docs Workflow

```
┌─────────────────────────────────────────────────────────────┐
│  YOUR DOCUMENTATION REPOSITORY                               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  1. SCAN                                                    │
│     clean-docs scan .                                       │
│                                                             │
│     → Parse all markdown files                              │
│     → Extract links, anchors, code examples                 │
│     → Check internal files exist                            │
│     → Validate external URLs (with caching)                 │
│     → Verify GitHub repos/branches                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  2. ANALYZE                                                 │
│                                                             │
│     Broken Links Found:                                     │
│     ❌ docs/api.md:47 → ./deprecated.md (file deleted)      │
│     ❌ README.md:23 → https://broken-url.com (404)          │
│     ❌ guide.md:89 → #old-section (anchor renamed)          │
│                                                             │
│     Auto-fixable:                                           │
│     💡 ./deprecated → ./new-location.md                     │
│     💡 #old-section → #new-section                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  3. FIX (Interactive or Automatic)                          │
│     clean-docs scan . --fix --yes                           │
│                                                             │
│     Iteration 1:                                            │
│     ✅ Fixed: docs/api.md:47 → ./new-location.md            │
│     ✅ Fixed: guide.md:89 → #new-section                    │
│                                                             │
│     Iteration 2: (Re-check)                                 │
│     ✅ All internal links working                           │
│                                                             │
│     Manual review needed:                                   │
│     ⚠️  README.md:23 → External 404 (manual fix)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  4. REPORT                                                  │
│                                                             │
│     Summary:                                                │
│     ┌──────────────────────────┬──────────┐                │
│     │ Files Checked            │ 23       │                │
│     │ Total Links              │ 156      │                │
│     │ Working                  │ 152 ✅   │                │
│     │ Broken (manual fix)      │ 4 ⚠️     │                │
│     └──────────────────────────┴──────────┘                │
│                                                             │
│     Score: 97% (Excellent!)                                 │
└─────────────────────────────────────────────────────────────┘
```

## 🎬 Demo Video

### Scenario: Cleaning Up a Real Project

```bash
# 1. First time setup
$ clean-docs init --wizard

╔══════════════════════════════════════════════════════════════╗
║     Clean Docs Initialization Wizard                         ║
╚══════════════════════════════════════════════════════════════╝

Step 1: Choose a template
┌────┬────────────────┬──────────────────────────────┐
│ #  │ Template       │ Description                  │
├────┼────────────────┼──────────────────────────────┤
│ 1  │ minimal        │ Essential files only         │
│ 2  │ full           │ Complete setup [default]     │
│ 3  │ python-lib     │ Python library with Sphinx   │
│ 4  │ js-package     │ JavaScript/TypeScript pkg    │
└────┴────────────────┴──────────────────────────────┘
Select template: 2

Step 2: Project type
┌────┬──────────────────────┐
│ #  │ Type                 │
├────┼──────────────────────┤
│ 1  │ Python library       │
│ 2  │ JavaScript package   │
│ 3  │ Documentation site   │
│ 4  │ Monorepo             │
└────┴──────────────────────┘
Select type: 1

[... 7 more steps ...]

✓ Created .clean-docs.yaml
✓ Created docs/README.md
✓ Created .github/workflows/docs-quality.yml
✓ Updated .gitignore

Next Steps:
1. Review .clean-docs.yaml
2. Run 'clean-docs doctor'
3. Run 'clean-docs scan .'
```

### Real-World Usage

```bash
# Check what's broken
$ clean-docs scan ./docs

╭──────────────────────────────────╮
│ Clean Docs Scan                  │
│ Files: 15                        │
│ Base: ./docs                     │
╰──────────────────────────────────╯

Checking README.md...
Checking api.md...
Checking guide.md...

Summary:
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Count ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Files Checked │ 15    │
│ Total Links   │ 127   │
│ Working       │ 119 ✅│
│ Broken        │ 8 ❌  │
└───────────────┴───────┘

✗ docs/api.md
  Line 47: [Config Guide](./config.md)
    Error: File not found: ./config.md
    Hint: Did you mean ./configuration.md?
  
  Line 89: [Authentication](#auth-section)
    Error: Anchor #auth-section not found
    Hint: Did you mean #authentication?

✗ README.md
  Line 23: https://broken-example.com
    Error: HTTP 404

# Dry run to preview fixes
$ clean-docs scan ./docs --fix --dry-run

╭────────────────────────────────╮
│ Dry Run Mode - Preview         │
╰────────────────────────────────╯

Iteration 1: 8 broken links, 6 auto-fixable

Proposed fixes:
┏━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ File         ┃ Line ┃ Change                         ┃ Description  ┃
┡━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ docs/api.md  │ 47   │ ./config.md → ./configuration.md│ Fix filename │
│ docs/api.md  │ 89   │ #auth-section → #authentication │ Fix anchor   │
│ ...          │ ...  │ ...                            │ ...          │
└──────────────┴──────┴────────────────────────────────┴──────────────┘

Would apply 6 fixes in 1 iteration

# Apply fixes automatically
$ clean-docs scan ./docs --fix --yes

Starting iterative fix loop...

Iteration 1: Found 8 broken links, 6 auto-fixable
✓ Fixed: docs/api.md:47
✓ Fixed: docs/api.md:89
✓ Fixed: docs/guide.md:12
...
Applied 6/6 fixes

Iteration 2: Re-checking...
✓ No broken links found!

Fix loop complete:
  Iterations: 2
  Total fixes: 6/6

Summary:
┏━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Metric        ┃ Count ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Files Checked │ 15    │
│ Total Links   │ 127   │
│ Working       │ 125 ✅│
│ Broken        │ 2 ⚠️  │
└───────────────┴───────┘

Note: 2 external links still broken (require manual fix)
```

## 📦 Installation

### One-Line Install (Recommended)

```bash
# Quick install
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# With semantic analysis support
WITH_SEMANTIC=1 curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash
```

### Pip Install

```bash
# Basic install (link checking only)
pip install clean-docs

# With all features
pip install clean-docs[semantic]
```

## 🎯 Features

### Core Features (Always Available)

| Feature | What It Does | Example |
|---------|--------------|---------|
| **Link Checking** | Validates all link types | Internal, external, GitHub, anchors |
| **Iterative Fixing** | Auto-fixes in loop until done | Missing `.md`, anchor typos, case issues |
| **Smart Caching** | Caches results for 24h | Skip re-checking working links |
| **GitHub Integration** | Checks repo/branch/file existence | `github.com/user/repo/blob/main/file.md` |
| **CI/CD Ready** | JSON output, exit codes | Perfect for GitHub Actions |

### Link Types Supported

```
Internal Links          External Links           GitHub Links
─────────────────       ─────────────────        ─────────────────
./file.md               https://example.com      github.com/user/repo
../docs/guide.md        http://api.site.com      github.com/user/repo/tree/branch
/guide.md (absolute)    https://bit.ly/xxx       github.com/user/repo/blob/branch/path
#section-anchor         ftp://... (skipped)      github.com/user/repo/issues/123
[ref][link]            mailto:... (skipped)
```

### Fixing Capabilities

```
✅ AUTO-FIXABLE (No human needed)
   • ./file → ./file.md (missing extension)
   • #secton → #section (anchor typo)
   • ./File.md → ./file.md (case sensitivity)
   
⚠️  MANUAL REVIEW NEEDED
   • External URL returns 404
   • GitHub repo doesn't exist
   • File deleted with no redirect
```

## 🏃 Usage

### 1. Doctor - Check Your Setup

```bash
# Check required dependencies
clean-docs doctor

# Check everything including optional features
clean-docs doctor --all
```

```
╭──────────── Doctor Report ─────────────╮
│ All checks passed! ✅                   │
╰─────────────────────────────────────────╯

┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check                    ┃ Status  ┃ Details                        ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Python Version           │ ✅ Pass │ Python 3.12.1                  │
│ GitHub CLI               │ ✅ Pass │ gh version 2.40.0              │
│ GITHUB_TOKEN             │ ✅ Pass │ Set                            │
│ Cache Directory          │ ✅ Pass │ /tmp/clean-docs-cache          │
│ Semantic Analysis (Opt)  │ ✅ Pass │ sentence-transformers v2.3.1   │
│ Copilot CLI (Opt)        │ ✅ Pass │ Available                      │
└──────────────────────────┴─────────┴────────────────────────────────┘
```

### 2. Scan - Find Issues

```bash
# Basic scan
clean-docs scan ./docs

# With all options
clean-docs scan ./docs \
  --verbose \              # Show all links
  --format json \          # JSON output
  --config ./custom.yaml   # Custom config

# Performance options
clean-docs scan ./docs \
  --internal-only \        # Skip external links (fast mode)
  --timeout 30 \           # Custom timeout
  --retry 3 \              # Retry flaky links
  --fail-fast              # Stop on first error

# CI/CD integration
clean-docs scan ./docs \
  --format markdown \      # Markdown report
  --output report.md \     # Write to file
  --github-annotations     # GitHub Actions annotations
```

### 3. Fix - Repair Issues

```bash
# Preview what would be fixed
clean-docs scan ./docs --fix --dry-run

# Interactive mode (prompts for confirmation)
clean-docs scan ./docs --fix

# Auto-fix everything
clean-docs scan ./docs --fix --yes
```

### 4. Init - Setup New Project

```bash
# Interactive wizard (9 steps)
clean-docs init --wizard

# Quick mode - just config file
clean-docs init --quick

# Specific template
clean-docs init --template python-lib
```

### 5. Fix PRs - Create PRs by CODEOWNERS (Monorepo)

For large repositories with CODEOWNERS, create separate PRs for each team:

```bash
# Preview what PRs would be created
clean-docs fix-prs . --codeowners CODEOWNERS --dry-run

# Create PRs for all owner groups
clean-docs fix-prs . --codeowners CODEOWNERS

# Only fix for a specific team
clean-docs fix-prs . --only-owner @myteam/docs

# Skip certain owners
clean-docs fix-prs . --skip-owner @bot-account
```

**Features:**
- Groups broken links by CODEOWNERS teams
- Creates separate branches and PRs per team
- Auto-detects base branch (main/master)
- Adds team members as reviewers
- Only applies safe, conservative fixes

### 6. Owners - Check File Ownership

```bash
# Check who owns a file
clean-docs owners ./docs/api.md

# Check ownership in a directory
clean-docs owners ./framework/
```

**Wizard creates:**
- `.clean-docs.yaml` (configuration)
- `docs/` structure (if requested)
- `.github/workflows/` (CI/CD)
- `.pre-commit-config.yaml` (git hooks)
- `README.md` template

## ⚙️ Configuration

### `.clean-docs.yaml` Example

```yaml
links:
  timeout: 10                    # HTTP timeout (seconds)
  concurrency: 20                # Parallel checks
  ignore_patterns:               # Skip these URLs
    - "localhost"
    - "127.0.0.1"
    - "example.com"
    - "*.local"

cache:
  ttl_hours: 24                  # Cache expiration
  max_size_mb: 100              # Max cache size
  # dir: ~/.cache/clean-docs    # Custom location

output:
  show_progress: true           # Progress bars
  colors: auto                  # auto/always/never
```

## 🔄 CI/CD Integration

### GitHub Actions

```yaml
name: Documentation Quality

on: [push, pull_request]

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install clean-docs
        run: pip install clean-docs
      
      - name: Check Documentation Links
        run: |
          # With GitHub annotations (shows errors inline in PR)
          clean-docs scan . --github-annotations --internal-only
      
      - name: Generate Report
        if: failure()
        run: |
          clean-docs scan . --format markdown --output report.md --internal-only || true
          cat report.md >> $GITHUB_STEP_SUMMARY
```

### Advanced CI Example (with CODEOWNERS)

```yaml
name: Docs Link Check by Owner

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday
  workflow_dispatch:

jobs:
  check-and-fix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Check by CODEOWNERS
        run: |
          pip install clean-docs
          clean-docs scan . --group-by-owner --format markdown
      
      - name: Create Fix PRs (dry-run)
        run: |
          clean-docs fix-prs . --dry-run
```

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All checks passed |
| `1` | Issues found (broken links, etc.) |

## 🧠 Advanced Features (Optional)

### Semantic Analysis

When installed with `pip install clean-docs[semantic]`:

```bash
# Find docs without related code
clean-docs semantic --orphaned ./docs

# Find code without docs
clean-docs semantic --missing-docs ./src
```

## 🗂️ Cache Location

By default, cache is stored in **system temp directory**:

- **Linux/macOS**: `/tmp/clean-docs-cache/` or `/var/folders/.../T/clean-docs-cache/`
- **Windows**: `%TEMP%\clean-docs-cache\`

**Why temp?**
- Auto-cleaned by OS
- No pollution of project dirs
- Works across projects
- Can customize in config

## 🐛 Troubleshooting

### Common Issues

**"clean-docs: command not found"**
```bash
# Add to PATH
export PATH="$HOME/.local/bin:$PATH"
# Or reinstall
pip install --force-reinstall clean-docs
```

**"Cannot connect to host"**
```yaml
# In .clean-docs.yaml
links:
  timeout: 30  # Increase from default 10s
```

**Rate limits on GitHub**
```bash
# Authenticate
gh auth login
# Or set token
export GITHUB_TOKEN=your_token
```

## 📊 Success Metrics

After using Clean Docs, you should see:

```
Before:                  After:
━━━━━━━━━━━━━━━━         ━━━━━━━━━━━━━━━━
156 links                156 links
23 broken ❌             0 broken ✅
0% automated             95% automated
No tracking              Full tracking
No CI                    CI integrated

Time to check: 5min     Time to check: 10sec
Time to fix: 2hrs       Time to fix: 0 (auto)
```

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🎉 Get Started Now

```bash
# Install
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash

# Setup
clean-docs init --wizard

# Check
clean-docs doctor

# Clean
clean-docs scan . --fix --yes

# Celebrate! 🎊
```

---

**Clean docs = Happy developers** 🧹✨
