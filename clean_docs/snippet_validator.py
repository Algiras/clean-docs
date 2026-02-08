"""Snippet validator to check code examples against actual source code."""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

from clean_docs.parsers.markdown import CodeBlock
from clean_docs.symbol_indexer import Symbol, SymbolIndexer


class ValidationStatus(str, Enum):
    """Status of snippet validation."""

    VALID = "valid"
    OUTDATED = "outdated"
    NOT_FOUND = "not_found"
    INVALID_SYNTAX = "invalid_syntax"


@dataclass
class ValidationResult:
    """Result of validating a code snippet."""

    snippet: CodeBlock
    status: ValidationStatus
    source_match: Optional[Symbol] = None
    diff: Optional[str] = None  # Unified diff if outdated
    suggestion: Optional[str] = None  # Updated code if fixable
    similarity: float = 0.0  # Similarity score if matched


@dataclass
class SnippetReport:
    """Summary report of all snippet validations."""

    doc_path: Path
    total_snippets: int
    valid_count: int
    outdated_count: int
    not_found_count: int
    invalid_count: int
    results: List[ValidationResult]


class SnippetValidator:
    """Validate code snippets against source code."""

    def __init__(
        self,
        symbol_indexer: SymbolIndexer,
        similarity_threshold: float = 0.8,
        embedding_manager=None,  # Optional SemanticAnalyzer for fuzzy matching
        vector_store=None,  # Optional CodeVectorStore for fast similarity search
    ):
        self.indexer = symbol_indexer
        self.similarity_threshold = similarity_threshold
        self.embedding_manager = embedding_manager
        self.vector_store = vector_store

    def validate_snippet(self, snippet: CodeBlock) -> ValidationResult:
        """Validate a single code snippet."""
        # Skip non-code blocks (empty or unsupported languages)
        if not snippet.code.strip() or not snippet.language:
            return ValidationResult(
                snippet=snippet,
                status=ValidationStatus.NOT_FOUND,
            )

        # Try to find source match
        source_match = self.find_source_match(snippet)

        if source_match is None:
            return ValidationResult(
                snippet=snippet,
                status=ValidationStatus.NOT_FOUND,
            )

        # Compare snippet with source
        similarity = self._compute_similarity(snippet.code, source_match.code)

        if similarity >= self.similarity_threshold:
            return ValidationResult(
                snippet=snippet,
                status=ValidationStatus.VALID,
                source_match=source_match,
                similarity=similarity,
            )

        # Snippet is outdated - compute diff and suggestion
        diff = self.compute_diff(snippet, source_match)
        suggestion = self._generate_suggestion(snippet, source_match)

        return ValidationResult(
            snippet=snippet,
            status=ValidationStatus.OUTDATED,
            source_match=source_match,
            diff=diff,
            suggestion=suggestion,
            similarity=similarity,
        )

    def find_source_match(self, snippet: CodeBlock) -> Optional[Symbol]:
        """Find the source symbol that matches a snippet."""
        # Strategy 1: File hint match
        if snippet.file_hint:
            match = self._find_by_file_hint(snippet)
            if match:
                return match

        # Strategy 2: Symbol name match
        if snippet.symbols:
            match = self._find_by_symbol_names(snippet)
            if match:
                return match

        # Strategy 3: Code content match
        match = self._find_by_code_content(snippet)
        if match:
            return match

        # Strategy 4: Embedding similarity (if available)
        if self.embedding_manager:
            match = self._find_by_embedding(snippet)
            if match:
                return match

        return None

    def _find_by_file_hint(self, snippet: CodeBlock) -> Optional[Symbol]:
        """Find symbol by file path hint in code comments."""
        if not snippet.file_hint:
            return None

        # Search indexed files for matching path
        hint_parts = snippet.file_hint.replace("\\", "/").split("/")
        hint_filename = hint_parts[-1]

        for symbols in self.indexer._symbols.values():
            for symbol in symbols:
                file_name = symbol.file_path.name
                if file_name == hint_filename:
                    # If we have symbol names, check if any match
                    if snippet.symbols:
                        if symbol.name in snippet.symbols:
                            return symbol
                    else:
                        # Return best match by code similarity
                        return self._best_match_in_file(snippet, symbols)

        return None

    def _find_by_symbol_names(self, snippet: CodeBlock) -> Optional[Symbol]:
        """Find symbol by extracted symbol names."""
        best_match: Optional[Symbol] = None
        best_similarity = 0.0

        for symbol_name in snippet.symbols:
            matches = self.indexer.find_symbol(symbol_name)
            for match in matches:
                similarity = self._compute_similarity(snippet.code, match.code)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = match

        return best_match

    def _find_by_code_content(self, snippet: CodeBlock) -> Optional[Symbol]:
        """Find symbol by matching code content."""
        best_match: Optional[Symbol] = None
        best_similarity = 0.0

        # Get all symbols and find best match
        for symbol in self.indexer.get_all_symbols():
            similarity = self._compute_similarity(snippet.code, symbol.code)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = symbol

        # Only return if similarity is above a minimum threshold
        if best_similarity >= 0.3:
            return best_match

        return None

    def _find_by_embedding(self, snippet: CodeBlock) -> Optional[Symbol]:
        """Find symbol using semantic embedding similarity.

        Uses vector store for fast similarity search if available.
        Falls back to semantic analyzer if vector store not available.
        """
        # Strategy 4a: Use vector store if available
        if self.vector_store and self.embedding_manager:
            try:
                # Generate embedding for snippet
                snippet_embedding = self.embedding_manager.embed_snippet(snippet.code)

                # Search vector store
                matches = self.vector_store.search_similar_code(
                    snippet_embedding,
                    top_k=3,
                    threshold=0.3,
                )

                if matches:
                    best_match = matches[0]
                    # Convert to Symbol
                    return Symbol(
                        name=best_match.get("name", ""),
                        type=best_match.get("type", "unknown"),
                        file_path=Path(best_match.get("file_path", "")),
                        start_line=best_match.get("start_line", 0),
                        end_line=best_match.get("end_line", 0),
                        signature="",
                        code=best_match.get("code", ""),
                    )
            except Exception:
                pass

        # Strategy 4b: Use embedding manager directly
        if self.embedding_manager:
            try:
                similar = self.embedding_manager.find_similar_code(
                    snippet.code,
                    top_k=3,
                    threshold=0.3,
                )

                if similar:
                    # Find corresponding Symbol from indexer
                    best_entry, _ = similar[0]
                    # Look up symbol by file path
                    symbols = self.indexer.get_symbols_for_file(best_entry.path)
                    if symbols:
                        return self._best_match_in_file(snippet, symbols)
            except Exception:
                pass

        return None

    def _best_match_in_file(self, snippet: CodeBlock, symbols: List[Symbol]) -> Optional[Symbol]:
        """Find best matching symbol within a file."""
        best_match: Optional[Symbol] = None
        best_similarity = 0.0

        for symbol in symbols:
            similarity = self._compute_similarity(snippet.code, symbol.code)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = symbol

        return best_match

    def _compute_similarity(self, code1: str, code2: str) -> float:
        """Compute similarity between two code snippets.

        Uses a combination of:
        1. Sequence matcher ratio (overall structure)
        2. Line-based matching (for partial matches)
        """
        # Normalize code for comparison
        norm1 = self._normalize_code(code1)
        norm2 = self._normalize_code(code2)

        # If one is a subset of the other, compute partial similarity
        if norm1 in norm2:
            return len(norm1) / len(norm2)
        if norm2 in norm1:
            return len(norm2) / len(norm1)

        # Use SequenceMatcher for general similarity
        matcher = difflib.SequenceMatcher(None, norm1, norm2)
        return matcher.ratio()

    def _normalize_code(self, code: str) -> str:
        """Normalize code for comparison (remove comments, whitespace variations)."""
        lines = []
        for line in code.strip().split("\n"):
            # Remove trailing whitespace
            line = line.rstrip()
            # Skip empty lines
            if not line.strip():
                continue
            # Skip comment-only lines (simple heuristic)
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
                continue
            lines.append(line)
        return "\n".join(lines)

    def compute_diff(self, snippet: CodeBlock, source: Symbol) -> str:
        """Compute unified diff between snippet and actual source."""
        snippet_lines = snippet.code.strip().split("\n")
        source_lines = source.code.strip().split("\n")

        diff = difflib.unified_diff(
            snippet_lines,
            source_lines,
            fromfile="documentation",
            tofile=str(source.file_path),
            lineterm="",
        )
        return "\n".join(diff)

    def _generate_suggestion(self, snippet: CodeBlock, source: Symbol) -> str:
        """Generate suggested updated code for the snippet.

        Tries to preserve documentation-specific formatting while
        updating the core code content.
        """
        # For now, return the source code directly
        # Future enhancement: preserve snippet-specific formatting/comments
        return source.code

    def validate_document(self, doc_path: Path, code_blocks: List[CodeBlock]) -> SnippetReport:
        """Validate all code snippets in a document."""
        results = []
        valid_count = 0
        outdated_count = 0
        not_found_count = 0
        invalid_count = 0

        for snippet in code_blocks:
            result = self.validate_snippet(snippet)
            results.append(result)

            if result.status == ValidationStatus.VALID:
                valid_count += 1
            elif result.status == ValidationStatus.OUTDATED:
                outdated_count += 1
            elif result.status == ValidationStatus.NOT_FOUND:
                not_found_count += 1
            elif result.status == ValidationStatus.INVALID_SYNTAX:
                invalid_count += 1

        return SnippetReport(
            doc_path=doc_path,
            total_snippets=len(code_blocks),
            valid_count=valid_count,
            outdated_count=outdated_count,
            not_found_count=not_found_count,
            invalid_count=invalid_count,
            results=results,
        )

    def fix_snippet(self, snippet: CodeBlock, suggestion: str, doc_content: str) -> str:
        """Replace a snippet in document content with updated code.

        Args:
            snippet: The snippet to replace
            suggestion: The new code to use
            doc_content: The full document content

        Returns:
            Updated document content
        """
        # Find the code block in the document
        lines = doc_content.split("\n")

        # Find the fence start (snippet.line is 1-indexed)
        fence_start = snippet.line - 1
        fence_end = fence_start

        # Find the closing fence
        in_fence = False
        for i in range(fence_start, len(lines)):
            line = lines[i].strip()
            if line.startswith("```"):
                if not in_fence:
                    in_fence = True
                else:
                    fence_end = i
                    break

        if fence_end <= fence_start:
            # Couldn't find proper fence bounds
            return doc_content

        # Reconstruct the code block
        fence_line = lines[fence_start]
        new_block = [
            fence_line,  # Opening fence with language
            suggestion.rstrip(),
            "```",
        ]

        # Replace the block
        new_lines = lines[:fence_start] + new_block + lines[fence_end + 1 :]
        return "\n".join(new_lines)

    def fix_document(
        self, doc_path: Path, report: SnippetReport, dry_run: bool = False
    ) -> Tuple[int, str]:
        """Fix all outdated snippets in a document.

        Args:
            doc_path: Path to the document
            report: Validation report with results
            dry_run: If True, don't write changes

        Returns:
            Tuple of (number of fixes applied, updated content)
        """
        content = doc_path.read_text(encoding="utf-8")
        fixes_applied = 0

        # Sort by line number descending so we don't invalidate line numbers
        outdated = [r for r in report.results if r.status == ValidationStatus.OUTDATED]
        outdated.sort(key=lambda r: r.snippet.line, reverse=True)

        for result in outdated:
            if result.suggestion:
                content = self.fix_snippet(result.snippet, result.suggestion, content)
                fixes_applied += 1

        if not dry_run and fixes_applied > 0:
            doc_path.write_text(content, encoding="utf-8")

        return fixes_applied, content
