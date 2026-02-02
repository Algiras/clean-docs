"""Interactive initialization wizard for Clean Docs."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table

from clean_docs.config import Config, DEFAULT_CONFIG_CONTENT


@dataclass
class TemplateChoice:
    """Represents a template option."""
    name: str
    description: str
    files: Dict[str, str]  # filename -> content
    config_overrides: Dict[str, Any]


@dataclass
class InitOptions:
    """User selections from the wizard."""
    project_type: str
    docs_location: str
    validate_examples: bool
    languages: List[str]
    enable_freshness: bool
    generate_badges: bool
    setup_ci: str
    setup_git_hooks: bool
    create_structure: bool
    template: str


class InitWizard:
    """Interactive wizard for project initialization."""
    
    # Template definitions
    TEMPLATES = {
        "minimal": TemplateChoice(
            name="minimal",
            description="Essential files only - fast setup",
            files={},
            config_overrides={}
        ),
        "full": TemplateChoice(
            name="full",
            description="Complete setup with all features",
            files={},
            config_overrides={
                "stale_detection": {"enabled": True, "threshold_days": 90},
                "code_validation": {"enabled": True},
                "readme_quality": {"enabled": True},
                "freshness_tracking": {"enabled": True},
            }
        ),
        "python-lib": TemplateChoice(
            name="python-lib",
            description="Python library with Sphinx docs",
            files={},
            config_overrides={
                "code_validation": {"enabled": True, "languages": ["python"]},
            }
        ),
        "js-package": TemplateChoice(
            name="js-package",
            description="JavaScript/TypeScript package",
            files={},
            config_overrides={
                "code_validation": {"enabled": True, "languages": ["javascript", "typescript"]},
            }
        ),
    }
    
    def __init__(self, console: Console, base_path: Path):
        self.console = console
        self.base_path = base_path
        self.options: Optional[InitOptions] = None
    
    def run(self) -> bool:
        """Run the interactive wizard. Returns True if successful."""
        self.console.print(Panel.fit(
            "[bold cyan]Clean Docs Initialization Wizard[/bold cyan]\n"
            "Let's set up documentation quality checks for your project!",
            border_style="cyan"
        ))
        
        try:
            # Step 1: Choose template
            template = self._choose_template()
            
            # Step 2: Project type
            project_type = self._ask_project_type()
            
            # Step 3: Documentation location
            docs_location = self._ask_docs_location()
            
            # Step 4: Code example validation
            validate_examples, languages = self._ask_code_validation()
            
            # Step 5: Freshness tracking
            enable_freshness = self._ask_freshness_tracking()
            
            # Step 6: Badges
            generate_badges = self._ask_badges()
            
            # Step 7: CI/CD
            setup_ci = self._ask_ci_setup()
            
            # Step 8: Git hooks
            setup_git_hooks = self._ask_git_hooks()
            
            # Step 9: Create structure
            create_structure = self._ask_create_structure()
            
            # Store options
            self.options = InitOptions(
                project_type=project_type,
                docs_location=docs_location,
                validate_examples=validate_examples,
                languages=languages,
                enable_freshness=enable_freshness,
                generate_badges=generate_badges,
                setup_ci=setup_ci,
                setup_git_hooks=setup_git_hooks,
                create_structure=create_structure,
                template=template,
            )
            
            # Show summary
            if not self._confirm_summary():
                self.console.print("[yellow]Cancelled. No changes made.[/yellow]")
                return False
            
            # Execute creation
            self._create_files()
            
            return True
            
        except KeyboardInterrupt:
            self.console.print("\n[yellow]Wizard cancelled.[/yellow]")
            return False
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")
            return False
    
    def _choose_template(self) -> str:
        """Ask user to choose a template."""
        self.console.print("\n[bold]Step 1: Choose a template[/bold]")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="cyan", justify="right")
        table.add_column("Template", style="green")
        table.add_column("Description", style="dim")
        
        templates = list(self.TEMPLATES.values())
        for i, template in enumerate(templates, 1):
            table.add_row(str(i), template.name, template.description)
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "Select template",
            choices=[str(i) for i in range(1, len(templates) + 1)],
            default="2"
        )
        
        return templates[int(choice) - 1].name
    
    def _ask_project_type(self) -> str:
        """Ask about project type."""
        self.console.print("\n[bold]Step 2: Project type[/bold]")
        
        choices = [
            "python-lib",
            "js-package",
            "documentation-site",
            "monorepo",
            "other"
        ]
        
        table = Table()
        table.add_column("#", justify="right")
        table.add_column("Type")
        
        for i, choice in enumerate(choices, 1):
            table.add_row(str(i), choice.replace("-", " ").title())
        
        self.console.print(table)
        
        choice = Prompt.ask(
            "Select type",
            choices=[str(i) for i in range(1, len(choices) + 1)],
            default="1"
        )
        
        return choices[int(choice) - 1]
    
    def _ask_docs_location(self) -> str:
        """Ask where documentation is/will be located."""
        self.console.print("\n[bold]Step 3: Documentation location[/bold]")
        
        # Check common locations
        common_locations = ["./docs", "./doc", "./", "./documentation"]
        existing = [loc for loc in common_locations if (self.base_path / loc.strip("./")).exists()]
        
        if existing:
            self.console.print(f"[dim]Detected existing docs: {', '.join(existing)}[/dim]")
        
        location = Prompt.ask(
            "Where is your documentation located?",
            choices=["./docs", "./doc", "./", "Other"],
            default="./docs" if "./docs" in existing else "./docs"
        )
        
        if location == "Other":
            location = Prompt.ask("Enter path")
        
        return location
    
    def _ask_code_validation(self) -> tuple:
        """Ask about code example validation."""
        self.console.print("\n[bold]Step 4: Code example validation[/bold]")
        
        enable = Confirm.ask(
            "Validate code examples in documentation?",
            default=True
        )
        
        languages = []
        if enable:
            self.console.print("[dim]Which languages should be validated?[/dim]")
            
            if Confirm.ask("Python?", default=True):
                languages.append("python")
            if Confirm.ask("JavaScript/TypeScript?", default=False):
                languages.extend(["javascript", "typescript"])
            if Confirm.ask("Bash/Shell?", default=False):
                languages.append("bash")
        
        return enable, languages
    
    def _ask_freshness_tracking(self) -> bool:
        """Ask about freshness tracking."""
        self.console.print("\n[bold]Step 5: Documentation freshness tracking[/bold]")
        
        self.console.print("[dim]Tracks when docs were last updated vs code changes[/dim]")
        
        return Confirm.ask(
            "Enable freshness tracking?",
            default=True
        )
    
    def _ask_badges(self) -> bool:
        """Ask about badge generation."""
        self.console.print("\n[bold]Step 6: Health badges[/bold]")
        
        self.console.print("[dim]Generate badges showing documentation health[/dim]")
        
        return Confirm.ask(
            "Generate health badges for README?",
            default=True
        )
    
    def _ask_ci_setup(self) -> str:
        """Ask about CI/CD setup."""
        self.console.print("\n[bold]Step 7: CI/CD Integration[/bold]")
        
        choices = ["github-actions", "gitlab-ci", "none"]
        
        table = Table()
        table.add_column("#", justify="right")
        table.add_column("Platform")
        
        for i, choice in enumerate(choices, 1):
            table.add_row(str(i), choice.replace("-", " ").title())
        
        self.console.print(table)
        
        # Auto-detect if .github exists
        default = "1" if (self.base_path / ".github").exists() else "3"
        
        choice = Prompt.ask(
            "Setup CI/CD?",
            choices=[str(i) for i in range(1, len(choices) + 1)],
            default=default
        )
        
        return choices[int(choice) - 1]
    
    def _ask_git_hooks(self) -> bool:
        """Ask about git hooks."""
        self.console.print("\n[bold]Step 8: Git hooks[/bold]")
        
        self.console.print("[dim]Pre-commit hooks to check docs before commits[/dim]")
        
        has_precommit = (self.base_path / ".pre-commit-config.yaml").exists()
        
        if has_precommit:
            self.console.print("[dim]Detected existing pre-commit config[/dim]")
        
        return Confirm.ask(
            "Setup pre-commit hooks?",
            default=has_precommit
        )
    
    def _ask_create_structure(self) -> bool:
        """Ask about creating documentation structure."""
        self.console.print("\n[bold]Step 9: Documentation structure[/bold]")
        
        docs_path = self.base_path / self.options.docs_location.replace("./", "") if self.options else self.base_path / "docs"
        
        if docs_path.exists():
            self.console.print(f"[dim]Documentation directory already exists at {docs_path}[/dim]")
            return False
        
        return Confirm.ask(
            "Create documentation directory structure?",
            default=True
        )
    
    def _confirm_summary(self) -> bool:
        """Show summary and get confirmation."""
        self.console.print("\n[bold]Summary[/bold]")
        
        table = Table(show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        
        table.add_row("Template", self.options.template)
        table.add_row("Project type", self.options.project_type.replace("-", " "))
        table.add_row("Docs location", self.options.docs_location)
        table.add_row("Code validation", "Yes" if self.options.validate_examples else "No")
        if self.options.validate_examples:
            table.add_row("  Languages", ", ".join(self.options.languages))
        table.add_row("Freshness tracking", "Yes" if self.options.enable_freshness else "No")
        table.add_row("Health badges", "Yes" if self.options.generate_badges else "No")
        table.add_row("CI/CD", self.options.setup_ci.replace("-", " ").title())
        table.add_row("Git hooks", "Yes" if self.options.setup_git_hooks else "No")
        table.add_row("Create structure", "Yes" if self.options.create_structure else "No")
        
        self.console.print(table)
        
        return Confirm.ask(
            "\nCreate these files?",
            default=True
        )
    
    def _create_files(self):
        """Create all selected files."""
        self.console.print("\n[bold]Creating files...[/bold]\n")
        
        created_files = []
        
        # 1. Create config file
        config_path = self._create_config()
        created_files.append(config_path)
        self.console.print(f"[green]✓[/green] Created {config_path}")
        
        # 2. Create docs structure
        if self.options.create_structure:
            docs_path = self._create_docs_structure()
            created_files.extend(docs_path)
        
        # 3. Create CI/CD workflow
        if self.options.setup_ci != "none":
            ci_path = self._create_ci_workflow()
            if ci_path:
                created_files.append(ci_path)
                self.console.print(f"[green]✓[/green] Created {ci_path}")
        
        # 4. Create pre-commit config
        if self.options.setup_git_hooks:
            hook_path = self._create_precommit_config()
            if hook_path:
                created_files.append(hook_path)
                self.console.print(f"[green]✓[/green] Updated {hook_path}")
        
        # 5. Create README template if none exists
        readme_path = self._create_readme_template()
        if readme_path:
            created_files.append(readme_path)
            self.console.print(f"[green]✓[/green] Created {readme_path}")
        
        # 6. Update .gitignore
        gitignore_path = self._update_gitignore()
        if gitignore_path:
            created_files.append(gitignore_path)
            self.console.print(f"[green]✓[/green] Updated {gitignore_path}")
        
        self.console.print(f"\n[bold green]Created {len(created_files)} files![/bold green]")
        self._print_next_steps()
    
    def _create_config(self) -> Path:
        """Create .clean-docs.yaml configuration file."""
        config = Config()
        
        # Apply template overrides
        template = self.TEMPLATES.get(self.options.template)
        if template and template.config_overrides:
            for section, values in template.config_overrides.items():
                if hasattr(config, section):
                    for key, value in values.items():
                        if hasattr(getattr(config, section), key):
                            setattr(getattr(config, section), key, value)
        
        # Apply user choices
        if self.options.validate_examples and self.options.languages:
            # Add to config
            pass
        
        config_path = self.base_path / ".clean-docs.yaml"
        config.save(config_path)
        return config_path
    
    def _create_docs_structure(self) -> List[Path]:
        """Create documentation directory structure."""
        docs_path = self.base_path / self.options.docs_location.replace("./", "")
        created = []
        
        # Main directories
        dirs = [
            docs_path,
            docs_path / "user-guide",
            docs_path / "api",
            docs_path / "examples",
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            created.append(dir_path)
            self.console.print(f"[green]✓[/green] Created directory {dir_path}")
        
        # Create README
        readme_content = f"""# Documentation

