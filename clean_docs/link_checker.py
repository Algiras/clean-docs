"""Link checker for internal and external links."""

import asyncio
import os
import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse

import aiohttp

from clean_docs.cache import CacheManager
from clean_docs.parsers.markdown import Link, MarkdownDocument


class LinkStatus(Enum):
    OK = "ok"
    BROKEN = "broken"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"
    CACHED = "cached"


@dataclass
class LinkResult:
    """Result of checking a single link."""
    link: Link
    status: LinkStatus
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    suggestion: Optional[str] = None
    response_time: Optional[float] = None
    from_cache: bool = False


@dataclass
class CheckResults:
    """All results from checking a document."""
    document: MarkdownDocument
    results: List[LinkResult] = field(default_factory=list)
    
    @property
    def broken_count(self) -> int:
        return sum(1 for r in self.results if r.status == LinkStatus.BROKEN)
    
    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.results if r.status == LinkStatus.OK)
    
    @property
    def total_count(self) -> int:
        return len(self.results)


class LinkChecker:
    """Check links in markdown documents."""
    
    def __init__(
        self,
        cache: CacheManager,
        timeout: int = 10,
        concurrency: int = 20,
        ignore_patterns: Optional[List[str]] = None,
        retry_count: int = 2,
        retry_delay: float = 1.0,
    ):
        self.cache = cache
        self.timeout = timeout
        self.concurrency = concurrency
        self.ignore_patterns = ignore_patterns or []
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.session: Optional[aiohttp.ClientSession] = None
        self._github_available = self._check_gh_cli()
        self._github_token = os.environ.get("GITHUB_TOKEN")
    
    def _check_gh_cli(self) -> bool:
        """Check if GitHub CLI is available and authenticated."""
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=self.concurrency)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"User-Agent": "Clean-Docs/0.1.0"},
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def check_document(self, doc: MarkdownDocument, base_path: Path) -> CheckResults:
        """Check all links in a document with optimized batch cache lookup."""
        # Pre-fetch all external URLs from cache in one batch query
        external_urls = [
            link.url for link in doc.links 
            if link.url.startswith("http://") or link.url.startswith("https://")
        ]
        cached_statuses = self.cache.get_link_statuses_batch(external_urls) if external_urls else {}
        
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.concurrency)
        
        async def check_with_limit(link: Link) -> LinkResult:
            async with semaphore:
                return await self._check_link(link, doc, base_path, cached_statuses)
        
        # Check all links concurrently
        tasks = [check_with_limit(link) for link in doc.links]
        results = await asyncio.gather(*tasks)
        
        return CheckResults(document=doc, results=list(results))
    
    async def _check_link(
        self, 
        link: Link, 
        doc: MarkdownDocument, 
        base_path: Path,
        cached_statuses: Optional[Dict[str, dict]] = None,
    ) -> LinkResult:
        """Check a single link."""
        url = link.url
        cached_statuses = cached_statuses or {}
        
        # Skip ignored patterns
        for pattern in self.ignore_patterns:
            if pattern in url:
                return LinkResult(
                    link=link,
                    status=LinkStatus.SKIPPED,
                    error_message=f"Matched ignore pattern: {pattern}",
                )
        
        # Handle different URL types
        if url.startswith("http://") or url.startswith("https://"):
            return await self._check_external_link(link, cached_statuses)
        elif url.startswith("mailto:"):
            return LinkResult(link=link, status=LinkStatus.SKIPPED)
        elif url.startswith("#"):
            return self._check_anchor_link(link, doc)
        elif url.startswith("/"):
            return self._check_absolute_link(link, base_path)
        else:
            return self._check_relative_link(link, doc, base_path)
    
    async def _check_external_link(
        self, 
        link: Link,
        cached_statuses: Optional[Dict[str, dict]] = None,
    ) -> LinkResult:
        """Check an external HTTP/HTTPS link with retry logic."""
        url = link.url
        cached_statuses = cached_statuses or {}
        
        # Check pre-fetched cache first (batch lookup), then individual lookup
        cached = cached_statuses.get(url) or self.cache.get_link_status(url)
        if cached:
            return LinkResult(
                link=link,
                status=LinkStatus.CACHED,
                status_code=cached.get("status_code"),
                error_message=cached.get("error"),
                from_cache=True,
            )
        
        # Check if it's a GitHub link
        if "github.com" in url:
            return await self._check_github_link(link)
        
        # Regular HTTP check with retry
        last_error = None
        for attempt in range(self.retry_count + 1):
            try:
                import time
                start = time.time()
                async with self.session.head(url, allow_redirects=True) as response:
                    elapsed = time.time() - start
                    
                    if response.status < 400:
                        self.cache.set_link_status(url, "ok", response.status, response_time=elapsed)
                        return LinkResult(
                            link=link,
                            status=LinkStatus.OK,
                            status_code=response.status,
                            response_time=elapsed,
                        )
                    elif response.status in (429, 503, 502, 504) and attempt < self.retry_count:
                        # Retry on rate limit or server errors
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                        continue
                    else:
                        self.cache.set_link_status(url, "broken", response.status, response_time=elapsed)
                        return LinkResult(
                            link=link,
                            status=LinkStatus.BROKEN,
                            status_code=response.status,
                            error_message=f"HTTP {response.status}",
                        )
            except asyncio.TimeoutError:
                last_error = f"Request timed out after {self.timeout}s"
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except aiohttp.ClientError as e:
                last_error = str(e)
                if attempt < self.retry_count:
                    await asyncio.sleep(self.retry_delay)
                    continue
            except Exception as e:
                last_error = str(e)
                break
        
        # All retries failed
        if "timed out" in (last_error or "").lower():
            self.cache.set_link_status(url, "timeout", error=last_error)
            return LinkResult(
                link=link,
                status=LinkStatus.TIMEOUT,
                error_message=last_error,
            )
        else:
            self.cache.set_link_status(url, "error", error=last_error)
            return LinkResult(
                link=link,
                status=LinkStatus.ERROR,
                error_message=last_error,
            )
    
    async def _check_github_link(self, link: Link) -> LinkResult:
        """Check a GitHub repository/link."""
        url = link.url
        
        # Parse GitHub URL
        # Patterns: https://github.com/owner/repo or https://github.com/owner/repo/blob/branch/path
        match = re.match(
            r'https://github\.com/([^/]+)/([^/]+)(?:/blob/([^/]+)/(.+))?',
            url
        )
        
        if not match:
            # Not a standard GitHub repo/blob URL, do regular HTTP check
            return await self._check_http_link(link)
        
        owner, repo, branch, path = match.groups()
        
        # Try gh CLI first if available
        if self._github_available:
            return await self._check_github_with_cli(link, owner, repo, branch, path)
        
        # Fall back to API with token
        if self._github_token:
            return await self._check_github_with_api(link, owner, repo, branch, path)
        
        # No GitHub access, do basic HTTP check
        return await self._check_http_link(link)
    
    async def _run_gh_command(self, *args: str, timeout: int = 10) -> tuple[int, str, str]:
        """Run gh CLI command asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "gh", *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout
            )
            return proc.returncode or 0, stdout.decode(), stderr.decode()
        except asyncio.TimeoutError:
            if proc:
                proc.kill()
                await proc.wait()
            raise
    
    async def _check_github_with_cli(
        self, 
        link: Link, 
        owner: str, 
        repo: str, 
        branch: Optional[str], 
        path: Optional[str]
    ) -> LinkResult:
        """Check GitHub link using gh CLI (async)."""
        try:
            # Check if repo exists
            returncode, stdout, stderr = await self._run_gh_command(
                "api", f"repos/{owner}/{repo}", "--jq", ".full_name"
            )
            
            if returncode != 0:
                return LinkResult(
                    link=link,
                    status=LinkStatus.BROKEN,
                    error_message=f"Repository {owner}/{repo} not found or not accessible",
                    suggestion=f"Check if the repository exists and is public",
                )
            
            # If there's a branch and path, check them
            if branch and path:
                returncode, stdout, stderr = await self._run_gh_command(
                    "api", f"repos/{owner}/{repo}/contents/{path}?ref={branch}",
                    "-H", "Accept: application/vnd.github.v3+json"
                )
                
                if returncode != 0:
                    # Try to find the default branch
                    returncode2, stdout2, stderr2 = await self._run_gh_command(
                        "api", f"repos/{owner}/{repo}", "--jq", ".default_branch"
                    )
                    if returncode2 == 0:
                        default_branch = stdout2.strip()
                        if branch != default_branch:
                            return LinkResult(
                                link=link,
                                status=LinkStatus.BROKEN,
                                error_message=f"File not found in branch '{branch}'",
                                suggestion=f"Try branch '{default_branch}' instead",
                            )
                    
                    return LinkResult(
                        link=link,
                        status=LinkStatus.BROKEN,
                        error_message=f"File not found: {path}",
                    )
            
            return LinkResult(
                link=link,
                status=LinkStatus.OK,
                status_code=200,
            )
            
        except asyncio.TimeoutError:
            return LinkResult(
                link=link,
                status=LinkStatus.TIMEOUT,
                error_message="GitHub CLI request timed out",
            )
        except Exception as e:
            return LinkResult(
                link=link,
                status=LinkStatus.ERROR,
                error_message=f"GitHub CLI error: {e}",
            )
    
    async def _check_github_with_api(
        self, 
        link: Link, 
        owner: str, 
        repo: str, 
        branch: Optional[str], 
        path: Optional[str]
    ) -> LinkResult:
        """Check GitHub link using REST API with token."""
        headers = {
            "Authorization": f"token {self._github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Clean-Docs/0.1.0",
        }
        
        try:
            # Check repo
            async with self.session.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers,
            ) as response:
                if response.status == 404:
                    return LinkResult(
                        link=link,
                        status=LinkStatus.BROKEN,
                        error_message=f"Repository {owner}/{repo} not found",
                    )
                elif response.status != 200:
                    return LinkResult(
                        link=link,
                        status=LinkStatus.ERROR,
                        status_code=response.status,
                        error_message=f"GitHub API error: {response.status}",
                    )
            
            # Check file if path provided
            if path:
                ref = branch or "HEAD"
                async with self.session.get(
                    f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={ref}",
                    headers=headers,
                ) as response:
                    if response.status == 404:
                        return LinkResult(
                            link=link,
                            status=LinkStatus.BROKEN,
                            error_message=f"File not found in branch '{ref}': {path}",
                        )
            
            return LinkResult(
                link=link,
                status=LinkStatus.OK,
                status_code=200,
            )
            
        except Exception as e:
            return LinkResult(
                link=link,
                status=LinkStatus.ERROR,
                error_message=f"GitHub API error: {e}",
            )
    
    async def _check_http_link(self, link: Link) -> LinkResult:
        """Basic HTTP HEAD request."""
        try:
            import time
            start = time.time()
            async with self.session.head(link.url, allow_redirects=True) as response:
                elapsed = time.time() - start
                
                if response.status < 400:
                    return LinkResult(
                        link=link,
                        status=LinkStatus.OK,
                        status_code=response.status,
                        response_time=elapsed,
                    )
                else:
                    return LinkResult(
                        link=link,
                        status=LinkStatus.BROKEN,
                        status_code=response.status,
                        error_message=f"HTTP {response.status}",
                    )
        except Exception as e:
            return LinkResult(
                link=link,
                status=LinkStatus.ERROR,
                error_message=str(e),
            )
    
    def _check_anchor_link(self, link: Link, doc: MarkdownDocument) -> LinkResult:
        """Check an internal anchor link (#section)."""
        anchor = link.url[1:]  # Remove #
        
        # Get all valid anchors from headings (with variants for different renderers)
        valid_anchors = set()
        primary_anchors = set()  # For suggestions
        from clean_docs.parsers.markdown import MarkdownParser
        parser = MarkdownParser()
        
        # Track heading counts for duplicate handling (heading-1, heading-2, etc.)
        heading_counts: Dict[str, int] = {}
        
        for level, text, line in doc.headings:
            # Get primary anchor and all variants
            primary = parser.get_anchor_id(text)
            primary_anchors.add(primary)
            
            # Add all variants
            variants = parser.get_anchor_variants(text)
            valid_anchors.update(variants)
            
            # Handle duplicate headings (GitHub adds -1, -2, etc.)
            if primary in heading_counts:
                heading_counts[primary] += 1
                numbered = f"{primary}-{heading_counts[primary]}"
                valid_anchors.add(numbered)
                # Also add numbered variants
                for v in variants:
                    valid_anchors.add(f"{v}-{heading_counts[primary]}")
            else:
                heading_counts[primary] = 0
            
            # Also add raw text for exact matches
            valid_anchors.add(text.lower().replace(" ", "-"))
        
        if anchor in valid_anchors:
            return LinkResult(link=link, status=LinkStatus.OK)
        
        # Check if it's a numbered anchor that might match (e.g., #section-2)
        anchor_match = re.match(r'^(.+)-(\d+)$', anchor)
        if anchor_match:
            base_anchor = anchor_match.group(1)
            if base_anchor in valid_anchors or base_anchor in primary_anchors:
                # The base exists, but not this numbered version - might be stale
                return LinkResult(
                    link=link,
                    status=LinkStatus.BROKEN,
                    error_message=f"Anchor #{anchor} not found (numbered anchor may be outdated)",
                    suggestion=f"Did you mean #{base_anchor}?",
                )
        
        # Suggest closest match from primary anchors (cleaner suggestions)
        suggestion = self._suggest_anchor(anchor, primary_anchors)
        
        return LinkResult(
            link=link,
            status=LinkStatus.BROKEN,
            error_message=f"Anchor #{anchor} not found",
            suggestion=suggestion,
        )
    
    def _check_relative_link(self, link: Link, doc: MarkdownDocument, base_path: Path) -> LinkResult:
        """Check a relative file link."""
        url = link.url
        
        # Split off anchor
        if "#" in url:
            file_part, anchor = url.split("#", 1)
        else:
            file_part, anchor = url, None
        
        # Resolve path
        doc_dir = doc.path.parent
        target_path = doc_dir / file_part
        target_path = target_path.resolve()
        
        # Check if file exists
        if not target_path.exists():
            # Try with .md extension
            md_path = Path(str(target_path) + ".md")
            if md_path.exists():
                target_path = md_path
            else:
                return LinkResult(
                    link=link,
                    status=LinkStatus.BROKEN,
                    error_message=f"File not found: {file_part}",
                    suggestion=f"Did you mean {file_part}.md?" if not file_part.endswith(".md") else None,
                )
        
        # If there's an anchor, check it
        if anchor and target_path.suffix in [".md", ".mdx"]:
            try:
                from clean_docs.parsers.markdown import MarkdownParser
                parser = MarkdownParser()
                target_doc = parser.parse_file(target_path)
                
                valid_anchors = set()
                primary_anchors = set()
                heading_counts: Dict[str, int] = {}
                
                for level, text, line in target_doc.headings:
                    primary = parser.get_anchor_id(text)
                    primary_anchors.add(primary)
                    
                    # Add all variants
                    variants = parser.get_anchor_variants(text)
                    valid_anchors.update(variants)
                    
                    # Handle duplicate headings
                    if primary in heading_counts:
                        heading_counts[primary] += 1
                        valid_anchors.add(f"{primary}-{heading_counts[primary]}")
                    else:
                        heading_counts[primary] = 0
                
                if anchor not in valid_anchors:
                    return LinkResult(
                        link=link,
                        status=LinkStatus.BROKEN,
                        error_message=f"Anchor #{anchor} not found in {file_part}",
                        suggestion=self._suggest_anchor(anchor, primary_anchors),
                    )
            except Exception:
                pass  # If we can't parse, assume the link is OK
        
        return LinkResult(link=link, status=LinkStatus.OK)
    
    def _check_absolute_link(self, link: Link, base_path: Path) -> LinkResult:
        """Check an absolute path link (/docs/foo.md)."""
        url = link.url
        
        # Split off anchor
        if "#" in url:
            file_part, anchor = url.split("#", 1)
        else:
            file_part, anchor = url, None
        
        # Remove leading slash and resolve from base
        target_path = (base_path / file_part.lstrip("/")).resolve()
        
        if not target_path.exists():
            # Try with .md extension
            md_path = Path(str(target_path) + ".md")
            if md_path.exists():
                target_path = md_path
            else:
                return LinkResult(
                    link=link,
                    status=LinkStatus.BROKEN,
                    error_message=f"File not found: {file_part}",
                )
        
        return LinkResult(link=link, status=LinkStatus.OK)
    
    def _suggest_anchor(self, anchor: str, valid_anchors: Set[str]) -> Optional[str]:
        """Suggest a similar anchor name."""
        if not valid_anchors:
            return None
        
        # Simple string similarity
        def similarity(a: str, b: str) -> float:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, a.lower(), b.lower()).ratio()
        
        best_match = max(valid_anchors, key=lambda a: similarity(anchor, a))
        score = similarity(anchor, best_match)
        
        if score > 0.5:
            return f"Did you mean #{best_match}?"
        return None
