# CI/CD Integration

Integrate clean-docs into your continuous integration pipeline.

## GitHub Actions

### Basic Link Checking

```yaml
name: Docs Check

on:
  push:
    branches: [main]
    paths: ['docs/**', '*.md']
  pull_request:
    paths: ['docs/**', '*.md']

jobs:
  link-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install clean-docs
        run: pip install clean-docs

      - name: Check links
        run: clean-docs scan . --internal-only --github-annotations
```

### With Code Snippet Validation

```yaml
name: Docs Quality

on:
  push:
    branches: [main]
  pull_request:

jobs:
  docs-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install clean-docs
        run: pip install 'clean-docs[snippets]'

      - name: Check links
        run: clean-docs scan . --internal-only

      - name: Validate code snippets
        run: clean-docs validate-snippets ./docs --code-dir ./src

      - name: Report on failure
        if: failure()
        run: |
          echo "## Documentation Issues" >> $GITHUB_STEP_SUMMARY
          clean-docs scan . --format markdown >> $GITHUB_STEP_SUMMARY || true
          clean-docs validate-snippets ./docs --format markdown >> $GITHUB_STEP_SUMMARY || true
```

### Full Pipeline with Caching

```yaml
name: Documentation Quality

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 0 * * 0'  # Weekly full check

jobs:
  quick-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Install
        run: pip install 'clean-docs[snippets]'

      - name: Quick check (internal only)
        run: |
          clean-docs scan . --internal-only --github-annotations
          clean-docs validate-snippets . --code-dir src/

  full-check:
    runs-on: ubuntu-latest
    if: github.event_name == 'schedule' || github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install
        run: pip install 'clean-docs[snippets]'

      - name: Cache HTTP results
        uses: actions/cache@v4
        with:
          path: ~/.cache/clean-docs
          key: clean-docs-cache-${{ github.run_id }}
          restore-keys: clean-docs-cache-

      - name: Full check (including external links)
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: clean-docs scan . --format markdown >> $GITHUB_STEP_SUMMARY
```

## GitLab CI

```yaml
docs-check:
  image: python:3.12
  script:
    - pip install 'clean-docs[snippets]'
    - clean-docs scan . --internal-only
    - clean-docs validate-snippets ./docs --code-dir ./src
  rules:
    - changes:
        - docs/**/*
        - "*.md"
```

## CircleCI

```yaml
version: 2.1

jobs:
  docs-check:
    docker:
      - image: cimg/python:3.12
    steps:
      - checkout
      - run:
          name: Install clean-docs
          command: pip install 'clean-docs[snippets]'
      - run:
          name: Check documentation
          command: |
            clean-docs scan . --internal-only
            clean-docs validate-snippets ./docs --code-dir ./src

workflows:
  check-docs:
    jobs:
      - docs-check
```

## Pre-commit Hook

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: clean-docs-links
        name: Check documentation links
        entry: clean-docs scan . --internal-only
        language: system
        types: [markdown]
        pass_filenames: false

      - id: clean-docs-snippets
        name: Validate code snippets
        entry: clean-docs validate-snippets . --code-dir src/
        language: system
        types: [markdown]
        pass_filenames: false
```

## Exit Codes

Use exit codes to control CI behavior:

| Code | Meaning | CI Behavior |
|------|---------|-------------|
| `0` | All checks pass | Success |
| `1` | Issues found | Failure |

## GitHub Annotations

With `--github-annotations`, issues appear directly in PR diffs:

```bash
clean-docs scan . --github-annotations
```

This creates annotations like:
```
::error file=docs/api.md,line=45::Broken link: ./missing.md
```

## Output Formats

### JSON (for programmatic processing)

```bash
clean-docs scan . --format json > results.json
```

### Markdown (for PR summaries)

```bash
clean-docs scan . --format markdown >> $GITHUB_STEP_SUMMARY
```

## Best Practices

1. **Fast checks on PRs** - Use `--internal-only` for quick feedback
2. **Full checks on main** - Run external checks after merge
3. **Weekly scheduled runs** - Catch external link rot
4. **Cache HTTP results** - Speed up repeated runs
5. **Use GitHub token** - Better rate limits for GitHub links
6. **Fail on broken links** - Don't merge docs with dead links
7. **Warn on outdated snippets** - Surface issues early
