"""Main CLI for Clean Docs."""

import asyncio
import fnmatch
import json
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, MofNCompleteColumn
from rich.table import Table
from rich.text import Text

from clean_docs import __version__
from clean_docs.cache import CacheManager
from clean_docs.config import Config, DEFAULT_CONFIG_CONTENT
from clean_docs.doctor import Doctor
from clean_docs.fixer import LinkFixer
from clean_docs.init_wizard import InitWizard
from clean_docs.link_checker import LinkChecker, LinkResult, LinkStatus
from clean_docs.parsers.markdown import MarkdownParser
from clean_docs.semantic import EmbeddingManager, SemanticAnalyzer, SEMANTIC_AVAILABLE
from clean_docs.codeowners import CodeOwners
from clean_docs.pr_pipeline import PRPipeline


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        console.print(f"clean-docs version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="clean-docs",
    help="Clean up documentation - check links, validate examples, maintain quality",
    rich_markup_mode="rich",
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main(
    version: bool = typer.Option(
        False, 
        "--version", 
        "-v", 
        callback=version_callback, 
        is_eager=True,
        help="Show version and exit."
    ),
):
    """Clean Docs - Documentation maintenance tool."""
    pass


class OutputFormat(str, Enum):
    CONSOLE = "console"
    JSON = "json"
    MARKDOWN = "markdown"


def _filter_files_by_exclude(files: List[Path], exclude_patterns: List[str], base_path: Path) -> List[Path]:
    """Filter files based on exclude glob patterns."""
    if not exclude_patterns:
        return files
    
    filtered = []
    for f in files:
        try:
            rel_path = str(f.relative_to(base_path))
        except ValueError:
            rel_path = str(f)
        
        excluded = False
        for pattern in exclude_patterns:
            # Support both glob-style and simple patterns
            if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(f.name, pattern):
                excluded = True
                break
            # Also check if pattern matches any parent directory
            if '**' in pattern:
                # Convert ** pattern to work with fnmatch
                simple_pattern = pattern.replace('**/', '').replace('/**', '')
                if simple_pattern in rel_path:
                    excluded = True
                    break
        
        if not excluded:
            filtered.append(f)
    
    return filtered


@app.command()
def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    all: bool = typer.Option(False, "--all", "-a", help="Also check optional features (semantic, copilot)"),
):
    """Check prerequisites for Clean Docs."""
    doc = Doctor(console)
    all_passed = doc.run_all_checks(check_optional=all)
    doc.print_report()
    
    if not all_passed:
        raise typer.Exit(code=1)


@app.command()
def init(
    path: Path = typer.Option(Path("."), "--path", "-p", help="Project path"),
    use_wizard: bool = typer.Option(True, "--wizard/--quick", "-w/-q", help="Use interactive wizard or quick mode"),
    template: str = typer.Option("full", "--template", "-t", help="Template to use (minimal, full, python-lib, js-package)"),
):
    """Initialize Clean Docs for a project with interactive wizard."""
    target_path = path.resolve()
    
    if use_wizard:
        # Use interactive wizard
        init_wizard = InitWizard(console, target_path)
        success = init_wizard.run()
        
        if not success:
            raise typer.Exit(code=1)
    else:
        # Quick mode - just create basic config
        config_path = target_path / ".clean-docs.yaml"
        
        if config_path.exists():
            console.print(f"[yellow]Config already exists: {config_path}[/yellow]")
            raise typer.Exit(code=1)
        
        config = Config()
        config.save(config_path)
        console.print(f"[green]Created config: {config_path}[/green]")
        console.print("[dim]Run 'clean-docs init --wizard' for full setup[/dim]")


