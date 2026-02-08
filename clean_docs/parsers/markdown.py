"""Markdown parser to extract links and structure."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from markdown_it import MarkdownIt
from markdown_it.token import Token


@dataclass
class CodeBlock:
    """Represents a code block found in markdown."""
    language: str           # "java", "python", "scala", etc.
    code: str               # The actual code content
    line: int               # Line number in markdown
    file_hint: Optional[str] = None  # Extracted from comments like "// src/Foo.java"
    symbols: List[str] = field(default_factory=list)  # Extracted class/function names


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
    code_blocks: List[CodeBlock] = field(default_factory=list)


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
        code_blocks = []

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
        content.split('\n')
        self._build_line_map(content, tokens)
        
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

            elif token.type == "fence":
                # Fenced code block
                language = token.info.strip().split()[0] if token.info else ""
                code_content = token.content
                line_num = token.map[0] + 1 if token.map else 0

                # Extract file hint and symbols
                file_hint = self._extract_file_hint(code_content, language)
                symbols = self._extract_symbols(code_content, language)

                code_blocks.append(CodeBlock(
                    language=language,
                    code=code_content,
                    line=line_num,
                    file_hint=file_hint,
                    symbols=symbols,
                ))

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
            code_blocks=code_blocks,
        )
    
    def _build_line_map(self, content: str, tokens: List[Token]) -> dict:
        """Build a mapping of token positions to line numbers."""
        content.split('\n')
        return {}

    def _extract_file_hint(self, code: str, language: str) -> Optional[str]:
        """Extract file path hint from code comments.

        Looks for patterns like:
        - // src/Foo.java
        - # src/foo.py
        - // File: src/Foo.java
        - /* src/Foo.java */
        """
        # Common file path patterns in comments
        patterns = [
            # Single-line comments with file path
            r'(?://|#)\s*(?:File:\s*)?([^\s]+\.[a-zA-Z]+)',
            # Block comments with file path
            r'/\*\s*(?:File:\s*)?([^\s]+\.[a-zA-Z]+)\s*\*/',
            # Path-like patterns at the start
            r'^(?://|#)\s*([\w/.-]+\.[a-zA-Z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, code, re.MULTILINE)
            if match:
                path = match.group(1)
                # Validate it looks like a file path
                if '/' in path or '\\' in path or '.' in path:
                    return path

        return None

    def _extract_symbols(self, code: str, language: str) -> List[str]:
        """Extract class/function/method names from code snippet.

        Uses regex-based extraction for common patterns.
        """
        symbols = []

        # Java/Scala patterns
        if language in ("java", "scala", "kotlin"):
            # Class/interface/trait definitions
            for match in re.finditer(r'\b(?:class|interface|trait|object|enum)\s+(\w+)', code):
                symbols.append(match.group(1))
            # Method definitions
            for match in re.finditer(r'\b(?:public|private|protected|def|fun)\s+\w*\s*(\w+)\s*\(', code):
                symbols.append(match.group(1))

        # Python patterns
        elif language in ("python", "py"):
            # Class definitions
            for match in re.finditer(r'\bclass\s+(\w+)', code):
                symbols.append(match.group(1))
            # Function definitions
            for match in re.finditer(r'\bdef\s+(\w+)', code):
                symbols.append(match.group(1))

        # JavaScript/TypeScript patterns
        elif language in ("javascript", "typescript", "js", "ts", "jsx", "tsx"):
            # Class definitions
            for match in re.finditer(r'\bclass\s+(\w+)', code):
                symbols.append(match.group(1))
            # Function definitions (including async)
            for match in re.finditer(r'\b(?:async\s+)?function\s+(\w+)', code):
                symbols.append(match.group(1))
            # Arrow functions and const functions
            for match in re.finditer(r'\bconst\s+(\w+)\s*=\s*(?:async\s*)?\(', code):
                symbols.append(match.group(1))

        # Go patterns
        elif language == "go":
            # Function definitions
            for match in re.finditer(r'\bfunc\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)', code):
                symbols.append(match.group(1))
            # Type definitions
            for match in re.finditer(r'\btype\s+(\w+)\s+(?:struct|interface)', code):
                symbols.append(match.group(1))

        # Rust patterns
        elif language in ("rust", "rs"):
            # Function definitions
            for match in re.finditer(r'\bfn\s+(\w+)', code):
                symbols.append(match.group(1))
            # Struct/enum definitions
            for match in re.finditer(r'\b(?:struct|enum|trait|impl)\s+(\w+)', code):
                symbols.append(match.group(1))

        # Bazel/Starlark patterns
        elif language in ("bazel", "starlark", "bzl"):
            # Rule/macro definitions
            for match in re.finditer(r'\bdef\s+(\w+)', code):
                symbols.append(match.group(1))
            # Target names
            for match in re.finditer(r'name\s*=\s*["\']([^"\']+)["\']', code):
                symbols.append(match.group(1))

        return list(dict.fromkeys(symbols))  # Remove duplicates while preserving order
    
    def find_all_markdown_files(self, root: Path) -> List[Path]:
        """Find all markdown files in directory."""
        markdown_files = []
        for pattern in ["**/*.md", "**/*.mdx"]:
            markdown_files.extend(root.glob(pattern))
        return sorted(markdown_files)
    
    def get_anchor_id(self, heading_text: str) -> str:
        """Convert heading text to anchor ID (GitHub-style)."""
        # GitHub-style anchors: lowercase, spaces to hyphens, remove most special chars
        anchor = heading_text.lower()
        anchor = re.sub(r'[^\w\s-]', '', anchor)
        anchor = re.sub(r'\s+', '-', anchor)
        anchor = anchor.strip('-')
        return anchor
    
    def get_anchor_variants(self, heading_text: str) -> Set[str]:
        """Generate multiple anchor ID variants to handle different markdown renderers.
        
        Different tools generate anchors differently:
        - GitHub: removes most punctuation, replaces spaces with hyphens
        - GitLab: similar but may keep some chars
        - Docusaurus/MDX: may use different rules
        - Some keep parentheses as-is, some remove them
        """
        variants = set()
        text = heading_text.lower()
        
        # Variant 1: Standard GitHub style (strict - remove all non-word chars)
        # Note: hyphen must be at end of character class to be literal
        v1 = re.sub(r'[^\w\s-]', '', text)
        v1 = re.sub(r'\s+', '-', v1).strip('-')
        variants.add(v1)
        
        # Variant 2: Keep periods and some punctuation (e.g., "a.k.a." -> "aka")
        v2 = text.replace('.', '').replace(',', '')
        v2 = re.sub(r'[^\w\s-]', '', v2)
        v2 = re.sub(r'\s+', '-', v2).strip('-')
        variants.add(v2)
        
        # Variant 3: Replace parentheses content style (e.g., "(a.k.a.)" -> "-aka-")
        v3 = re.sub(r'\(([^)]+)\)', r'-\1-', text)
        v3 = v3.replace('.', '').replace(',', '')
        v3 = re.sub(r'[^\w\s-]', '', v3)
        v3 = re.sub(r'\s+', '-', v3)
        v3 = re.sub(r'-+', '-', v3).strip('-')
        variants.add(v3)
        
        # Variant 4: Keep parentheses as part of slug (hyphen at end of class)
        v4 = text.replace('(', '').replace(')', '')
        v4 = re.sub(r'[^\w\s.-]', '', v4)
        v4 = re.sub(r'\s+', '-', v4)
        v4 = v4.replace('.', '').strip('-')
        variants.add(v4)
        
        # Variant 5: e.g. -> eg style conversion
        v5 = text.replace('e.g.', 'eg').replace('i.e.', 'ie').replace('a.k.a.', 'aka')
        v5 = re.sub(r'[^\w\s-]', '', v5)
        v5 = re.sub(r'\s+', '-', v5).strip('-')
        variants.add(v5)
        
        # Variant 6: Numbered duplicates (heading-1, heading-2 for duplicate headings)
        # We'll add these during anchor checking, not here
        
        # Remove empty strings
        variants.discard('')
        
        return variants
