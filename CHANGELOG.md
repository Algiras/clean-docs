# Changelog

## 0.1.0 (2024-02-02)

### MVP Release

**Features:**
- **Link Checking**: Validate internal file links, external HTTP/HTTPS URLs, and GitHub repository links
- **Smart Caching**: SQLite-based cache with TTL to avoid redundant checks
- **GitHub Integration**: Uses `gh` CLI when available, falls back to GITHUB_TOKEN
- **Anchor Validation**: Check that internal anchors (#section) exist in target documents
- **Rich CLI**: Beautiful progress bars, color-coded output, and detailed reports
- **Multiple Output Formats**: Console (human-readable) and JSON (CI/CD friendly)
- **Doctor Command**: Check prerequisites (Python version, GitHub CLI, cache permissions)
- **Configuration**: YAML-based configuration with sensible defaults

**Commands:**
- `clean-docs doctor` - Check prerequisites
- `clean-docs scan <path>` - Scan for broken links
- `clean-docs cache --stats` - View cache statistics
- `clean-docs cache --clear` - Clear the cache

**Link Types Supported:**
- Internal relative links: `./file.md`, `../file.md`
- Internal absolute links: `/docs/file.md`
- External HTTP/HTTPS: `https://example.com`
- GitHub links: `https://github.com/owner/repo`
- Anchor links: `#section-heading`
- Reference-style links: `[text][ref]` with `[ref]: url`