@app.command()
def scan(
    path: Path = typer.Argument(..., help="Path to documentation directory or file", exists=True),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
    fix: bool = typer.Option(False, "--fix", help="Propose and apply fixes for broken links"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be fixed without making changes"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-accept all proposed fixes (use with --fix)"),
    format: OutputFormat = typer.Option(OutputFormat.CONSOLE, "--format", "-f", help="Output format (console, json, markdown)"),
    init: bool = typer.Option(False, "--init", help="Create default config file and exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    internal_only: bool = typer.Option(False, "--internal-only", "-i", help="Only check internal links (skip http/https)"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Glob patterns to exclude (can be used multiple times)"),
    group_by_owner: bool = typer.Option(False, "--group-by-owner", "-g", help="Group results by CODEOWNERS (for creating separate PRs)"),
    codeowners_path: Optional[Path] = typer.Option(None, "--codeowners", help="Path to CODEOWNERS file (auto-detected if not specified)"),
    retry: int = typer.Option(2, "--retry", "-r", help="Number of retries for flaky external links"),
    timeout: Optional[int] = typer.Option(None, "--timeout", "-t", help="HTTP timeout in seconds (overrides config)"),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop on first broken link found"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Write results to file instead of stdout"),
    github_annotations: bool = typer.Option(False, "--github-annotations", help="Output GitHub Actions annotations for CI"),
):
    """Scan documentation for broken links and issues."""
    
    # Initialize config if requested
    if init:
        config_file = path / ".clean-docs.yaml" if path.is_dir() else path.parent / ".clean-docs.yaml"
        if config_file.exists():
            console.print(f"[yellow]Config file already exists: {config_file}[/yellow]")
            raise typer.Exit(code=1)
        
        config_file.write_text(DEFAULT_CONFIG_CONTENT)
        console.print(f"[green]Created config file: {config_file}[/green]")
        console.print("[dim]Edit it to customize Clean Docs behavior[/dim]")
        return
    
    # Load configuration
    config = Config.load(config_path)
    
    # Initialize cache
    cache = CacheManager(config.get_cache_dir(), config.cache.ttl_hours)
    
    # Build ignore patterns - add http/https if internal_only mode
    ignore_patterns = list(config.links.ignore_patterns)
    if internal_only:
        ignore_patterns.extend(["http://", "https://"])
    
    # Find markdown files
    parser = MarkdownParser()
    
    if path.is_file():
        markdown_files = [path]
        base_path = path.parent
    else:
        markdown_files = parser.find_all_markdown_files(path)
        base_path = path
    
    # Apply exclude patterns
    if exclude:
        original_count = len(markdown_files)
        markdown_files = _filter_files_by_exclude(markdown_files, list(exclude), base_path)
        if verbose and original_count != len(markdown_files):
            console.print(f"[dim]Excluded {original_count - len(markdown_files)} files based on patterns[/dim]")
    
    # Load CODEOWNERS if grouping by owner
    codeowners: Optional[CodeOwners] = None
    if group_by_owner:
        if codeowners_path:
            codeowners = CodeOwners.parse_file(codeowners_path)
        else:
            codeowners = CodeOwners.find_and_parse(base_path)
        
        if codeowners is None or (not codeowners.rules and not codeowners.default_owners):
            console.print("[yellow]Warning: No CODEOWNERS file found. Results will not be grouped by owner.[/yellow]")
            codeowners = None
        elif verbose:
            console.print(f"[dim]Loaded CODEOWNERS with {len(codeowners.rules)} rules[/dim]")
    
    if not markdown_files:
        console.print(f"[yellow]No markdown files found in {path}[/yellow]")
        raise typer.Exit(code=0)
    
    if format == OutputFormat.CONSOLE:
        console.print(Panel.fit(
            f"[bold blue]Clean Docs Scan[/bold blue]\n"
            f"Files: {len(markdown_files)}\n"
            f"Base: {base_path}",
            border_style="blue"
        ))
    
    # Parse all documents
    documents = []
    for file_path in markdown_files:
        try:
            doc = parser.parse_file(file_path)
            if doc.links:  # Only include docs with links
                documents.append(doc)
        except Exception as e:
            if verbose:
                console.print(f"[red]Error parsing {file_path}: {e}[/red]")
    
    if not documents:
        console.print("[yellow]No documents with links found[/yellow]")
        raise typer.Exit(code=0)
    
    # Count total links for progress
    total_links = sum(len(doc.links) for doc in documents)
    
    # Check all links
    async def run_checks():
        async with LinkChecker(
            cache=cache,
            timeout=timeout if timeout else config.links.timeout,
            concurrency=config.links.concurrency,
            ignore_patterns=ignore_patterns,
            retry_count=retry,
        ) as checker:
            results = []
            found_broken = False
            
            if format == OutputFormat.CONSOLE and config.output.show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    TextColumn("[cyan]{task.fields[links_checked]}/{task.fields[total_links]} links[/cyan]"),
                    console=console,
                    transient=True,
                ) as progress:
                    task = progress.add_task(
                        "Checking links...",
                        total=len(documents),
                        links_checked=0,
                        total_links=total_links,
                    )
                    links_checked = 0
                    for doc in documents:
                        progress.update(task, description=f"Checking {doc.path.name}...")
                        result = await checker.check_document(doc, base_path)
                        results.append(result)
                        links_checked += len(doc.links)
                        progress.update(task, advance=1, links_checked=links_checked)
                        
                        # Fail fast mode
                        if fail_fast and result.broken_count > 0:
                            found_broken = True
                            break
            else:
                for doc in documents:
                    result = await checker.check_document(doc, base_path)
                    results.append(result)
                    
                    # Fail fast mode
                    if fail_fast and result.broken_count > 0:
                        found_broken = True
                        break
            
            return results, found_broken
    
    all_results, stopped_early = asyncio.run(run_checks())
    
    # Calculate totals
    total_broken = sum(r.broken_count for r in all_results)
    
    if stopped_early and format == OutputFormat.CONSOLE:
        console.print("[yellow]Stopped early due to --fail-fast[/yellow]")
    
    # Handle fixing with iterative loop
    if fix and format == OutputFormat.CONSOLE:
        fixer = LinkFixer(base_path, console, config)
        
        if dry_run:
            # Single pass to show what would be fixed
            console.print("\n[bold yellow]Dry Run Mode - Preview of fixes:[/bold yellow]")
            iterations, attempted, succeeded = asyncio.run(
                fixer.fix_iteratively(markdown_files, cache, auto_accept=False, dry_run=True)
            )
            console.print(f"\n[yellow]Would apply fixes in {iterations} iteration(s)[/yellow]")
        else:
            # Iterative fixing loop
            console.print("\n[bold cyan]Starting iterative fix loop...[/bold cyan]")
            console.print("[dim]Will re-check links after each round of fixes[/dim]\n")
            
            iterations, attempted, succeeded = asyncio.run(
                fixer.fix_iteratively(markdown_files, cache, auto_accept=yes, dry_run=False)
            )
            
            if attempted > 0:
                console.print(f"\n[bold green]Fix loop complete:[/bold green]")
                console.print(f"  Iterations: {iterations}")
                console.print(f"  Total fixes applied: {succeeded}/{attempted}")
            
            # Re-run check to get final status
            console.print("\n[dim]Re-checking links after fixes...[/dim]")
            async def final_check():
                async with LinkChecker(
                    cache=cache,
                    timeout=config.links.timeout,
                    concurrency=config.links.concurrency,
                    ignore_patterns=ignore_patterns,
                ) as checker:
                    final_results = []
                    for file_path in markdown_files:
                        try:
                            doc = parser.parse_file(file_path)
                            if doc.links:
                                result = await checker.check_document(doc, base_path)
                                final_results.append(result)
                        except Exception:
                            pass
                    return final_results
            
            all_results = asyncio.run(final_check())
            total_broken = sum(r.broken_count for r in all_results)
    
    # Print results
    # GitHub Actions annotations
    if github_annotations:
        _print_github_annotations(all_results, base_path)
    
    # Determine output destination
    output_content = None
    if output_file or format != OutputFormat.CONSOLE:
        import io
        output_buffer = io.StringIO()
    
    # Print results
    if format == OutputFormat.JSON:
        output_content = _get_json_output(all_results, fix, dry_run, codeowners, base_path)
        if output_file:
            output_file.write_text(output_content)
            console.print(f"[green]Results written to {output_file}[/green]")
        else:
            console.print(output_content)
    elif format == OutputFormat.MARKDOWN:
        output_content = _get_markdown_output(all_results, fix, dry_run, base_path, codeowners)
        if output_file:
            output_file.write_text(output_content)
            console.print(f"[green]Results written to {output_file}[/green]")
        else:
            print(output_content)
    else:
        _print_console_results(all_results, fix, dry_run, verbose, total_broken, codeowners, base_path)
    
    # Exit with error code if broken links found
    if total_broken > 0:
        raise typer.Exit(code=1)


