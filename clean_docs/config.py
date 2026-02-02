"""Configuration management for Clean Docs."""

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


@dataclass
class LinkConfig:
    timeout: int = 10
    concurrency: int = 20
    ignore_patterns: List[str] = field(default_factory=list)


@dataclass
class CacheConfig:
    ttl_hours: int = 24
    max_size_mb: int = 100
    dir: Optional[str] = None


@dataclass
class OutputConfig:
    show_progress: bool = True
    colors: str = "auto"


@dataclass
class Config:
    links: LinkConfig = field(default_factory=LinkConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load config from file or create default."""
        if path is None:
            # Look for config in current directory
            for filename in [".clean-docs.yaml", ".clean-docs.yml", "clean-docs.yaml"]:
                config_path = Path(filename)
                if config_path.exists():
                    path = config_path
                    break
        
        if path and path.exists():
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            return cls._from_dict(data)
        
        return cls()
    
    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from dictionary."""
        links_data = data.get("links", {})
        cache_data = data.get("cache", {})
        output_data = data.get("output", {})
        
        return cls(
            links=LinkConfig(
                timeout=links_data.get("timeout", 10),
                concurrency=links_data.get("concurrency", 20),
                ignore_patterns=links_data.get("ignore_patterns", []),
            ),
            cache=CacheConfig(
                ttl_hours=cache_data.get("ttl_hours", 24),
                max_size_mb=cache_data.get("max_size_mb", 100),
                dir=cache_data.get("dir"),
            ),
            output=OutputConfig(
                show_progress=output_data.get("show_progress", True),
                colors=output_data.get("colors", "auto"),
            ),
        )
    
    def save(self, path: Path) -> None:
        """Save config to file."""
        data = {
            "links": {
                "timeout": self.links.timeout,
                "concurrency": self.links.concurrency,
                "ignore_patterns": self.links.ignore_patterns,
            },
            "cache": {
                "ttl_hours": self.cache.ttl_hours,
                "max_size_mb": self.cache.max_size_mb,
            },
            "output": {
                "show_progress": self.output.show_progress,
                "colors": self.output.colors,
            },
        }
        
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    def get_cache_dir(self) -> Path:
        """Get cache directory path.
        
        Uses system temp directory by default:
        - Unix: /tmp/clean-docs-cache/
        - Windows: %TEMP%/clean-docs-cache/
        
        Can be overridden via config.
        """
        if self.cache.dir:
            return Path(self.cache.dir)
        
        # Use system temp directory
        temp_dir = Path(tempfile.gettempdir()) / "clean-docs-cache"
        return temp_dir


DEFAULT_CONFIG_CONTENT = '''# Clean Docs Configuration
# Generated automatically - customize as needed

links:
  timeout: 10                    # HTTP request timeout in seconds
  concurrency: 20                # Concurrent link checks
  ignore_patterns:               # URL patterns to skip
    - "localhost"
    - "127.0.0.1"
    - "example.com"

cache:
  ttl_hours: 24                  # How long to cache link status
  max_size_mb: 100               # Max cache size

output:
  show_progress: true            # Show progress bars
  colors: auto                   # auto/always/never
'''
