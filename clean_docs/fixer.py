"""Auto-fixer for broken links with iterative fixing support."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from rich.console import Console
from rich.table import Table

from clean_docs.link_checker import LinkResult, LinkStatus, LinkChecker
from clean_docs.parsers.markdown import MarkdownParser


@dataclass
class Fix:
    """Represents a proposed fix."""

    file_path: Path
    line: int
    original_url: str
    suggested_url: str
    description: str
    auto_fixable: bool = False


class LinkFixer:
    """Analyze and propose fixes for broken links."""

    def __init__(self, base_path: Path, console: Console, config=None):
        self.base_path = base_path
        self.console = console
        self.parser = MarkdownParser()
        self.config = config
        self.fixes: List[Fix] = []
        self.max_iterations = 5  # Prevent infinite loops

    async def fix_iteratively(
        self, markdown_files: List[Path], cache, auto_accept: bool = False, dry_run: bool = False
    ) -> Tuple[int, int, int]:
        """Iteratively fix links until no more fixes can be applied.

        Returns: (total_iterations, total_attempted, total_succeeded)
        """
        total_attempted = 0
        total_succeeded = 0
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Re-parse documents (they may have changed)
            documents = []
            for file_path in markdown_files:
                try:
                    doc = self.parser.parse_file(file_path)
                    if doc.links:
                        documents.append(doc)
                except Exception:
                    pass

            if not documents:
                break

            # Check all links
            async with LinkChecker(
                cache=cache,
                timeout=self.config.links.timeout if self.config else 10,
                concurrency=self.config.links.concurrency if self.config else 20,
                ignore_patterns=self.config.links.ignore_patterns if self.config else [],
            ) as checker:
                results = []
                for doc in documents:
                    result = await checker.check_document(doc, self.base_path)
                    results.append(result)

            # Count broken links
            total_broken = sum(r.broken_count for r in results)

            if total_broken == 0:
                self.console.print(
                    f"[green]✓ Iteration {iteration}: No broken links found![/green]"
                )
                break

            # Analyze and propose fixes
            self.fixes = []
            for check_result in results:
                for link_result in check_result.results:
                    if link_result.status == LinkStatus.BROKEN:
                        fix = self._analyze_broken_link(check_result.document, link_result)
                        if fix:
                            self.fixes.append(fix)

            auto_fixable = [f for f in self.fixes if f.auto_fixable]

            if not auto_fixable:
                self.console.print(
                    f"[yellow]Iteration {iteration}: {total_broken} broken links, but none are auto-fixable[/yellow]"
                )
                break

            self.console.print(
                f"\n[cyan]Iteration {iteration}:[/cyan] Found {total_broken} broken links, {len(auto_fixable)} auto-fixable"
            )

            if dry_run:
                self.print_fixes()
                break

            # Show fixes for this iteration
            self.print_fixes()

            # Check if user wants to continue (unless auto_accept)
            if not auto_accept:
                if not self.prompt_user(f"Apply these {len(auto_fixable)} fixes?"):
                    self.console.print("[yellow]Stopping fix loop.[/yellow]")
                    break

            # Apply fixes
            attempted, succeeded = self.apply_fixes(dry_run=False)
            total_attempted += attempted
            total_succeeded += succeeded

            self.console.print(
                f"[green]Applied {succeeded}/{attempted} fixes in iteration {iteration}[/green]"
            )

            # If no fixes succeeded, we're done
            if succeeded == 0:
                break

        return iteration, total_attempted, total_succeeded

    def _analyze_broken_link(self, doc, link_result: LinkResult) -> Optional[Fix]:
        """Analyze a single broken link and propose a fix."""
        link = link_result.link
        url = link.url

        # Handle missing .md extension
        if not url.startswith("http") and not url.startswith("#"):
            if not url.endswith(".md") and not url.endswith(".mdx"):
                # Check if adding .md would fix it
                md_url = url + ".md"
                if self._resolve_path(doc.path, md_url).exists():
                    return Fix(
                        file_path=doc.path,
                        line=link.line,
                        original_url=url,
                        suggested_url=md_url,
                        description="Add .md extension",
                        auto_fixable=True,
                    )

        # Handle anchor suggestions - ONLY auto-fix safe transformations
        if link_result.suggestion and "Did you mean" in link_result.suggestion:
            # Extract suggested anchor from the hint
            match = re.search(r"Did you mean #([^?]+)\?", link_result.suggestion)
            if match:
                suggested_anchor = match.group(1)
                original_anchor = url.split("#")[1] if "#" in url else url.lstrip("#")

                # Only auto-fix if it's a safe transformation
                if self._is_safe_anchor_fix(original_anchor, suggested_anchor):
                    if "#" in url:
                        base_url = url.split("#")[0]
                        new_url = f"{base_url}#{suggested_anchor}"
                    else:
                        new_url = f"#{suggested_anchor}"

                    return Fix(
                        file_path=doc.path,
                        line=link.line,
                        original_url=url,
                        suggested_url=new_url,
                        description=f"Fix anchor: #{original_anchor} → #{suggested_anchor}",
                        auto_fixable=True,
                    )
                else:
                    # Not safe to auto-fix - mark for manual review
                    return Fix(
                        file_path=doc.path,
                        line=link.line,
                        original_url=url,
                        suggested_url=f"#{suggested_anchor}",
                        description=f"Anchor not found (suggestion: #{suggested_anchor}) - needs manual review",
                        auto_fixable=False,
                    )

        # Try case-insensitive match for internal files
        if not url.startswith("http") and not url.startswith("#"):
            resolved = self._resolve_path(doc.path, url)
            if not resolved.exists():
                # Try case-insensitive search in same directory
                search_dir = resolved.parent if resolved.parent.exists() else doc.path.parent
                target_name = resolved.name.lower()

                try:
                    for file in search_dir.iterdir():
                        if file.is_file() and file.name.lower() == target_name:
                            # Calculate relative path
                            rel_path = self._make_relative(doc.path.parent, file)
                            return Fix(
                                file_path=doc.path,
                                line=link.line,
                                original_url=url,
                                suggested_url=rel_path,
                                description=f"Fix case: {resolved.name} → {file.name}",
                                auto_fixable=True,
                            )
                except (PermissionError, OSError):
                    pass

        # External/GitHub links need manual review
        if url.startswith("http"):
            return Fix(
                file_path=doc.path,
                line=link.line,
                original_url=url,
                suggested_url=url,
                description=f"External link broken - needs manual review: {link_result.error_message}",
                auto_fixable=False,
            )

        return None

    def _is_safe_anchor_fix(self, original: str, suggested: str) -> bool:
        """Check if an anchor fix is safe to auto-apply.

        Safe fixes are:
        1. Case changes only: #Context -> #context
        2. Double hyphen to single: #foo--bar -> #foo-bar
        3. Trailing/leading hyphen removal: #-foo- -> #foo
        4. The normalized forms are identical
        """

        # Normalize both anchors for comparison
        def normalize(s: str) -> str:
            s = s.lower()
            # Collapse multiple hyphens
            s = re.sub(r"-+", "-", s)
            # Remove leading/trailing hyphens
            s = s.strip("-")
            return s

        orig_norm = normalize(original)
        sugg_norm = normalize(suggested)

        # If normalized versions are identical, it's safe
        if orig_norm == sugg_norm:
            return True

        # Check if it's just case difference (without normalization)
        if original.lower() == suggested.lower():
            return True

        # Check if it's just hyphen normalization
        orig_dehyphen = original.lower().replace("-", "")
        sugg_dehyphen = suggested.lower().replace("-", "")
        if orig_dehyphen == sugg_dehyphen:
            return True

        # Otherwise, not safe - the anchors are semantically different
        return False

    def _resolve_path(self, doc_path: Path, url: str) -> Path:
        """Resolve a URL to an absolute path."""
        if url.startswith("/"):
            return (self.base_path / url.lstrip("/")).resolve()
        else:
            return (doc_path.parent / url).resolve()

    def _make_relative(self, from_dir: Path, to_file: Path) -> str:
        """Make a relative path from one directory to a file."""
        try:
            rel = to_file.relative_to(from_dir)
            return f"./{rel}" if not str(rel).startswith(".") else str(rel)
        except ValueError:
            # Files are on different drives or can't be relativized
            return str(to_file)

    def print_fixes(self) -> None:
        """Print proposed fixes to console."""
        if not self.fixes:
            self.console.print("[green]No auto-fixable issues found![/green]")
            return

        auto_fixable = [f for f in self.fixes if f.auto_fixable]
        manual_review = [f for f in self.fixes if not f.auto_fixable]

        if auto_fixable:
            table = Table(show_header=True, header_style="bold green")
            table.add_column("File", style="cyan")
            table.add_column("Line", style="dim", justify="right")
            table.add_column("Change", style="white")
            table.add_column("Description", style="green")

            for fix in auto_fixable:
                change = f"{fix.original_url} → {fix.suggested_url}"
                table.add_row(str(fix.file_path), str(fix.line), change, fix.description)

            self.console.print("\n[bold green]Proposed fixes:[/bold green]")
            self.console.print(table)

        if manual_review:
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("File", style="cyan")
            table.add_column("Line", style="dim", justify="right")
            table.add_column("URL", style="white")
            table.add_column("Issue", style="yellow")

            for fix in manual_review:
                table.add_row(str(fix.file_path), str(fix.line), fix.original_url, fix.description)

            self.console.print("\n[bold yellow]Needs manual review:[/bold yellow]")
            self.console.print(table)

    def apply_fixes(self, dry_run: bool = False) -> Tuple[int, int]:
        """Apply all auto-fixable fixes. Returns (attempted, succeeded)."""
        auto_fixable = [f for f in self.fixes if f.auto_fixable]

        if not auto_fixable:
            return 0, 0

        attempted = 0
        succeeded = 0

        for fix in auto_fixable:
            attempted += 1
            if dry_run:
                succeeded += 1
                continue

            try:
                if self._apply_single_fix(fix):
                    succeeded += 1
            except Exception:
                pass

        return attempted, succeeded

    def _apply_single_fix(self, fix: Fix) -> bool:
        """Apply a single fix to a file."""
        content = fix.file_path.read_text(encoding="utf-8")
        lines = content.split("\n")

        if fix.line < 1 or fix.line > len(lines):
            return False

        line_idx = fix.line - 1
        original_line = lines[line_idx]

        # Replace the URL in the line
        fixed_line = original_line.replace(fix.original_url, fix.suggested_url, 1)

        if fixed_line == original_line:
            # Try regex replacement for markdown links
            pattern = re.escape(fix.original_url)
            fixed_line = re.sub(pattern, fix.suggested_url, original_line, count=1)

        if fixed_line != original_line:
            lines[line_idx] = fixed_line
            fix.file_path.write_text("\n".join(lines), encoding="utf-8")
            return True

        return False

    def prompt_user(self, message: str = "Apply these fixes?") -> bool:
        """Prompt user to confirm fixes. Returns True if user accepts."""
        self.console.print(f"\n[cyan]{message}[/cyan]")
        self.console.print("[dim]Type 'yes' to apply, 'no' to cancel:[/dim]")

        try:
            response = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[yellow]Cancelled.[/yellow]")
            return False

        if response in ("yes", "y"):
            return True
        else:
            self.console.print("[yellow]Cancelled.[/yellow]")
            return False