def _print_github_annotations(results, base_path: Path):
    """Print GitHub Actions workflow annotations for broken links."""
    for check_result in results:
        if check_result.broken_count == 0:
            continue
        
        doc = check_result.document
        try:
            rel_path = doc.path.relative_to(base_path)
        except ValueError:
            rel_path = doc.path
        
        for result in check_result.results:
            if result.status == LinkStatus.BROKEN:
                link = result.link
                # GitHub Actions annotation format
                # ::error file={name},line={line},col={col}::{message}
                message = f"Broken link: {link.url}"
                if result.error_message:
                    message += f" - {result.error_message}"
                print(f"::error file={rel_path},line={link.line}::{message}")


def _get_json_output(results, fix: bool, dry_run: bool, codeowners: Optional[CodeOwners] = None, 
                     base_path: Optional[Path] = None) -> str:
    """Get results as JSON string."""
    output = {
        "summary": {
            "files_checked": len(results),
            "total_links": sum(r.total_count for r in results),
            "broken_links": sum(r.broken_count for r in results),
            "ok_links": sum(r.ok_count for r in results),
        },
        "files": [],
    }
    
    if codeowners and base_path:
        output["by_owner"] = {}
    
    for check_result in results:
        doc = check_result.document
        
        try:
            rel_path = str(doc.path.relative_to(base_path)) if base_path else str(doc.path)
        except ValueError:
            rel_path = str(doc.path)
        
        file_data = {
            "path": str(doc.path),
            "relative_path": rel_path,
            "total_links": check_result.total_count,
            "broken_links": check_result.broken_count,
            "links": [],
        }
        
        if codeowners:
            owners = codeowners.get_owners(rel_path)
            file_data["owners"] = owners
            
            owner_key = codeowners.get_owner_key(rel_path)
            if owner_key not in output["by_owner"]:
                output["by_owner"][owner_key] = {
                    "owners": owners,
                    "files": [],
                    "broken_count": 0,
                }
            output["by_owner"][owner_key]["files"].append(rel_path)
            output["by_owner"][owner_key]["broken_count"] += check_result.broken_count
        
        for result in check_result.results:
            link_data = {
                "url": result.link.url,
                "text": result.link.text,
                "line": result.link.line,
                "status": result.status.value,
                "status_code": result.status_code,
            }
            if result.error_message:
                link_data["error"] = result.error_message
            if result.suggestion:
                link_data["suggestion"] = result.suggestion
            
            file_data["links"].append(link_data)
        
        output["files"].append(file_data)
    
    return json.dumps(output, indent=2)


