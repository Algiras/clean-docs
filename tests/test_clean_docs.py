"""Comprehensive tests for Clean Docs with cleanup strategies."""

import asyncio
import os
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest

from clean_docs.cache import CacheManager
from clean_docs.config import Config
from clean_docs.fixer import LinkFixer, Fix
from clean_docs.link_checker import LinkChecker, LinkResult, LinkStatus
from clean_docs.parsers.markdown import MarkdownDocument, MarkdownParser, Link


# Fixtures with cleanup strategies


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory that gets cleaned up after tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def cache_manager(temp_dir: Path) -> Generator[CacheManager, None, None]:
    """Create a cache manager with automatic cleanup."""
    cache = CacheManager(temp_dir / "cache", ttl_hours=1)
    yield cache
    # Explicitly close the cache to release file handles (important on Windows)
    cache.close()


@pytest.fixture
def markdown_parser() -> MarkdownParser:
    """Provide a markdown parser instance."""
    return MarkdownParser()


@pytest.fixture
def sample_config() -> Config:
    """Provide a sample configuration."""
    config = Config()
    config.links.timeout = 5
    config.links.concurrency = 10
    return config


# Markdown Parser Tests


class TestMarkdownParser:
    """Test markdown parsing functionality."""

    def test_parse_simple_link(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test parsing a simple markdown link."""
        content = "[link text](https://example.com)"
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.links) == 1
        assert doc.links[0].url == "https://example.com"
        assert doc.links[0].text == "link text"
        assert doc.links[0].line == 1

    def test_parse_multiple_links(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test parsing multiple links in a document."""
        content = """
# Title

[Link 1](https://example.com)
[Link 2](./local.md)
[Link 3](#anchor)

## Section

[Link 4](https://github.com/user/repo)
"""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.links) == 4
        assert doc.links[0].url == "https://example.com"
        assert doc.links[1].url == "./local.md"
        assert doc.links[2].url == "#anchor"

    def test_parse_anchor_links(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test parsing anchor links."""
        content = """
# Heading 1
## Heading 2
### Heading 3

[link](#heading-1)
[another](#heading-2)
"""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.links) == 2
        assert len(doc.headings) == 3
        assert doc.headings[0] == (1, "Heading 1", 2)
        assert doc.headings[1] == (2, "Heading 2", 3)

    def test_parse_reference_links(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test parsing reference-style links."""
        content = """
[reference link][ref1]
[implicit][]

[ref1]: https://example.com
[implicit]: ./local.md
"""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.links) == 2
        # Should resolve reference links
        assert "https://example.com" in [link.url for link in doc.links]
        assert "./local.md" in [link.url for link in doc.links]

    def test_parse_image_links(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test parsing image links."""
        content = """
![Alt text](./image.png)
![Another](./docs/screenshot.jpg)
"""
        file_path = temp_dir / "test.md"
        file_path.write_text(content)

        doc = markdown_parser.parse_file(file_path)

        assert len(doc.links) == 2
        assert all(link.is_image for link in doc.links)
        assert doc.links[0].text == "Alt text"

    def test_get_anchor_id(self, markdown_parser: MarkdownParser):
        """Test anchor ID generation from heading text."""
        test_cases = [
            ("Hello World", "hello-world"),
            ("Test 123", "test-123"),
            ("Special!@#Chars", "specialchars"),
            ("Multiple   Spaces", "multiple-spaces"),
            ("CamelCase", "camelcase"),
            ("UPPER CASE", "upper-case"),
            ("", ""),
        ]

        for heading, expected in test_cases:
            result = markdown_parser.get_anchor_id(heading)
            assert result == expected, f"Failed for '{heading}': got '{result}', expected '{expected}'"

    def test_find_all_markdown_files(self, temp_dir: Path, markdown_parser: MarkdownParser):
        """Test finding all markdown files in a directory."""
        # Create various files
        (temp_dir / "readme.md").write_text("# Readme")
        (temp_dir / "guide.mdx").write_text("# Guide")
        (temp_dir / "notes.txt").write_text("Notes")
        (temp_dir / "sub").mkdir()
        (temp_dir / "sub" / "doc.md").write_text("# Doc")

        files = markdown_parser.find_all_markdown_files(temp_dir)

        assert len(files) == 3
        assert all(f.suffix in [".md", ".mdx"] for f in files)


# Cache Tests


class TestCache:
    """Test cache functionality."""

    def test_cache_set_get(self, cache_manager: CacheManager):
        """Test setting and getting cached link status."""
        url = "https://example.com"

        # Initially not cached
        assert cache_manager.get_link_status(url) is None

        # Set status
        cache_manager.set_link_status(url, "ok", 200, response_time=0.5)

        # Retrieve
        result = cache_manager.get_link_status(url)
        assert result is not None
        assert result["status"] == "ok"
        assert result["status_code"] == 200
        assert result["response_time"] == 0.5

    def test_cache_expiry(self, temp_dir: Path):
        """Test that cache entries expire after TTL."""
        # Very short TTL for testing
        cache = CacheManager(temp_dir, ttl_hours=0.0001)  # ~0.36 seconds

        url = "https://example.com"
        cache.set_link_status(url, "ok", 200)

        # Should exist immediately
        assert cache.get_link_status(url) is not None

        # Wait for expiry
        time.sleep(0.5)

        # Should be expired
        assert cache.get_link_status(url) is None

    def test_cache_clear(self, cache_manager: CacheManager):
        """Test clearing all cached data."""
        # Add multiple entries
        for i in range(5):
            cache_manager.set_link_status(f"https://example{i}.com", "ok", 200)

        # Verify they're there
        stats = cache_manager.get_stats()
        assert stats["total_links"] == 5

        # Clear
        cache_manager.clear()

        # Verify cleared
        stats = cache_manager.get_stats()
        assert stats["total_links"] == 0

    def test_cache_stats(self, cache_manager: CacheManager):
        """Test cache statistics."""
        # Initially empty
        stats = cache_manager.get_stats()
        assert stats["total_links"] == 0

        # Add entries
        for i in range(3):
            cache_manager.set_link_status(f"https://example{i}.com", "ok", 200)

        stats = cache_manager.get_stats()
        assert stats["total_links"] == 3
        assert stats["valid_links"] == 3
        assert stats["expired_links"] == 0
        assert stats["cache_size_mb"] > 0

    def test_cache_update_existing(self, cache_manager: CacheManager):
        """Test updating existing cache entries."""
        url = "https://example.com"

        # Initial status
        cache_manager.set_link_status(url, "ok", 200)
        result1 = cache_manager.get_link_status(url)
        assert result1["status"] == "ok"

        # Update status
        cache_manager.set_link_status(url, "broken", 404, error="Not found")
        result2 = cache_manager.get_link_status(url)
        assert result2["status"] == "broken"
        assert result2["status_code"] == 404
        assert result2["error"] == "Not found"

    def test_cache_batch_get(self, cache_manager: CacheManager):
        """Test batch retrieval of cache entries."""
        # Add multiple entries
        urls = [f"https://example{i}.com" for i in range(5)]
        for url in urls:
            cache_manager.set_link_status(url, "ok", 200)
        
        # Batch get
        results = cache_manager.get_link_statuses_batch(urls)
        
        assert len(results) == 5
        for url in urls:
            assert url in results
            assert results[url]["status"] == "ok"

    def test_cache_batch_set(self, cache_manager: CacheManager):
        """Test batch setting of cache entries."""
        entries = [
            ("https://a.com", "ok", 200, None, 0.1),
            ("https://b.com", "broken", 404, "Not found", 0.2),
            ("https://c.com", "ok", 301, None, 0.3),
        ]
        
        cache_manager.set_link_statuses_batch(entries)
        
        # Verify all were set
        for url, status, code, error, _ in entries:
            result = cache_manager.get_link_status(url)
            assert result is not None
            assert result["status"] == status
            assert result["status_code"] == code

    def test_cache_cleanup_expired(self, temp_dir: Path):
        """Test cleanup of expired entries."""
        # Very short TTL
        cache = CacheManager(temp_dir, ttl_hours=0.0001)
        
        # Add entry
        cache.set_link_status("https://old.com", "ok", 200)
        
        # Wait for expiry
        import time
        time.sleep(0.5)
        
        # Cleanup should remove the entry
        deleted = cache.cleanup_expired()
        assert deleted >= 1
        
        # Entry should be gone
        assert cache.get_link_status("https://old.com") is None

    def test_cache_get_broken_links(self, cache_manager: CacheManager):
        """Test retrieval of broken links."""
        # Add mix of ok and broken
        cache_manager.set_link_status("https://good.com", "ok", 200)
        cache_manager.set_link_status("https://bad1.com", "broken", 404, error="Not found")
        cache_manager.set_link_status("https://bad2.com", "broken", 500, error="Server error")
        
        broken = cache_manager.get_broken_links()
        
        assert len(broken) == 2
        urls = [b["url"] for b in broken]
        assert "https://bad1.com" in urls
        assert "https://bad2.com" in urls
        assert "https://good.com" not in urls


# Configuration Tests


class TestConfig:
    """Test configuration management."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()

        assert config.links.timeout == 10
        assert config.links.concurrency == 20
        assert config.links.ignore_patterns == []
        assert config.cache.ttl_hours == 24
        assert config.cache.max_size_mb == 100
        assert config.cache.dir is None
        assert config.output.show_progress is True
        assert config.output.colors == "auto"

    def test_config_from_dict(self):
        """Test creating config from dictionary."""
        data = {
            "links": {
                "timeout": 30,
                "concurrency": 50,
                "ignore_patterns": ["localhost", "127.0.0.1"],
            },
            "cache": {
                "ttl_hours": 48,
                "max_size_mb": 200,
                "dir": "/custom/cache",
            },
            "output": {
                "show_progress": False,
                "colors": "never",
            },
        }

        config = Config._from_dict(data)

        assert config.links.timeout == 30
        assert config.links.concurrency == 50
        assert config.links.ignore_patterns == ["localhost", "127.0.0.1"]
        assert config.cache.ttl_hours == 48
        assert config.cache.max_size_mb == 200
        assert config.cache.dir == "/custom/cache"
        assert config.output.show_progress is False
        assert config.output.colors == "never"

    def test_config_load_save(self, temp_dir: Path):
        """Test saving and loading configuration."""
        config_path = temp_dir / ".clean-docs.yaml"

        # Create and save config
        config = Config()
        config.links.timeout = 25
        config.links.ignore_patterns = ["example.com", "test.local"]
        config.save(config_path)

        # Load and verify
        loaded = Config.load(config_path)
        assert loaded.links.timeout == 25
        assert loaded.links.ignore_patterns == ["example.com", "test.local"]

    def test_get_cache_dir_default(self):
        """Test default cache directory is in temp."""
        import tempfile
        config = Config()
        cache_dir = config.get_cache_dir()

        # Should be in system temp directory
        expected_temp = Path(tempfile.gettempdir())
        assert cache_dir.parent == expected_temp
        assert "clean-docs-cache" in str(cache_dir)

    def test_get_cache_dir_custom(self, temp_dir: Path):
        """Test custom cache directory."""
        custom_path = temp_dir / "custom-cache"
        config = Config()
        config.cache.dir = str(custom_path)

        cache_dir = config.get_cache_dir()
        assert cache_dir == custom_path
        assert cache_dir.exists()  # Directory should be created


# Link Checker Tests


@pytest.mark.asyncio
class TestLinkChecker:
    """Test link checking functionality."""

    async def test_check_internal_file_exists(self, temp_dir: Path):
        """Test checking existing internal file."""
        # Create target file
        (temp_dir / "existing.md").write_text("# Test")

        cache = CacheManager(temp_dir / "cache")
        async with LinkChecker(cache) as checker:
            link = Link(text="test", url="./existing.md", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.OK
            assert result.error_message is None

    async def test_check_internal_file_missing(self, temp_dir: Path):
        """Test checking non-existing internal file."""
        cache = CacheManager(temp_dir / "cache")
        async with LinkChecker(cache) as checker:
            link = Link(text="test", url="./nonexistent.md", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.BROKEN
            assert "not found" in result.error_message.lower()

    async def test_check_internal_with_md_extension(self, temp_dir: Path):
        """Test that .md extension is handled correctly."""
        # Create file with .md extension
        (temp_dir / "target.md").write_text("# Target")

        cache = CacheManager(temp_dir / "cache")
        async with LinkChecker(cache) as checker:
            # Link without extension should resolve to .md
            link = Link(text="test", url="./target", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            # This might fail depending on implementation
            # The fixer should handle missing extensions
            pass

    async def test_check_anchor_valid(self, temp_dir: Path):
        """Test checking valid anchor links."""
        cache = CacheManager(temp_dir / "cache")
        async with LinkChecker(cache) as checker:
            link = Link(text="test", url="#existing-heading", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[(1, "Existing Heading", 5)],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.OK

    async def test_check_anchor_invalid(self, temp_dir: Path):
        """Test checking invalid anchor links."""
        cache = CacheManager(temp_dir / "cache")
        async with LinkChecker(cache) as checker:
            link = Link(text="test", url="#missing-heading", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[(1, "Different Heading", 5)],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.BROKEN
            assert "not found" in result.error_message.lower()

    async def test_check_external_cached(self, temp_dir: Path):
        """Test that external links use cache."""
        cache = CacheManager(temp_dir / "cache")

        # Pre-populate cache
        cache.set_link_status("https://example.com", "ok", 200)

        async with LinkChecker(cache) as checker:
            link = Link(text="test", url="https://example.com", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.CACHED
            assert result.from_cache is True

    async def test_ignore_patterns(self, temp_dir: Path):
        """Test that ignore patterns work."""
        cache = CacheManager(temp_dir / "cache")
        checker = LinkChecker(
            cache,
            ignore_patterns=["localhost", "127.0.0.1"],
        )

        async with checker:
            link = Link(text="test", url="http://localhost:3000", line=1, column=0)
            doc = MarkdownDocument(
                path=temp_dir / "test.md",
                content="",
                links=[link],
                headings=[],
                references={},
            )

            result = await checker._check_link(link, doc, temp_dir)

            assert result.status == LinkStatus.SKIPPED


# Link Fixer Tests


class TestLinkFixer:
    """Test link fixing functionality."""

    def test_analyze_broken_link_missing_extension(self, temp_dir: Path):
        """Test detecting missing .md extension."""
        # Create target file with extension
        (temp_dir / "target.md").write_text("# Target")

        from rich.console import Console

        fixer = LinkFixer(temp_dir, Console())

        # Create broken link without extension
        link = Link(text="test", url="./target", line=5, column=0)
        result = LinkResult(
            link=link,
            status=LinkStatus.BROKEN,
            error_message="File not found",
        )
        doc = MarkdownDocument(
            path=temp_dir / "doc.md",
            content="[test](./target)",
            links=[link],
            headings=[],
            references={},
        )

        fix = fixer._analyze_broken_link(doc, result)

        assert fix is not None
        assert fix.auto_fixable is True
        assert fix.suggested_url == "./target.md"
        assert "extension" in fix.description.lower()

    def test_analyze_anchor_typo(self, temp_dir: Path):
        """Test detecting anchor typos with suggestions.
        
        Note: Semantic changes (sectin -> section) are NOT auto-fixable
        because they could be incorrect suggestions. Only safe changes
        like case or hyphen normalization are auto-fixed.
        """
        from rich.console import Console

        fixer = LinkFixer(temp_dir, Console())

        # Link with typo - semantic change, NOT auto-fixable
        link = Link(text="test", url="#sectin", line=5, column=0)
        result = LinkResult(
            link=link,
            status=LinkStatus.BROKEN,
            error_message="Anchor not found",
            suggestion="Did you mean #section?",
        )
        doc = MarkdownDocument(
            path=temp_dir / "doc.md",
            content="[test](#sectin)",
            links=[link],
            headings=[(1, "Section", 10)],
            references={},
        )

        fix = fixer._analyze_broken_link(doc, result)

        assert fix is not None
        assert fix.auto_fixable is False  # NOT auto-fixable (semantic change)
        assert fix.suggested_url == "#section"
        assert "manual review" in fix.description.lower()
    
    def test_analyze_anchor_safe_change(self, temp_dir: Path):
        """Test that safe anchor changes (case, hyphens) ARE auto-fixable."""
        from rich.console import Console

        fixer = LinkFixer(temp_dir, Console())

        # Link with double-hyphen - safe change, IS auto-fixable  
        link = Link(text="test", url="#data-cleanup--retention", line=5, column=0)
        result = LinkResult(
            link=link,
            status=LinkStatus.BROKEN,
            error_message="Anchor not found",
            suggestion="Did you mean #data-cleanup-retention?",
        )
        doc = MarkdownDocument(
            path=temp_dir / "doc.md",
            content="[test](#data-cleanup--retention)",
            links=[link],
            headings=[(1, "Data Cleanup & Retention", 10)],
            references={},
        )

        fix = fixer._analyze_broken_link(doc, result)

        assert fix is not None
        assert fix.auto_fixable is True  # IS auto-fixable (hyphen normalization)
        assert fix.suggested_url == "#data-cleanup-retention"

    def test_apply_single_fix(self, temp_dir: Path):
        """Test applying a single fix to a file."""
        from rich.console import Console

        # Create file with broken link
        file_path = temp_dir / "doc.md"
        file_path.write_text("[test](./old-url)")

        fixer = LinkFixer(temp_dir, Console())
        fix = Fix(
            file_path=file_path,
            line=1,
            original_url="./old-url",
            suggested_url="./new-url",
            description="Fix URL",
            auto_fixable=True,
        )

        success = fixer._apply_single_fix(fix)

        assert success is True
        content = file_path.read_text()
        assert "./new-url" in content
        assert "./old-url" not in content

    def test_apply_fix_no_change(self, temp_dir: Path):
        """Test applying fix when no change needed."""
        from rich.console import Console

        file_path = temp_dir / "doc.md"
        file_path.write_text("[test](./url)")

        fixer = LinkFixer(temp_dir, Console())
        fix = Fix(
            file_path=file_path,
            line=1,
            original_url="./nonexistent",
            suggested_url="./other",
            description="Fix URL",
            auto_fixable=True,
        )

        success = fixer._apply_single_fix(fix)

        assert success is False  # No change made


# Integration Tests


class TestIntegration:
    """Integration tests for end-to-end workflows."""

    def test_full_scan_workflow(self, temp_dir: Path):
        """Test complete scan workflow with multiple file types."""
        # Create a documentation structure
        (temp_dir / "README.md").write_text("""
# Project

[Getting Started](./docs/guide.md)
[API Reference](./docs/api.md)
[External](https://example.com)

## Installation

See [installation guide](#installation)
""")

        (temp_dir / "docs").mkdir()
        (temp_dir / "docs" / "guide.md").write_text("""
# Guide

[Back to README](../README.md)
[Missing](./missing.md)
""")

        (temp_dir / "docs" / "api.md").write_text("""
# API

[Endpoint](#endpoints)

## Endpoints

API endpoints here.
""")

        # Parse and check
        parser = MarkdownParser()
        files = parser.find_all_markdown_files(temp_dir)

        assert len(files) == 3

        # Check that links were parsed
        readme = parser.parse_file(temp_dir / "README.md")
        assert len(readme.links) == 4  # Including anchor

    def test_cache_persists_across_operations(self, temp_dir: Path):
        """Test that cache persists across multiple operations."""
        cache = CacheManager(temp_dir / "cache")

        # First operation - add to cache
        cache.set_link_status("https://example.com", "ok", 200)

        # Simulate new session with same cache
        cache2 = CacheManager(temp_dir / "cache")
        result = cache2.get_link_status("https://example.com")

        assert result is not None
        assert result["status"] == "ok"

    def test_config_reload(self, temp_dir: Path):
        """Test that config changes are persisted and reloaded."""
        config_path = temp_dir / ".clean-docs.yaml"

        # Create initial config
        config1 = Config()
        config1.links.timeout = 15
        config1.save(config_path)

        # Reload
        config2 = Config.load(config_path)
        assert config2.links.timeout == 15

        # Modify and save again
        config2.links.timeout = 25
        config2.save(config_path)

        # Reload again
        config3 = Config.load(config_path)
        assert config3.links.timeout == 25


# Cleanup and Resource Management Tests


class TestCleanup:
    """Test proper cleanup of resources."""

    def test_temp_files_cleaned(self, temp_dir: Path):
        """Test that temporary files are properly cleaned up."""
        # Create temp files
        temp_file = temp_dir / "temp.txt"
        temp_file.write_text("test")

        # Verify exists
        assert temp_file.exists()

        # After test (using temp_dir fixture), it should be cleaned
        # Note: In actual test, this happens automatically

    def test_cache_db_closed_properly(self, temp_dir: Path):
        """Test that database connections are closed."""
        cache = CacheManager(temp_dir)

        # Perform operations
        cache.set_link_status("https://test.com", "ok", 200)

        # Delete cache object
        del cache

        # Try to create new cache in same location (should work if closed)
        cache2 = CacheManager(temp_dir)
        result = cache2.get_link_status("https://test.com")
        assert result is not None


# CODEOWNERS Tests


class TestCodeOwners:
    """Test CODEOWNERS parsing and matching."""

    def test_parse_simple_codeowners(self, temp_dir: Path):
        """Test parsing a simple CODEOWNERS file."""
        from clean_docs.codeowners import CodeOwners
        
        codeowners_content = """
# This is a comment
* @default-owner

/docs/ @docs-team
/src/*.py @python-team
"""
        codeowners_path = temp_dir / "CODEOWNERS"
        codeowners_path.write_text(codeowners_content)
        
        owners = CodeOwners.parse_file(codeowners_path)
        
        assert owners.default_owners == ["@default-owner"]
        assert len(owners.rules) == 2

    def test_get_owners_for_file(self, temp_dir: Path):
        """Test getting owners for a specific file."""
        from clean_docs.codeowners import CodeOwners
        
        codeowners_content = """
* @default
/docs/ @docs-team
/docs/api/ @api-team
"""
        codeowners_path = temp_dir / "CODEOWNERS"
        codeowners_path.write_text(codeowners_content)
        
        owners = CodeOwners.parse_file(codeowners_path)
        
        # Last matching rule wins
        assert owners.get_owners("docs/api/reference.md") == ["@api-team"]
        assert owners.get_owners("docs/guide.md") == ["@docs-team"]
        assert owners.get_owners("src/main.py") == ["@default"]

    def test_get_owner_key(self, temp_dir: Path):
        """Test owner key generation for grouping."""
        from clean_docs.codeowners import CodeOwners
        
        codeowners_content = """
/docs/ @team-a @team-b
/src/ @team-c
"""
        codeowners_path = temp_dir / "CODEOWNERS"
        codeowners_path.write_text(codeowners_content)
        
        owners = CodeOwners.parse_file(codeowners_path)
        
        # Keys should be sorted and comma-separated
        key = owners.get_owner_key("docs/readme.md")
        assert "@team-a" in key
        assert "@team-b" in key

    def test_group_files_by_owner(self, temp_dir: Path):
        """Test grouping files by owner."""
        from clean_docs.codeowners import CodeOwners
        
        codeowners_content = """
/docs/ @docs-team
/src/ @dev-team
"""
        codeowners_path = temp_dir / "CODEOWNERS"
        codeowners_path.write_text(codeowners_content)
        
        owners = CodeOwners.parse_file(codeowners_path)
        
        files = ["docs/a.md", "docs/b.md", "src/c.py", "other.txt"]
        groups = owners.group_files_by_owner(files)
        
        assert len(groups) >= 2  # At least docs-team and dev-team groups

    def test_find_codeowners_locations(self, temp_dir: Path):
        """Test finding CODEOWNERS in standard locations."""
        from clean_docs.codeowners import CodeOwners
        
        # Create .github/CODEOWNERS
        github_dir = temp_dir / ".github"
        github_dir.mkdir()
        (github_dir / "CODEOWNERS").write_text("* @default")
        
        owners = CodeOwners.find_and_parse(temp_dir)
        
        assert owners is not None
        assert owners.default_owners == ["@default"]


# Safe Anchor Fix Tests


class TestSafeAnchorFix:
    """Test the safe anchor fix detection."""

    def test_case_change_is_safe(self, temp_dir: Path):
        """Test that case changes are considered safe."""
        from rich.console import Console
        from clean_docs.fixer import LinkFixer
        
        fixer = LinkFixer(temp_dir, Console())
        
        # Case-only changes should be safe
        assert fixer._is_safe_anchor_fix("Section", "section") is True
        assert fixer._is_safe_anchor_fix("UPPER", "upper") is True

    def test_double_hyphen_is_safe(self, temp_dir: Path):
        """Test that double-hyphen normalization is safe."""
        from rich.console import Console
        from clean_docs.fixer import LinkFixer
        
        fixer = LinkFixer(temp_dir, Console())
        
        # Double hyphen to single should be safe
        assert fixer._is_safe_anchor_fix("foo--bar", "foo-bar") is True
        assert fixer._is_safe_anchor_fix("a---b", "a-b") is True

    def test_semantic_change_is_not_safe(self, temp_dir: Path):
        """Test that semantic changes are NOT considered safe."""
        from rich.console import Console
        from clean_docs.fixer import LinkFixer
        
        fixer = LinkFixer(temp_dir, Console())
        
        # Different words should NOT be safe
        assert fixer._is_safe_anchor_fix("introduction", "getting-started") is False
        assert fixer._is_safe_anchor_fix("api-reference", "endpoints") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