Welcome to the documentation!

## Structure

- `user-guide/` - User documentation and tutorials
- `api/` - API reference documentation  
- `examples/` - Code examples and sample usage

## Getting Started

Run documentation quality checks:

```bash
# Check all links
clean-docs scan .

# Fix broken links
clean-docs scan . --fix --dry-run

# Full health check
clean-docs analyze .
```
"""
        readme_path = docs_path / "README.md"
        readme_path.write_text(readme_content)
        created.append(readme_path)
        self.console.print(f"[green]✓[/green] Created {readme_path}")
        
        return created
    
    def _create_ci_workflow(self) -> Optional[Path]:
        """Create CI/CD workflow file."""
        if self.options.setup_ci == "github-actions":
            workflows_dir = self.base_path / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)
            
            workflow_content = """name: Documentation Quality

on:
  push:
    branches: [ main, master ]
    paths:
      - 'docs/**'
      - '*.md'
  pull_request:
    branches: [ main, master ]
    paths:
      - 'docs/**'
      - '*.md'

jobs:
  docs-quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install Clean Docs
        run: pip install clean-docs
      
      - name: Check documentation links
        run: clean-docs scan . --format json
        continue-on-error: true
      
      - name: Analyze documentation health
        run: clean-docs analyze . --report markdown
        continue-on-error: true
      
      - name: Upload results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: docs-health-report
          path: docs-health-report.md