def _get_markdown_output(results, fix: bool, dry_run: bool, base_path: Path, 
                         codeowners: Optional[CodeOwners] = None) -> str:
    """Get results as Markdown string."""
    total_links = sum(r.total_count for r in results)
    total_broken = sum(r.broken_count for r in results)
    total_ok = sum(r.ok_count for r in results)
    
    lines = []
    lines.append("# Clean Docs Report\n")
    
    # Summary
    lines.append("## Summary\n")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Files Checked | {len(results)} |")
    lines.append(f"| Total Links | {total_links} |")
    lines.append(f"| Working | {total_ok} |")
    lines.append(f"| Broken | {total_broken} |")
    lines.append("")
    
    if total_broken == 0:
        lines.append("> ✅ **All links are working!**\n")
    else:
        lines.append(f"> ❌ **Found {total_broken} broken link(s)**\n")
    
    # Broken links details
    if total_broken > 0:
        if codeowners:
            _append_markdown_by_owner(lines, results, base_path, codeowners)
        else:
            _append_markdown_ungrouped(lines, results, base_path)
    
    return "\n".join(lines)


def _append_markdown_ungrouped(lines: list, results, base_path: Path):
    """Append broken links without grouping to lines list."""
    lines.append("## Broken Links\n")
    
    for check_result in results:
        if check_result.broken_count == 0:
            continue
        
        doc = check_result.document
        try:
            rel_path = doc.path.relative_to(base_path)
        except ValueError:
            rel_path = doc.path
        
        broken_in_doc = [r for r in check_result.results if r.status == LinkStatus.BROKEN]
        
        lines.append(f"### `{rel_path}`\n")
        lines.append("| Line | Link | Error | Suggestion |")
        lines.append("|------|------|-------|------------|")
        
        for result in broken_in_doc:
            link = result.link
            url = link.url.replace("|", "\\|")
            error = (result.error_message or "").replace("|", "\\|")
            suggestion = (result.suggestion or "-").replace("|", "\\|")
            lines.append(f"| {link.line} | `{url}` | {error} | {suggestion} |")
        
        lines.append("")


def _append_markdown_by_owner(lines: list, results, base_path: Path, codeowners: CodeOwners):
    """Append broken links grouped by CODEOWNERS to lines list."""
    from collections import defaultdict
    
    owner_groups: dict = defaultdict(list)
    
    for check_result in results:
        if check_result.broken_count == 0:
            continue
        
        doc = check_result.document
        try:
            rel_path = str(doc.path.relative_to(base_path))
        except ValueError:
            rel_path = str(doc.path)
        
        owner_key = codeowners.get_owner_key(rel_path)
        
        for result in check_result.results:
            if result.status == LinkStatus.BROKEN:
                owner_groups[owner_key].append((rel_path, doc, result))
    
    lines.append("## Broken Links by Owner\n")
    lines.append(f"*Results grouped by CODEOWNERS - {len(owner_groups)} owner group(s)*\n")
    
    # Owner summary table
    lines.append("### Owner Summary\n")
    lines.append("| Owner | Broken Links | Files Affected |")
    lines.append("|-------|--------------|----------------|")
    
    for owner_key in sorted(owner_groups.keys()):
        items = owner_groups[owner_key]
        owner_display = owner_key if owner_key != "_no_owner_" else "(no owner)"
        files_affected = len(set(item[0] for item in items))
        lines.append(f"| {owner_display} | {len(items)} | {files_affected} |")
    
    lines.append("")


