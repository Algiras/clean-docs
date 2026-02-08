"""Configuration management for Clean Docs with validation."""

import tempfile
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails."""
    pass


@dataclass
class LinkConfig:
    timeout: int = 10
    concurrency: int = 20
    ignore_patterns: List[str] = field(default_factory=list)
    
    def validate(self) -> None:
        """Validate link configuration values."""
        if not isinstance(self.timeout, int) or self.timeout < 1:
            raise ConfigValidationError(
                f"Invalid timeout: {self.timeout}. Must be a positive integer (seconds)."
            )
        if not isinstance(self.concurrency, int) or self.concurrency < 1:
            raise ConfigValidationError(
                f"Invalid concurrency: {self.concurrency}. Must be a positive integer."
            )
        if not isinstance(self.ignore_patterns, list):
            raise ConfigValidationError(
                f"Invalid ignore_patterns: {self.ignore_patterns}. Must be a list of strings."
            )


@dataclass
class CacheConfig:
    ttl_hours: int = 24
    max_size_mb: int = 100
    dir: Optional[str] = None
    
    def validate(self) -> None:
        """Validate cache configuration values."""
        if not isinstance(self.ttl_hours, int) or self.ttl_hours < 1:
            raise ConfigValidationError(
                f"Invalid ttl_hours: {self.ttl_hours}. Must be a positive integer."
            )
        if not isinstance(self.max_size_mb, int) or self.max_size_mb < 1:
            raise ConfigValidationError(
                f"Invalid max_size_mb: {self.max_size_mb}. Must be a positive integer."
            )


@dataclass
class OutputConfig:
    show_progress: bool = True
    colors: str = "auto"
    
    def validate(self) -> None:
        """Validate output configuration values."""
        valid_colors = ["auto", "always", "never"]
        if self.colors not in valid_colors:
            raise ConfigValidationError(
                f"Invalid colors: {self.colors}. Must be one of: {', '.join(valid_colors)}"
            )


@dataclass
class Config:
    links: LinkConfig = field(default_factory=LinkConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    output: OutputConfig = field(default_factory=OutputConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load config from file or create default.
        
        Args:
            path: Explicit path to config file. If provided but doesn't exist,
                  raises FileNotFoundError.
        
        Returns:
            Config object with loaded or default values.
            
        Raises:
            FileNotFoundError: If explicit path doesn't exist.
            ConfigValidationError: If config values are invalid.
            ValueError: If YAML is malformed.
        """
        if path:
            if not path.exists():
                raise FileNotFoundError(f"Config file not found: {path}")
            return cls._load_from_file(path)
        
        # Look for config in current directory
        for filename in [".clean-docs.yaml", ".clean-docs.yml", "clean-docs.yaml"]:
            config_path = Path(filename)
            if config_path.exists():
                return cls._load_from_file(config_path)
        
        return cls()
    
    @classmethod
    def _load_from_file(cls, path: Path) -> "Config":
        """Load and validate config from a file."""
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in config file {path}: {e}")
        
        # Check for unknown keys
        known_keys = {"links", "cache", "output"}
        unknown_keys = set(data.keys()) - known_keys
        if unknown_keys:
            warnings.warn(
                f"Unknown config keys in {path}: {', '.join(unknown_keys)}. "
                f"Known keys are: {', '.join(known_keys)}"
            )
        
        return cls._from_dict(data)
    
    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        """Create Config from dictionary with validation."""
        links_data = data.get("links", {})
        cache_data = data.get("cache", {})
        output_data = data.get("output", {})
        
        config = cls(
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
        
        # Validate all sections
        config.validate()
        
        return config
    
    def validate(self) -> None:
        """Validate entire configuration."""
        self.links.validate()
        self.cache.validate()
        self.output.validate()
    
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
            path = Path(self.cache.dir)
        else:
            path = Path(tempfile.gettempdir()) / "clean-docs-cache"
        
        # Ensure directory exists
        path.mkdir(parents=True, exist_ok=True)
        return path


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
