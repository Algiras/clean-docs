"""Doctor command - check prerequisites."""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


class Doctor:
    """Check system prerequisites for Clean Docs."""
    
    def __init__(self, console: Console):
        self.console = console
        self.checks: List[Tuple[str, bool, str]] = []
    
    def run_all_checks(self, check_optional: bool = False) -> bool:
        """Run all prerequisite checks. Returns True if all required checks passed.
        
        Args:
            check_optional: Also check optional features (semantic, copilot)
        """
        self.checks = []
        
        # Required checks
        self._check_python_version()
        self._check_gh_cli()
        self._check_github_token()
        self._check_cache_writable()
        
        # Optional checks (suggested features)
        if check_optional:
            self._check_semantic_deps()
            self._check_copilot_cli()
        
        # Only required checks determine success
        required_checks = [c for c in self.checks if "(Optional)" not in c[0]]
        return all(passed for _, passed, _ in required_checks)
    
    def _check_python_version(self) -> None:
        """Check Python version >= 3.10."""
        import sys
        version = sys.version_info
        passed = version.major >= 3 and version.minor >= 10
        message = f"Python {version.major}.{version.minor}.{version.micro}"
        if not passed:
            message += " (requires >= 3.10)"
        self.checks.append(("Python Version", passed, message))
    
    def _check_gh_cli(self) -> None:
        """Check if GitHub CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                version = result.stdout.strip().split("\n")[0]
                # Check authentication
                auth_result = subprocess.run(
                    ["gh", "auth", "status"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if auth_result.returncode == 0:
                    self.checks.append(("GitHub CLI", True, f"{version} (authenticated)"))
                else:
                    self.checks.append(("GitHub CLI", True, f"{version} (not authenticated)"))
            else:
                self.checks.append(("GitHub CLI", False, "Not installed"))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.checks.append(("GitHub CLI", False, "Not installed"))
    
    def _check_github_token(self) -> None:
        """Check for GITHUB_TOKEN environment variable."""
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            masked = token[:4] + "..." + token[-4:] if len(token) > 8 else "***"
            self.checks.append(("GITHUB_TOKEN", True, f"Set ({masked})"))
        else:
            self.checks.append(("GITHUB_TOKEN", False, "Not set (needed if gh CLI not authenticated)"))
    
    def _check_cache_writable(self) -> None:
        """Check if cache directory is writable."""
        import tempfile
        try:
            cache_dir = Path(tempfile.gettempdir()) / "clean-docs-cache"
            cache_dir.mkdir(exist_ok=True)
            test_file = cache_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            self.checks.append(("Cache Directory", True, str(cache_dir)))
        except Exception as e:
            self.checks.append(("Cache Directory", False, f"Not writable: {e}"))
    
    def _check_semantic_deps(self) -> None:
        """Check if semantic analysis dependencies are available (optional)."""
        try:
            import sentence_transformers  # noqa: F401
            import torch  # noqa: F401
            self.checks.append((
                "Semantic Analysis (Optional)",
                True,
                "sentence-transformers available"
            ))
        except ImportError:
            self.checks.append((
                "Semantic Analysis (Optional)",
                False,
                "Install with: pip install clean-docs[semantic]"
            ))
    
    def _check_copilot_cli(self) -> None:
        """Check if GitHub Copilot CLI is available (optional)."""
        try:
            result = subprocess.run(
                ["gh", "copilot", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                self.checks.append((
                    "Copilot CLI (Optional)", 
                    True, 
                    "Available for agent-based fixes"
                ))
            else:
                self.checks.append((
                    "Copilot CLI (Optional)", 
                    False, 
                    "Install: gh extension install github/copilot-cli"
                ))
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self.checks.append((
                "Copilot CLI (Optional)", 
                False, 
                "Not installed (optional for agent mode)"
            ))
    
    def print_report(self) -> None:
        """Print formatted report of all checks."""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Check", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")
        
        for name, passed, details in self.checks:
            status = "✅ Pass" if passed else "❌ Fail"
            status_style = "green" if passed else "red"
            table.add_row(name, f"[{status_style}]{status}[/{status_style}]", details)
        
        all_passed = all(passed for _, passed, _ in self.checks)
        
        if all_passed:
            self.console.print(Panel.fit(
                "[green]All checks passed! Ready to use Clean Docs.[/green]",
                title="Doctor Report",
                border_style="green"
            ))
        else:
            self.console.print(Panel.fit(
                "[yellow]Some checks failed. See details below.[/yellow]",
                title="Doctor Report",
                border_style="yellow"
            ))
        
        self.console.print(table)
        
        if not all_passed:
            self.console.print("\n[yellow]Recommendations:[/yellow]")
            self._print_recommendations()
    
    def _print_recommendations(self) -> None:
        """Print recommendations for failed checks."""
        failed = [name for name, passed, _ in self.checks if not passed]
        
        if "Python Version" in failed:
            self.console.print("  • Install Python 3.10 or higher")
        
        if "GitHub CLI" in failed and "GITHUB_TOKEN" in failed:
            self.console.print("  • Install GitHub CLI: https://cli.github.com/")
            self.console.print("    Then run: gh auth login")
            self.console.print("  • Or set GITHUB_TOKEN environment variable")
        elif "GitHub CLI" in failed:
            self.console.print("  • Install GitHub CLI for better GitHub link checking")
            self.console.print("    https://cli.github.com/")
        elif "GITHUB_TOKEN" in failed:
            self.console.print("  • GitHub CLI is installed but not authenticated")
            self.console.print("    Run: gh auth login")
        
        if "Cache Directory" in failed:
            self.console.print("  • Ensure you have write permissions in the current directory")