def _print_console_results(results, fix: bool, dry_run: bool, verbose: bool, total_broken: int = None, 
                          codeowners: Optional[CodeOwners] = None, base_path: Optional[Path] = None):
    """Print results in console format."""
    total_links = sum(r.total_count for r in results)
    if total_broken is None:
        total_broken = sum(r.broken_count for r in results)
    total_ok = sum(r.ok_count for r in results)
    
    # Summary table
    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="bold")
    
    summary_table.add_row("Files Checked", str(len(results)))
    summary_table.add_row("Total Links", str(total_links))
    summary_table.add_row("Working", f"[green]{total_ok}[/green]")
    summary_table.add_row("Broken", f"[red]{total_broken}[/red]" if total_broken > 0 else "[green]0[/green]")
    
    console.print("\n[bold]Summary:[/bold]")
    console.print(summary_table)
    
    # Group results by owner if codeowners is provided
    if codeowners and total_broken > 0:
        _print_results_by_owner(results, codeowners, base_path, verbose)
    elif total_broken > 0 or verbose:
        # Standard detailed results
        console.print("\n[bold]Details:[/bold]")
        
        for check_result in results:
            if check_result.broken_count == 0 and not verbose:
                continue
            
            doc = check_result.document
            broken_in_doc = [r for r in check_result.results if r.status == LinkStatus.BROKEN]
            
            if broken_in_doc:
                console.print(f"\n[bold red]✗[/bold red] {doc.path}")
                for result in broken_in_doc:
                    link = result.link
                    # Escape brackets in URL/text to prevent Rich markup interpretation
                    safe_url = link.url.replace("[", "\\[").replace("]", "\\]")
                    safe_text = (link.text or 'link').replace("[", "\\[").replace("]", "\\]")
                    console.print(f"  [dim]Line {link.line}:[/dim] \\[{safe_url}]({safe_text})")
                    console.print(f"    [red]Error:[/red] {result.error_message}")
                    if result.suggestion:
                        console.print(f"    [yellow]Hint:[/yellow] {result.suggestion}")
            elif verbose:
                console.print(f"\n[bold green]✓[/bold green] {doc.path}")
                for result in check_result.results:
                    if result.status == LinkStatus.OK:
                        safe_url = result.link.url.replace("[", "\\[").replace("]", "\\]")
                        console.print(f"  [dim]Line {result.link.line}:[/dim] {safe_url} [green]OK[/green]")
    
    # Fix mode info
    if fix and total_broken > 0:
        if dry_run:
            console.print(f"\n[yellow]Dry run mode - would attempt to fix {total_broken} broken links[/yellow]")
            console.print("[dim]Run without --dry-run to apply fixes[/dim]")
        else:
            console.print(f"\n[yellow]Fix mode not yet implemented in MVP[/yellow]")
            console.print("[dim]Use --dry-run to see what would be fixed[/dim]")
    
    # Final status
    if total_broken == 0:
        console.print(Panel.fit(
            "[green bold]All links are working! ✓[/green bold]",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            f"[red bold]Found {total_broken} broken link(s)[/red bold]",
            border_style="red"
        ))


def _print_results_by_owner(results, codeowners: CodeOwners, base_path: Path, verbose: bool):
    """Print results grouped by CODEOWNERS."""
    from collections import defaultdict
    
    # Group broken links by owner
    owner_groups: dict = defaultdict(list)
    
    for check_result in results:
        if check_result.broken_count == 0:
            continue
        
        doc = check_result.document
        try:
            rel_path = str(doc.path.relative_to(base_path))
        except ValueError:
            rel_path = str(doc.path)
        
        owner_key = codeowners.get_owner_key(rel_path)
        
        for result in check_result.results:
            if result.status == LinkStatus.BROKEN:
                owner_groups[owner_key].append((doc, result))
    
    if not owner_groups:
        return
    
    console.print(f"\n[bold]Results grouped by CODEOWNERS ({len(owner_groups)} groups):[/bold]")
    
    for owner_key in sorted(owner_groups.keys()):
        broken_items = owner_groups[owner_key]
        
        # Format owner display
        if owner_key == "_no_owner_":
            owner_display = "[dim]No owner defined[/dim]"
        else:
            owners = owner_key.split(",")
            owner_display = " ".join(f"[cyan]{o}[/cyan]" for o in owners)
        
        console.print(f"\n[bold blue]━━━ {owner_display} ({len(broken_items)} broken links) ━━━[/bold blue]")
        
        # Group by file within owner
        files_in_group: dict = defaultdict(list)
        for doc, result in broken_items:
            files_in_group[doc.path].append(result)
        
        for file_path, link_results in files_in_group.items():
            console.print(f"\n  [bold red]✗[/bold red] {file_path}")
            for result in link_results:
                link = result.link
                safe_url = link.url.replace("[", "\\[").replace("]", "\\]")
                console.print(f"    [dim]Line {link.line}:[/dim] {safe_url}")
                console.print(f"      [red]Error:[/red] {result.error_message}")


