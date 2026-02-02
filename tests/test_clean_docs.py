"""Tests for Clean Docs."""

import pytest
from pathlib import Path
from clean_docs.parsers.markdown import MarkdownParser, Link
from clean_docs.cache import CacheManager
from clean_docs.config import Config


class TestMarkdownParser:
    """Test markdown parsing."""
    
    def test_parse_simple_link(self, tmp_path):
        """Test parsing a simple markdown link."""
        content = "[link text](https://example.com)"
        file_path = tmp_path / "test.md"
        file_path.write_text(content)
        
        parser = MarkdownParser()
        doc = parser.parse_file(file_path)
        
        assert len(doc.links) == 1
        assert doc.links[0].url == "https://example.com"
        assert doc.links[0].text == "link text"
    
    def test_parse_anchor_link(self, tmp_path):
        """Test parsing anchor links."""
        content = """
# Heading 1
## Heading 2
[link](#heading-1)
"""
        file_path = tmp_path / "test.md"
        file_path.write_text(content)
        
        parser = MarkdownParser()
        doc = parser.parse_file(file_path)
        
        assert len(doc.links) == 1
        assert doc.links[0].url == "#heading-1"
        assert len(doc.headings) == 2
    
    def test_get_anchor_id(self):
        """Test anchor ID generation."""
        parser = MarkdownParser()
        
        assert parser.get_anchor_id("Hello World") == "hello-world"
        assert parser.get_anchor_id("Test 123") == "test-123"
        assert parser.get_anchor_id("Special!@#Chars") == "specialchars"


class TestCache:
    """Test cache functionality."""
    
    def test_cache_set_get(self, tmp_path):
        """Test setting and getting from cache."""
        cache = CacheManager(tmp_path, ttl_hours=1)
        
        # Set a link status
        cache.set_link_status("https://example.com", "ok", 200)
        
        # Get it back
        result = cache.get_link_status("https://example.com")
        
        assert result is not None
        assert result["status"] == "ok"
        assert result["status_code"] == 200
    
    def test_cache_expiry(self, tmp_path):
        """Test cache expiry."""
        import time
        
        # Create cache with very short TTL
        cache = CacheManager(tmp_path, ttl_hours=0.0001)  # ~0.36 seconds
        
        # Set a value
        cache.set_link_status("https://example.com", "ok", 200)
        
        # Should exist immediately
        result = cache.get_link_status("https://example.com")
        assert result is not None
        
        # Wait for expiry
        time.sleep(0.5)
        
        # Should be expired now
        result = cache.get_link_status("https://example.com")
        assert result is None


class TestConfig:
    """Test configuration."""
    
    def test_default_config(self):
        """Test default configuration."""
        config = Config()
        
        assert config.links.timeout == 10
        assert config.links.concurrency == 20
        assert config.cache.ttl_hours == 24
    
    def test_config_load_save(self, tmp_path):
        """Test loading and saving config."""
        config_path = tmp_path / ".clean-docs.yaml"
        
        # Create a config
        config = Config()
        config.links.timeout = 20
        config.links.ignore_patterns = ["localhost", "example.com"]
        
        # Save it
        config.save(config_path)
        
        # Load it back
        loaded = Config.load(config_path)
        
        assert loaded.links.timeout == 20
        assert loaded.links.ignore_patterns == ["localhost", "example.com"]


@pytest.mark.asyncio
class TestLinkChecker:
    """Test link checking functionality."""
    
    async def test_check_internal_link(self, tmp_path):
        """Test checking internal file links."""
        from clean_docs.link_checker import LinkChecker, LinkStatus
        
        # Create files
        (tmp_path / "existing.md").write_text("# Test")
        
        cache = CacheManager(tmp_path / "cache")
        
        async with LinkChecker(cache) as checker:
            # Test existing file
            link = Link(text="test", url="./existing.md", line=1, column=0)
            doc = type('obj', (object,), {
                'path': tmp_path / "test.md",
                'content': '',
                'links': [link],
                'headings': [],
                'references': {}
            })()
            
            result = await checker._check_link(link, doc, tmp_path)
            assert result.status == LinkStatus.OK
            
            # Test non-existing file
            link2 = Link(text="test", url="./nonexistent.md", line=1, column=0)
            result2 = await checker._check_link(link2, doc, tmp_path)
            assert result2.status == LinkStatus.BROKEN


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