"""
            workflow_path = workflows_dir / "docs-quality.yml"
            workflow_path.write_text(workflow_content)
            return workflow_path
            
        elif self.options.setup_ci == "gitlab-ci":
            gitlab_content = """# GitLab CI configuration for documentation quality
docs-check:
  image: python:3.12
  script:
    - pip install clean-docs
    - clean-docs scan . --format json > docs-report.json
    - clean-docs analyze . --report markdown
  artifacts:
    reports:
      junit: docs-report.json
    paths:
      - docs-health-report.md
  allow_failure: true
  only:
    - merge_requests
    - main
"""
            gitlab_path = self.base_path / ".gitlab-ci.yml"
            gitlab_path.write_text(gitlab_content)
            return gitlab_path
        
        return None
    
    def _create_precommit_config(self) -> Optional[Path]:
        """Create or update pre-commit configuration."""
        config_path = self.base_path / ".pre-commit-config.yaml"
        
        clean_docs_hook = {
            "repo": "local",
            "hooks": [{
                "id": "clean-docs",
                "name": "Check documentation links",
                "entry": "clean-docs scan .",
                "language": "system",
                "pass_filenames": False,
                "always_run": True,
            }]
        }
        
        if config_path.exists():
            # Append to existing
            content = config_path.read_text()
            if "clean-docs" not in content:
                # Simple append (would need proper YAML handling for production)
                content += f"\n# Clean Docs hook\n{str(clean_docs_hook)}\n"
                config_path.write_text(content)
            return config_path
        else:
            # Create new
            content = """repos:
  - repo: local
    hooks:
      - id: clean-docs
        name: Check documentation links
        entry: clean-docs scan .
        language: system
        pass_filenames: false
        always_run: true