@app.command()
def cache(
    clear: bool = typer.Option(False, "--clear", help="Clear the cache"),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    cleanup: bool = typer.Option(False, "--cleanup", help="Remove expired entries only"),
    broken: bool = typer.Option(False, "--broken", help="Show cached broken links"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Manage the link cache."""
    config = Config.load(config_path)
    cache_mgr = CacheManager(config.get_cache_dir(), config.cache.ttl_hours)
    
    if clear:
        cache_mgr.clear()
        console.print("[green]Cache cleared successfully[/green]")
    elif cleanup:
        deleted = cache_mgr.cleanup_expired()
        console.print(f"[green]Removed {deleted} expired cache entries[/green]")
    elif broken:
        broken_links = cache_mgr.get_broken_links(limit=50)
        if not broken_links:
            console.print("[green]No broken links in cache[/green]")
        else:
            table = Table(show_header=True, header_style="bold red")
            table.add_column("URL", style="cyan", max_width=60)
            table.add_column("Status", justify="right")
            table.add_column("Error", max_width=30)
            
            for item in broken_links:
                table.add_row(
                    item["url"][:60],
                    str(item["status_code"] or "-"),
                    (item["error"] or "")[:30],
                )
            
            console.print(f"\n[bold]Cached Broken Links ({len(broken_links)}):[/bold]")
            console.print(table)
    elif stats:
        cache_stats = cache_mgr.get_stats()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold")
        
        table.add_row("Total Links Cached", str(cache_stats["total_links"]))
        table.add_row("Valid (not expired)", str(cache_stats["valid_links"]))
        table.add_row("Expired", str(cache_stats["expired_links"]))
        table.add_row("OK Links", f"[green]{cache_stats['ok_links']}[/green]")
        table.add_row("Broken Links", f"[red]{cache_stats['broken_links']}[/red]")
        table.add_row("Avg Response Time", f"{cache_stats['avg_response_time_ms']:.1f} ms")
        table.add_row("Cache Size", f"{cache_stats['cache_size_mb']:.2f} MB")
        table.add_row("Cache Location", str(config.get_cache_dir()))
        
        console.print(table)
        
        if cache_stats["expired_links"] > 0:
            console.print(f"\n[dim]Tip: Run 'clean-docs cache --cleanup' to remove {cache_stats['expired_links']} expired entries[/dim]")
    else:
        console.print("[yellow]Use --clear, --cleanup, --stats, or --broken[/yellow]")


@app.command("fix-prs")
def fix_prs(
    path: Path = typer.Argument(..., help="Path to documentation directory", exists=True),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config file"),
    codeowners_path: Optional[Path] = typer.Option(None, "--codeowners", help="Path to CODEOWNERS file"),
    base_branch: Optional[str] = typer.Option(None, "--base", "-b", help="Base branch to create PRs against (auto-detected if not specified)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be done without making changes"),
    no_pr: bool = typer.Option(False, "--no-pr", help="Apply fixes but don't create PRs"),
    internal_only: bool = typer.Option(True, "--internal-only/--all-links", "-i", help="Only check internal links"),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Glob patterns to exclude"),
    only_owner: Optional[List[str]] = typer.Option(None, "--only-owner", help="Only process these owners (can repeat)"),
    skip_owner: Optional[List[str]] = typer.Option(None, "--skip-owner", help="Skip these owners (can repeat)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Create separate fix PRs grouped by CODEOWNERS.
    
    This command:
    1. Scans for broken links
    2. Groups them by CODEOWNERS
    3. For each owner group with auto-fixable issues:
       - Creates a branch
       - Applies fixes
       - Creates a PR targeting the owners
    
    Example:
        clean-docs fix-prs ./docs --base main --dry-run
        clean-docs fix-prs . --only-owner @myteam --no-pr
    """
    # Load configuration
    config = Config.load(config_path)
    
    # Initialize cache
    cache_mgr = CacheManager(config.get_cache_dir(), config.cache.ttl_hours)
    
    # Build ignore patterns
    ignore_patterns = list(config.links.ignore_patterns)
    if internal_only:
        ignore_patterns.extend(["http://", "https://"])
    
    # Find CODEOWNERS
    base_path = path.resolve()
    if codeowners_path:
        codeowners = CodeOwners.parse_file(codeowners_path)
    else:
        codeowners = CodeOwners.find_and_parse(base_path)
    
    if codeowners is None or (not codeowners.rules and not codeowners.default_owners):
        console.print("[red]Error: No CODEOWNERS file found.[/red]")
        console.print("[dim]Use --codeowners to specify the path, or ensure CODEOWNERS exists in the repo root.[/dim]")
        raise typer.Exit(code=1)
    
    if verbose:
        console.print(f"[dim]Loaded CODEOWNERS with {len(codeowners.rules)} rules[/dim]")
    
    # Find markdown files
    parser = MarkdownParser()
    markdown_files = parser.find_all_markdown_files(base_path)
    
    # Apply exclude patterns
    if exclude:
        original_count = len(markdown_files)
        markdown_files = _filter_files_by_exclude(markdown_files, list(exclude), base_path)
        if verbose:
            console.print(f"[dim]Excluded {original_count - len(markdown_files)} files[/dim]")
    
    if not markdown_files:
        console.print(f"[yellow]No markdown files found in {path}[/yellow]")
        raise typer.Exit(code=0)
    
    # Check if we're in a git repo and auto-detect base branch
    try:
        import subprocess
        subprocess.run(
            ["git", "status"],
            cwd=base_path,
            capture_output=True,
            check=True,
        )
        
        # Auto-detect base branch if not specified
        if base_branch is None:
            # Try to get the default branch from remote
            result = subprocess.run(
                ["git", "remote", "show", "origin"],
                cwd=base_path,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'HEAD branch:' in line:
                        base_branch = line.split(':')[1].strip()
                        break
            
            # Fallback: check if main or master exists
            if base_branch is None:
                for branch in ['main', 'master']:
                    check = subprocess.run(
                        ["git", "rev-parse", "--verify", branch],
                        cwd=base_path,
                        capture_output=True,
                    )
                    if check.returncode == 0:
                        base_branch = branch
                        break
            
            if base_branch is None:
                base_branch = 'main'  # Final fallback
            
            if verbose:
                console.print(f"[dim]Auto-detected base branch: {base_branch}[/dim]")
                
    except subprocess.CalledProcessError:
        console.print("[red]Error: Not a git repository[/red]")
        raise typer.Exit(code=1)
    except FileNotFoundError:
        console.print("[red]Error: git not found[/red]")
        raise typer.Exit(code=1)
    
    # Check gh CLI if we're creating PRs
    if not no_pr and not dry_run:
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print("[red]Error: GitHub CLI not authenticated[/red]")
                console.print("[dim]Run 'gh auth login' first[/dim]")
                raise typer.Exit(code=1)
        except FileNotFoundError:
            console.print("[red]Error: GitHub CLI (gh) not found[/red]")
            console.print("[dim]Install it from https://cli.github.com/[/dim]")
            raise typer.Exit(code=1)
    
    # Run the pipeline
    pipeline = PRPipeline(
        base_path=base_path,
        console=console,
        config=config,
        codeowners=codeowners,
    )
    
    results = asyncio.run(pipeline.run(
        markdown_files=markdown_files,
        cache=cache_mgr,
        ignore_patterns=ignore_patterns,
        dry_run=dry_run,
        create_prs=not no_pr,
        base_branch=base_branch,
        skip_owners=list(skip_owner) if skip_owner else None,
        only_owners=list(only_owner) if only_owner else None,
    ))
    
    # Exit with error if any PRs failed
    if any(r.get("error") for r in results.values()):
        raise typer.Exit(code=1)


@app.command()
def semantic(
    path: Path = typer.Argument(..., help="Path to documentation/code directory"),
    docs_dir: Optional[Path] = typer.Option(None, "--docs", "-d", help="Documentation directory (default: docs/, *.md)"),
    code_dir: Optional[Path] = typer.Option(None, "--code", "-c", help="Code directory (default: src/, lib/, *.py)"),
    orphaned: bool = typer.Option(False, "--orphaned", help="Find docs without related code"),
    missing: bool = typer.Option(False, "--missing", help="Find code without documentation"),
    threshold: float = typer.Option(0.5, "--threshold", "-t", help="Similarity threshold (0.0-1.0)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed results"),
):
    """Semantic analysis - find orphaned docs and missing documentation.
    
    Requires: pip install clean-docs[semantic]
    
    Examples:
        clean-docs semantic . --orphaned      # Find docs with no related code
        clean-docs semantic . --missing       # Find code with no docs
        clean-docs semantic . --orphaned --missing  # Both
    """
    if not SEMANTIC_AVAILABLE:
        console.print("[red]Semantic analysis requires additional dependencies.[/red]")
        console.print("Install with: [cyan]pip install 'clean-docs[semantic]'[/cyan]")
        raise typer.Exit(code=1)
    
    if not orphaned and not missing:
        console.print("[yellow]Specify --orphaned and/or --missing[/yellow]")
        console.print("Example: clean-docs semantic . --orphaned --missing")
        raise typer.Exit(code=1)
    
    base_path = path.resolve()
    config = Config.load(None)
    
    # Determine directories
    if docs_dir:
        docs_path = docs_dir.resolve()
    else:
        # Auto-detect docs directory
        for candidate in ["docs", "doc", "documentation"]:
            if (base_path / candidate).is_dir():
                docs_path = base_path / candidate
                break
        else:
            docs_path = base_path
    
    if code_dir:
        code_path = code_dir.resolve()
    else:
        # Auto-detect code directory
        for candidate in ["src", "lib", "app", base_path.name]:
            if (base_path / candidate).is_dir():
                code_path = base_path / candidate
                break
        else:
            code_path = base_path
    
    console.print(Panel(
        f"[bold]Semantic Analysis[/bold]\n"
        f"Docs: {docs_path}\n"
        f"Code: {code_path}\n"
        f"Threshold: {threshold}",
        title="Clean Docs",
    ))
    
    # Initialize embedding manager
    cache_dir = config.get_cache_dir() / "semantic"
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Loading embedding model...", total=None)
        
        embedding_manager = EmbeddingManager(cache_dir, console=console)
        analyzer = SemanticAnalyzer(embedding_manager, console=console)
        
        # Index documents
        progress.update(task, description="Indexing documentation...")
        doc_files = list(docs_path.rglob("*.md"))
        for doc_file in doc_files:
            analyzer.index_document(doc_file)
        
        # Index code
        progress.update(task, description="Indexing code...")
        code_extensions = ["*.py", "*.js", "*.ts", "*.go", "*.java", "*.rs"]
        for ext in code_extensions:
            for code_file in code_path.rglob(ext):
                if "node_modules" not in str(code_file) and ".git" not in str(code_file):
                    analyzer.index_code(code_file)
        
        progress.update(task, description="Analyzing relationships...")
    
    # Results
    console.print()
    
    if orphaned:
        console.print("[bold]Orphaned Documentation[/bold] (docs with no related code):")
        orphaned_results = analyzer.find_orphaned_docs(threshold=threshold)
        
        if not orphaned_results:
            console.print("  [green]No orphaned docs found![/green]")
        else:
            table = Table(show_header=True)
            table.add_column("Document", style="cyan")
            table.add_column("Best Match", style="dim")
            table.add_column("Similarity", justify="right")
            
            for doc_entry, matches in orphaned_results:
                try:
                    rel_path = doc_entry.path.relative_to(base_path)
                except ValueError:
                    rel_path = doc_entry.path
                
                if matches:
                    best_match = matches[0]
                    try:
                        match_path = best_match[0].path.relative_to(base_path)
                    except ValueError:
                        match_path = best_match[0].path
                    table.add_row(str(rel_path), str(match_path), f"{best_match[1]:.2f}")
                else:
                    table.add_row(str(rel_path), "-", "-")
            
            console.print(table)
            console.print(f"\n[yellow]Found {len(orphaned_results)} orphaned doc(s)[/yellow]")
        
        console.print()
    
    if missing:
        console.print("[bold]Missing Documentation[/bold] (code with no related docs):")
        missing_results = analyzer.find_missing_docs(threshold=threshold)
        
        if not missing_results:
            console.print("  [green]All code has documentation![/green]")
        else:
            table = Table(show_header=True)
            table.add_column("Code File", style="cyan")
            table.add_column("Best Match", style="dim")
            table.add_column("Similarity", justify="right")
            
            for code_entry, matches in missing_results:
                try:
                    rel_path = code_entry.path.relative_to(base_path)
                except ValueError:
                    rel_path = code_entry.path
                
                if matches:
                    best_match = matches[0]
                    try:
                        match_path = best_match[0].path.relative_to(base_path)
                    except ValueError:
                        match_path = best_match[0].path
                    table.add_row(str(rel_path), str(match_path), f"{best_match[1]:.2f}")
                else:
                    table.add_row(str(rel_path), "-", "-")
            
            console.print(table)
            console.print(f"\n[yellow]Found {len(missing_results)} code file(s) without docs[/yellow]")
    
    # Summary
    console.print()
    total_issues = 0
    if orphaned:
        total_issues += len(analyzer.find_orphaned_docs(threshold=threshold))
    if missing:
        total_issues += len(analyzer.find_missing_docs(threshold=threshold))
    
    if total_issues > 0:
        raise typer.Exit(code=1)


@app.command()
def owners(
    path: Path = typer.Argument(..., help="File or directory path to check ownership"),
    codeowners_path: Optional[Path] = typer.Option(None, "--codeowners", help="Path to CODEOWNERS file"),
):
    """Show CODEOWNERS for a file or directory.
    
    Example:
        clean-docs owners ./docs/guide.md
        clean-docs owners ./framework/
    """
    # Find repo root (where CODEOWNERS might be)
    check_path = path.resolve()
    if check_path.is_file():
        repo_root = check_path.parent
    else:
        repo_root = check_path
    
    # Walk up to find .git or CODEOWNERS
    while repo_root != repo_root.parent:
        if (repo_root / ".git").exists() or (repo_root / "CODEOWNERS").exists():
            break
        repo_root = repo_root.parent
    
    # Load CODEOWNERS
    if codeowners_path:
        codeowners = CodeOwners.parse_file(codeowners_path)
    else:
        codeowners = CodeOwners.find_and_parse(repo_root)
    
    if codeowners is None:
        console.print("[yellow]No CODEOWNERS file found[/yellow]")
        raise typer.Exit(code=1)
    
    # Get relative path from repo root
    try:
        rel_path = str(path.resolve().relative_to(repo_root))
    except ValueError:
        rel_path = str(path)
    
    owners = codeowners.get_owners(rel_path)
    
    if owners:
        console.print(f"[bold]Owners of[/bold] {rel_path}:")
        for owner in owners:
            console.print(f"  [cyan]{owner}[/cyan]")
    else:
        console.print(f"[yellow]No owners defined for[/yellow] {rel_path}")


if __name__ == "__main__":
    app()
