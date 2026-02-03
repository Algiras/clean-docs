# Link Checking

Scan your documentation for broken links of all types.

## Supported Link Types

| Type | Example | Description |
|------|---------|-------------|
| Internal | `./file.md`, `../docs/guide.md` | Relative file paths |
| Anchors | `#section`, `./file.md#anchor` | Section links within pages |
| External | `https://example.com` | HTTP/HTTPS URLs |
| GitHub | `github.com/user/repo/blob/main/file.md` | GitHub file and directory links |

## Basic Usage

```bash
# Scan all markdown files in a directory
clean-docs scan ./docs

# Scan a single file
clean-docs scan README.md

# Fast mode - internal links only (no HTTP requests)
clean-docs scan ./docs --internal-only
```

## Options

### Performance

```bash
# Adjust HTTP timeout (default: 10s)
clean-docs scan ./docs --timeout 30

# Set retry count for failed requests (default: 2)
clean-docs scan ./docs --retry 3

# Limit concurrent requests (default: 20)
clean-docs scan ./docs --concurrency 10

# Stop on first error
clean-docs scan ./docs --fail-fast
```

### Filtering

```bash
# Ignore certain patterns
clean-docs scan ./docs --ignore "localhost" --ignore "127.0.0.1"

# Exclude files
clean-docs scan ./docs --exclude "archive/*" --exclude "*.draft.md"
```

### Output

```bash
# Verbose mode - show all links, not just broken ones
clean-docs scan ./docs --verbose

# JSON output
clean-docs scan ./docs --format json

# Markdown report
clean-docs scan ./docs --format markdown --output report.md

# GitHub Actions annotations
clean-docs scan ./docs --github-annotations
```

## Smart Caching

Clean Docs caches HTTP request results to speed up subsequent runs:

- **24-hour TTL** by default (configurable)
- **SQLite-based** for reliability
- **Batch operations** for efficiency

```bash
# View cache statistics
clean-docs cache --stats

# Show cached broken links
clean-docs cache --broken

# Clear expired entries
clean-docs cache --cleanup

# Clear all cache
clean-docs cache --clear
```

## GitHub Link Checking

Clean Docs has special handling for GitHub links:

- Uses GitHub CLI (`gh`) when available for authenticated requests
- Falls back to `GITHUB_TOKEN` environment variable
- Handles rate limiting gracefully
- Validates file existence in repositories

```bash
# Ensure gh is authenticated for better rate limits
gh auth login

# Or set token directly
export GITHUB_TOKEN=ghp_xxxxx
clean-docs scan ./docs
```

## Configuration File

Create `.clean-docs.yaml` for persistent configuration:

```yaml
links:
  timeout: 10
  concurrency: 20
  retries: 2
  ignore_patterns:
    - "localhost"
    - "127.0.0.1"
    - "example.com"
    - "*.internal.company.com"

cache:
  ttl_hours: 24
  directory: ~/.cache/clean-docs
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | All links valid |
| `1` | Broken links found |

## Example Output

```
╭───────────────── Link Check ─────────────────╮
│ Scanning: ./docs                             │
│ Files: 24                                    │
│ Links: 156                                   │
╰──────────────────────────────────────────────╯

Checking links...

✗ docs/api.md:45
  Link: ./endpoints.md
  Error: File not found

✗ docs/guide.md:112
  Link: https://old-domain.com/docs
  Error: 404 Not Found

✗ README.md:23
  Link: #instalation
  Error: Anchor not found (did you mean #installation?)

Summary:
  Total links: 156
  Valid: 153
  Broken: 3
```
