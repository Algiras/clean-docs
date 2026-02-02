"""Markdown parser to extract links and structure."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

from markdown_it import MarkdownIt
from markdown_it.token import Token


@dataclass
class Link:
    """Represents a link found in markdown."""
    text: str
    url: str
    line: int
    column: int
    is_image: bool = False
    is_reference: bool = False
    reference_label: Optional[str] = None


@dataclass
class MarkdownDocument:
    """Parsed markdown document with links and structure."""
    path: Path
    content: str
    links: List[Link]
    headings: List[tuple]  # (level, text, line)
    references: dict  # reference label -> url


class MarkdownParser:
    """Parse markdown files to extract links and structure."""
    
    def __init__(self):
        self.md = MarkdownIt()
    
    def parse_file(self, file_path: Path) -> MarkdownDocument:
        """Parse a markdown file."""
        content = file_path.read_text(encoding="utf-8")
        return self.parse_content(content, file_path)
    
    def parse_content(self, content: str, file_path: Path) -> MarkdownDocument:
        """Parse markdown content."""
        links = []
        headings = []
        references = {}
        
        # First pass: find all reference definitions
        ref_pattern = re.compile(
            r'^\s*\[([^\]]+)\]:\s*(\S+)(?:\s+"([^"]+)")?\s*$',
            re.MULTILINE
        )
        for match in ref_pattern.finditer(content):
            label = match.group(1).lower()
            url = match.group(2)
            references[label] = url
        
        # Parse with markdown-it
        tokens = self.md.parse(content)
        
        # Track line numbers
        lines = content.split('\n')
        line_map = self._build_line_map(content, tokens)
        
        for i, token in enumerate(tokens):
            if token.type == "inline" and token.children:
                for child in token.children:
                    if child.type == "link_open":
                        href = child.attrGet("href") or ""
                        line_num = token.map[0] + 1 if token.map else 0
                        
                        # Get link text from next text token
                        text = ""
                        for next_child in token.children[token.children.index(child)+1:]:
                            if next_child.type == "text":
                                text = next_child.content
                                break
                            if next_child.type == "link_close":
                                break
                        
                        links.append(Link(
                            text=text,
                            url=href,
                            line=line_num,
                            column=0,
                            is_image=False,
                            is_reference=href.startswith("["),
                        ))
                    
                    elif child.type == "image":
                        src = child.attrGet("src") or ""
                        # Alt text is stored in the token content for images
                        alt = child.content or ""
                        line_num = token.map[0] + 1 if token.map else 0
                        
                        links.append(Link(
                            text=alt,
                            url=src,
                            line=line_num,
                            column=0,
                            is_image=True,
                            is_reference=src.startswith("["),
                        ))
            
            elif token.type == "heading_open":
                level = int(token.tag[1])  # h1 -> 1, h2 -> 2, etc.
                # Find the heading text in the next token
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = tokens[i + 1].content
                    line_num = token.map[0] + 1 if token.map else 0
                    headings.append((level, heading_text, line_num))
        
        # Resolve reference-style links
        for link in links:
            if link.url.startswith("[") and link.url.endswith("]"):
                ref_label = link.url[1:-1].lower()
                if ref_label in references:
                    link.url = references[ref_label]
                    link.is_reference = True
                    link.reference_label = ref_label
                elif link.text.lower() in references and not ref_label:
                    # Implicit reference [text][] or [text]
                    link.url = references[link.text.lower()]
                    link.is_reference = True
                    link.reference_label = link.text.lower()
        
        return MarkdownDocument(
            path=file_path,
            content=content,
            links=links,
            headings=headings,
            references=references,
        )
    
    def _build_line_map(self, content: str, tokens: List[Token]) -> dict:
        """Build a mapping of token positions to line numbers."""
        lines = content.split('\n')
        return {}
    
    def find_all_markdown_files(self, root: Path) -> List[Path]:
        """Find all markdown files in directory."""
        markdown_files = []
        for pattern in ["**/*.md", "**/*.mdx"]:
            markdown_files.extend(root.glob(pattern))
        return sorted(markdown_files)
    
    def get_anchor_id(self, heading_text: str) -> str:
        """Convert heading text to anchor ID."""
        # GitHub-style anchors: lowercase, spaces to hyphens, remove special chars
        anchor = heading_text.lower()
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        anchor = re.sub(r'\s+', '-', anchor)
        anchor = anchor.strip('-')
        return anchor
