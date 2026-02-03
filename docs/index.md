# Clean Docs

**Documentation quality CLI** - Validate code snippets, detect broken links, auto-fix issues, and integrate with CI/CD.

<div class="grid cards" markdown>

-   :material-code-tags-check:{ .lg .middle } **Code Snippet Validation**

    ---

    Validate that code examples in your docs match actual source code using tree-sitter parsing.

    [:octicons-arrow-right-24: Learn more](features/snippet-validation.md)

-   :material-link:{ .lg .middle } **Link Checking**

    ---

    Check internal files, external URLs, GitHub repos, and anchors for broken links.

    [:octicons-arrow-right-24: Learn more](features/link-checking.md)

-   :material-auto-fix:{ .lg .middle } **Auto-fixing**

    ---

    Automatically fix outdated snippets, missing extensions, anchor typos, and case issues.

    [:octicons-arrow-right-24: Learn more](features/auto-fix.md)

-   :material-github:{ .lg .middle } **CI/CD Ready**

    ---

    JSON/Markdown output, GitHub annotations, and proper exit codes for automation.

    [:octicons-arrow-right-24: Learn more](guides/ci-cd.md)

</div>

## Quick Start

### Installation

```bash
# Via pip (recommended)
pip install clean-docs                       # Core features
pip install 'clean-docs[snippets]'           # + Code snippet validation
pip install 'clean-docs[snippets,semantic]'  # All features

# Or via curl installer
curl -fsSL https://raw.githubusercontent.com/Algiras/clean-docs/main/install.sh | bash
```

### Basic Usage

```bash
# Check your setup
clean-docs doctor

# Scan for broken links
clean-docs scan ./docs

# Validate code snippets
clean-docs validate-snippets ./docs --code-dir ./src

# Auto-fix issues
clean-docs scan ./docs --fix --yes
```

## Why Clean Docs?

Documentation quality degrades over time. Code changes but examples don't get updated. Links break. Clean Docs helps you:

- **Catch outdated code examples** before users do
- **Find broken links** across your entire documentation
- **Automate fixes** to reduce manual work
- **Integrate with CI** to prevent regressions

## Supported Languages

For code snippet validation, clean-docs supports:

| Language | Extensions |
|----------|------------|
| Python | `.py` |
| Java | `.java` |
| Scala | `.scala` |
| TypeScript | `.ts`, `.tsx` |
| JavaScript | `.js`, `.jsx` |
| Go | `.go` |
| Rust | `.rs` |
| Bazel | `BUILD`, `BUILD.bazel`, `.bzl` |

## License

MIT License - see [LICENSE](https://github.com/Algiras/clean-docs/blob/main/LICENSE).
