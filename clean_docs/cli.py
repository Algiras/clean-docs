"""Main CLI for Clean Docs."""

import asyncio
import json
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text

from clean_docs.cache import CacheManager
from clean_docs.config import Config, DEFAULT_CONFIG_CONTENT
from clean_docs.doctor import Doctor
from clean_docs.fixer import LinkFixer
from clean_docs.init_wizard import InitWizard
from clean_docs.link_checker import LinkChecker, LinkResult, LinkStatus
from clean_docs.parsers.markdown import MarkdownParser
from clean_docs.semantic import EmbeddingManager, SemanticAnalyzer

app = typer.Typer(
    name="clean-docs",
    help="Clean up documentation - check links, find outdated content",
    rich_markup_mode="rich",
)
console = Console()


class OutputFormat(str, Enum):
    CONSOLE = "console"
    JSON = "json"


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
    format: OutputFormat = typer.Option(OutputFormat.CONSOLE, "--format", "-f", help="Output format"),
    init: bool = typer.Option(False, "--init", help="Create default config file and exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
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
    
    # Find markdown files
    parser = MarkdownParser()
    
    if path.is_file():
        markdown_files = [path]
        base_path = path.parent
    else:
        markdown_files = parser.find_all_markdown_files(path)
        base_path = path
    
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
    
    # Check all links
    async def run_checks():
        async with LinkChecker(
            cache=cache,
            timeout=config.links.timeout,
            concurrency=config.links.concurrency,
            ignore_patterns=config.links.ignore_patterns,
        ) as checker:
            results = []
            
            if format == OutputFormat.CONSOLE and config.output.show_progress:
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    console=console,
                ) as progress:
                    for doc in documents:
                        task = progress.add_task(
                            f"Checking {doc.path.name}...",
                            total=None,
                        )
                        result = await checker.check_document(doc, base_path)
                        results.append(result)
                        progress.update(task, completed=True)
            else:
                for doc in documents:
                    result = await checker.check_document(doc, base_path)
                    results.append(result)
            
            return results
    
    all_results = asyncio.run(run_checks())
    
    # Calculate totals
    total_broken = sum(r.broken_count for r in all_results)
    
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
                    ignore_patterns=config.links.ignore_patterns,
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
    if format == OutputFormat.JSON:
        _print_json_results(all_results, fix, dry_run)
    else:
        _print_console_results(all_results, fix, dry_run, verbose, total_broken)
    
    # Exit with error code if broken links found
    if total_broken > 0:
        raise typer.Exit(code=1)


def _print_console_results(results, fix: bool, dry_run: bool, verbose: bool, total_broken: int = None):
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
    
    # Detailed results
    if total_broken > 0 or verbose:
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
                    console.print(f"  [dim]Line {link.line}:[/dim] [{link.url}]({link.text or 'link'})")
                    console.print(f"    [red]Error:[/red] {result.error_message}")
                    if result.suggestion:
                        console.print(f"    [yellow]Hint:[/yellow] {result.suggestion}")
            elif verbose:
                console.print(f"\n[bold green]✓[/bold green] {doc.path}")
                for result in check_result.results:
                    if result.status == LinkStatus.OK:
                        console.print(f"  [dim]Line {result.link.line}:[/dim] {result.link.url} [green]OK[/green]")
    
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


def _print_json_results(results, fix: bool, dry_run: bool):
    """Print results in JSON format."""
    output = {
        "summary": {
            "files_checked": len(results),
            "total_links": sum(r.total_count for r in results),
            "broken_links": sum(r.broken_count for r in results),
            "ok_links": sum(r.ok_count for r in results),
        },
        "files": [],
    }
    
    for check_result in results:
        doc = check_result.document
        file_data = {
            "path": str(doc.path),
            "total_links": check_result.total_count,
            "broken_links": check_result.broken_count,
            "links": [],
        }
        
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
    
    console.print(json.dumps(output, indent=2))


@app.command()
def cache(
    clear: bool = typer.Option(False, "--clear", help="Clear the cache"),
    stats: bool = typer.Option(False, "--stats", help="Show cache statistics"),
    config_path: Optional[Path] = typer.Option(None, "--config", "-c"),
):
    """Manage the link cache."""
    config = Config.load(config_path)
    cache_mgr = CacheManager(config.get_cache_dir(), config.cache.ttl_hours)
    
    if clear:
        cache_mgr.clear()
        console.print("[green]Cache cleared successfully[/green]")
    elif stats:
        cache_stats = cache_mgr.get_stats()
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="bold")
        
        table.add_row("Total Links Cached", str(cache_stats["total_links"]))
        table.add_row("Valid (not expired)", str(cache_stats["valid_links"]))
        table.add_row("Expired", str(cache_stats["expired_links"]))
        table.add_row("Cache Size", f"{cache_stats['cache_size_mb']:.2f} MB")
        
        console.print(table)
    else:
        console.print("[yellow]Use --clear or --stats[/yellow]")


if __name__ == "__main__":
    app()
