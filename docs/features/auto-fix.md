# Auto-Fix

Automatically repair common documentation issues.

## What Can Be Fixed

| Issue Type | Example | Auto-Fix |
|------------|---------|----------|
| Outdated code snippets | Old API usage | Updates to match source |
| Missing file extension | `./guide` | `./guide.md` |
| Case sensitivity | `./Guide.MD` | `./guide.md` |
| Anchor normalization | `#My-Section` | `#my-section` |

## What Requires Manual Review

- External 404 errors (site may be down or moved)
- Deleted files with no obvious redirect
- Semantic anchor changes (section renamed)
- Code snippets with no source match

## Usage

### Preview Mode (Recommended First)

Always preview changes before applying:

```bash
# Preview link fixes
clean-docs scan ./docs --fix --dry-run

# Preview snippet fixes
clean-docs validate-snippets ./docs --fix --dry-run
```

### Interactive Mode

Prompts for confirmation on each fix:

```bash
clean-docs scan ./docs --fix
```

Output:
```
Found fixable issue in docs/api.md:45
  Current: ./endpoints
  Suggested: ./endpoints.md

Apply this fix? [y/n/a(ll)/q(uit)]:
```

### Automatic Mode

Apply all fixes without prompting:

```bash
clean-docs scan ./docs --fix --yes
```

## Snippet Fixing

When code snippets are outdated, clean-docs can update them:

```bash
# Preview what would change
clean-docs validate-snippets ./docs --fix --dry-run
```

Example output:
```
Would fix README.md:45 (python)
  Current:
    def add(a, b):
        return a + b  # old implementation

  Updated:
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b
```

The fix preserves:

- Fence markers (` ``` `)
- Language annotations
- Surrounding content
- Original indentation style

## CODEOWNERS Integration

For monorepos, create separate PRs per team:

```bash
# View who owns which files
clean-docs owners ./docs/api.md

# Scan grouped by owner
clean-docs scan . --group-by-owner

# Create PRs per team
clean-docs fix-prs . --codeowners CODEOWNERS

# Only for specific team
clean-docs fix-prs . --only-owner @myteam/docs
```

## Best Practices

1. **Always dry-run first** - Review changes before applying
2. **Commit before fixing** - So you can easily revert
3. **Review diffs** - Automated fixes aren't always perfect
4. **Run tests after** - Ensure fixes didn't break anything
5. **Use CI preview** - Show what would be fixed in PRs

## CI Integration

Add a step to show fixable issues without failing:

```yaml
- name: Check for fixable issues
  run: |
    clean-docs scan . --fix --dry-run || true
    clean-docs validate-snippets . --fix --dry-run || true
```