"""
            config_path.write_text(content)
            return config_path
        
        return None
    
    def _create_readme_template(self) -> Optional[Path]:
        """Create README.md template if none exists."""
        readme_path = self.base_path / "README.md"
        
        if readme_path.exists():
            return None
        
        badges = ""
        if self.options.generate_badges:
            badges = """[![Docs Health](https://img.shields.io/badge/docs-health%20check-blue)](https://github.com/yourusername/yourrepo/actions)
[![Links](https://img.shields.io/badge/links-checked-green)]()

"""
        
        content = f"""# Project Name

{ badges }Brief description of your project.

## Installation

```bash
pip install your-package
```

## Quick Start

```python
# Add a quick example here
import your_package

result = your_package.do_something()
print(result)
```

## Documentation

Full documentation is available in the [docs/](docs/) directory.

## Development

Run documentation quality checks:

```bash
# Check all documentation links
clean-docs scan .

# Fix broken links (dry-run first)
clean-docs scan . --fix --dry-run

# Full health analysis
clean-docs analyze .
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License - see [LICENSE](LICENSE) file.
"""
        
        readme_path.write_text(content)
        return readme_path
    
    def _update_gitignore(self) -> Optional[Path]:
        """Update .gitignore with Clean Docs patterns."""
        gitignore_path = self.base_path / ".gitignore"
        
        patterns = [
            "",
            "# Clean Docs",
            ".clean-docs-cache/",
            "*.clean-docs.db",
            "docs-health-report.*",
        ]
        
        if gitignore_path.exists():
            content = gitignore_path.read_text()
            if "# Clean Docs" not in content:
                content += "\n".join(patterns) + "\n"
                gitignore_path.write_text(content)
        else:
            content = "\n".join(patterns[1:]) + "\n"  # Skip empty first line
            gitignore_path.write_text(content)
        
        return gitignore_path
    
    def _print_next_steps(self):
        """Print next steps for the user."""
        self.console.print("\n[bold cyan]Next Steps:[/bold cyan]\n")
        
        steps = [
            "1. Review [bold].clean-docs.yaml[/bold] and customize settings",
            "2. Run [bold]clean-docs doctor[/bold] to verify setup",
            "3. Run [bold]clean-docs scan .[/bold] to check current state",
        ]
        
        if self.options.setup_ci == "github-actions":
            steps.append("4. Push to GitHub to trigger first CI run")
        
        if self.options.setup_git_hooks:
            steps.append("5. Install pre-commit hooks: [bold]pre-commit install[/bold]")
        
        steps.append(f"\nSee [bold]{self.options.docs_location}/README.md[/bold] for detailed documentation")
        
        for step in steps:
            self.console.print(step)
        
        self.console.print(f"\n[green bold]Happy documenting! 📝[/green bold]\n")
