"""Semantic analyzer using embeddings to match docs with code.

This module is optional. If sentence-transformers is not installed,
semantic analysis features will be disabled gracefully.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

from rich.console import Console
from rich.table import Table

# Optional dependencies - gracefully handle if not installed
try:
    import numpy as np
    from sentence_transformers import SentenceTransformer

    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    np = None  # type: ignore
    SentenceTransformer = None

# For type hints only - won't fail at runtime
if TYPE_CHECKING:
    import numpy as np


@dataclass
class EmbeddingEntry:
    """Represents an embedded document or code file."""

    path: Path
    content_hash: str
    chunks: List[str]
    embeddings: Any  # np.ndarray when numpy is available
    file_type: str  # 'doc', 'code', 'example'


class EmbeddingManager:
    """Generate and cache embeddings for docs and code."""

    def __init__(
        self,
        cache_dir: Path,
        model_name: str = "mixedbread-ai/mxbai-embed-large-v1",
        console: Optional[Console] = None,
    ):
        if not SEMANTIC_AVAILABLE:
            raise ImportError(
                "Semantic analysis requires sentence-transformers. "
                "Install with: pip install clean-docs[semantic]"
            )

        self.cache_dir = cache_dir
        self.db_path = cache_dir / "semantic_cache.db"
        self.model_name = model_name
        self.console = console or Console()
        self._model = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database for embeddings."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                path TEXT PRIMARY KEY,
                content_hash TEXT,
                chunks TEXT,
                embedding BLOB,
                file_type TEXT,
                timestamp REAL
            )
        """)

        conn.commit()
        conn.close()

    @property
    def model(self):
        """Lazy load the embedding model."""
        if self._model is None:
            if self.console:
                self.console.print(f"[dim]Loading embedding model: {self.model_name}...[/dim]")
            self._model = SentenceTransformer(self.model_name, truncate_dim=1024)
        return self._model

    def _compute_hash(self, content: str) -> str:
        """Compute hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _get_cached(self, file_path: Path) -> Optional[EmbeddingEntry]:
        """Get cached embedding if content hasn't changed."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT content_hash, chunks, embedding, file_type FROM embeddings WHERE path = ?",
            (str(file_path),),
        )
        row = cursor.fetchone()
        conn.close()

        if row is None:
            return None

        content_hash, chunks_json, embedding_blob, file_type = row

        # Check if file has changed
        if file_path.exists():
            current_content = file_path.read_text(encoding="utf-8")
            current_hash = self._compute_hash(current_content)
            if current_hash != content_hash:
                return None

        chunks = json.loads(chunks_json)
        embedding = np.frombuffer(embedding_blob, dtype=np.float32)

        return EmbeddingEntry(
            path=file_path,
            content_hash=content_hash,
            chunks=chunks,
            embeddings=embedding,
            file_type=file_type,
        )

    def _cache_embedding(self, entry: EmbeddingEntry) -> None:
        """Cache an embedding."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        import time

        cursor.execute(
            """
            INSERT OR REPLACE INTO embeddings 
            (path, content_hash, chunks, embedding, file_type, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(entry.path),
                entry.content_hash,
                json.dumps(entry.chunks),
                entry.embeddings.tobytes(),
                entry.file_type,
                time.time(),
            ),
        )

        conn.commit()
        conn.close()

    def embed_document(self, file_path: Path, chunk_size: int = 1000) -> EmbeddingEntry:
        """Generate embeddings for a document."""
        # Check cache first
        cached = self._get_cached(file_path)
        if cached:
            return cached

        # Read and chunk content
        content = file_path.read_text(encoding="utf-8")
        content_hash = self._compute_hash(content)

        # Simple chunking by paragraphs for docs
        chunks = self._chunk_text(content, chunk_size)

        # Generate embeddings
        if self.console:
            self.console.print(f"[dim]Embedding {file_path.name} ({len(chunks)} chunks)...[/dim]")

        embeddings = self.model.encode(chunks, show_progress_bar=False)

        # Average embeddings for the whole document
        avg_embedding = np.mean(embeddings, axis=0)

        entry = EmbeddingEntry(
            path=file_path,
            content_hash=content_hash,
            chunks=chunks,
            embeddings=avg_embedding,
            file_type="doc",
        )

        self._cache_embedding(entry)
        return entry

    def embed_code_file(self, file_path: Path) -> EmbeddingEntry:
        """Generate embeddings for a code file."""
        # Check cache first
        cached = self._get_cached(file_path)
        if cached:
            return cached

        # Read content
        content = file_path.read_text(encoding="utf-8")
        content_hash = self._compute_hash(content)

        # Extract code blocks/sections
        chunks = self._extract_code_chunks(content, file_path.suffix)

        if not chunks:
            # Fallback: use entire file
            chunks = [content[:5000]]  # Limit size

        # Generate embeddings
        if self.console:
            self.console.print(
                f"[dim]Embedding code {file_path.name} ({len(chunks)} chunks)...[/dim]"
            )

        embeddings = self.model.encode(chunks, show_progress_bar=False)
        avg_embedding = np.mean(embeddings, axis=0)

        entry = EmbeddingEntry(
            path=file_path,
            content_hash=content_hash,
            chunks=chunks,
            embeddings=avg_embedding,
            file_type="code",
        )

        self._cache_embedding(entry)
        return entry

    def _chunk_text(self, text: str, chunk_size: int) -> List[str]:
        """Split text into chunks."""
        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)
            if current_size + para_size > chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_size = 0

            current_chunk.append(para)
            current_size += para_size

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks if chunks else [text]

    def _extract_code_chunks(self, content: str, extension: str) -> List[str]:
        """Extract meaningful code chunks."""
        chunks = []

        # Extract docstrings/comments (Python style)
        if extension in [".py", ".pyx"]:
            import re

            # Find docstrings
            docstring_pattern = r'"""(.*?)"""'
            for match in re.finditer(docstring_pattern, content, re.DOTALL):
                chunks.append(match.group(1))

            # Find function/class definitions
            def_pattern = r"(?:def|class)\s+\w+[^:]*:"
            for match in re.finditer(def_pattern, content):
                start = match.start()
                # Get a window around the definition
                chunk = content[max(0, start - 100) : start + 500]
                chunks.append(chunk)

        # Extract JSDoc comments (JavaScript/TypeScript)
        elif extension in [".js", ".ts", ".jsx", ".tsx"]:
            import re

            jsdoc_pattern = r"/\*\*(.*?)\*/"
            for match in re.finditer(jsdoc_pattern, content, re.DOTALL):
                chunks.append(match.group(1))

        # Limit chunk size
        return [c[:2000] for c in chunks if len(c) > 50]

    def compute_similarity(self, embedding1: Any, embedding2: Any) -> float:
        """Compute cosine similarity between two embeddings."""
        dot = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot / (norm1 * norm2))

    def find_similar(
        self,
        query_embedding: Any,
        candidates: List[EmbeddingEntry],
        top_k: int = 5,
        threshold: float = 0.5,
    ) -> List[Tuple[EmbeddingEntry, float]]:
        """Find most similar entries to query."""
        similarities = []

        for entry in candidates:
            sim = self.compute_similarity(query_embedding, entry.embeddings)
            if sim >= threshold:
                similarities.append((entry, sim))

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities[:top_k]


class SemanticAnalyzer:
    """Analyze semantic relationships between docs and code."""

    def __init__(self, embedding_manager: EmbeddingManager, console: Optional[Console] = None):
        self.embeddings = embedding_manager
        self.console = console or Console()
        self.doc_entries: List[EmbeddingEntry] = []
        self.code_entries: List[EmbeddingEntry] = []

    def index_documents(self, docs: List[Path]) -> None:
        """Index all documentation files."""
        self.console.print(f"[bold cyan]Indexing {len(docs)} documents...[/bold cyan]")

        self.doc_entries = []
        for doc_path in docs:
            try:
                entry = self.embeddings.embed_document(doc_path)
                self.doc_entries.append(entry)
            except Exception as e:
                self.console.print(f"[red]Error embedding {doc_path}: {e}[/red]")

        self.console.print(f"[green]Indexed {len(self.doc_entries)} documents[/green]")

    def index_code(self, code_files: List[Path]) -> None:
        """Index all code files."""
        self.console.print(f"[bold cyan]Indexing {len(code_files)} code files...[/bold cyan]")

        self.code_entries = []
        for code_path in code_files:
            try:
                entry = self.embeddings.embed_code_file(code_path)
                self.code_entries.append(entry)
            except Exception as e:
                self.console.print(f"[red]Error embedding {code_path}: {e}[/red]")

        self.console.print(f"[green]Indexed {len(self.code_entries)} code files[/green]")

    def find_orphaned_docs(
        self, threshold: float = 0.5
    ) -> List[Tuple[EmbeddingEntry, List[Tuple[EmbeddingEntry, float]]]]:
        """Find documentation with no related code (orphaned docs)."""
        if not self.code_entries:
            return []

        orphaned = []

        for doc_entry in self.doc_entries:
            # Find most similar code
            matches = self.embeddings.find_similar(
                doc_entry.embeddings,
                self.code_entries,
                top_k=3,
                threshold=threshold,
            )

            if not matches:
                orphaned.append((doc_entry, []))
            elif matches[0][1] < threshold:
                orphaned.append((doc_entry, matches))

        return orphaned

    def find_missing_docs(
        self, threshold: float = 0.5
    ) -> List[Tuple[EmbeddingEntry, List[Tuple[EmbeddingEntry, float]]]]:
        """Find code with no documentation (missing docs)."""
        if not self.doc_entries:
            return []

        missing = []

        for code_entry in self.code_entries:
            # Find most similar docs
            matches = self.embeddings.find_similar(
                code_entry.embeddings,
                self.doc_entries,
                top_k=3,
                threshold=threshold,
            )

            if not matches:
                missing.append((code_entry, []))
            elif matches[0][1] < threshold:
                missing.append((code_entry, matches))

        return missing

    def suggest_related_code(
        self, doc_path: Path, top_k: int = 5
    ) -> List[Tuple[EmbeddingEntry, float]]:
        """Suggest related code files for a documentation file."""
        # Find the doc entry
        doc_entry = None
        for entry in self.doc_entries:
            if entry.path == doc_path:
                doc_entry = entry
                break

        if doc_entry is None:
            # Not indexed yet, index it
            doc_entry = self.embeddings.embed_document(doc_path)
            self.doc_entries.append(doc_entry)

        return self.embeddings.find_similar(
            doc_entry.embeddings,
            self.code_entries,
            top_k=top_k,
            threshold=0.0,  # Return all, sorted
        )

    def print_orphaned_docs(self, orphaned: List[Tuple[EmbeddingEntry, List]]) -> None:
        """Print orphaned documentation."""
        if not orphaned:
            self.console.print("[green]✓ All documents have related code![/green]")
            return

        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Document", style="cyan")
        table.add_column("Best Match", style="dim")
        table.add_column("Similarity", style="yellow")

        for doc_entry, matches in orphaned:
            if matches:
                best = matches[0]
                table.add_row(
                    str(doc_entry.path),
                    str(best[0].path),
                    f"{best[1]:.2f}",
                )
            else:
                table.add_row(
                    str(doc_entry.path),
                    "None found",
                    "N/A",
                )

        self.console.print(
            f"\n[bold yellow]Orphaned Documentation ({len(orphaned)} files):[/bold yellow]"
        )
        self.console.print(table)

    def print_missing_docs(self, missing: List[Tuple[EmbeddingEntry, List]]) -> None:
        """Print code missing documentation."""
        if not missing:
            self.console.print("[green]✓ All code has related documentation![/green]")
            return

        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Code File", style="cyan")
        table.add_column("Best Doc Match", style="dim")
        table.add_column("Similarity", style="yellow")

        for code_entry, matches in missing:
            if matches:
                best = matches[0]
                table.add_row(
                    str(code_entry.path),
                    str(best[0].path),
                    f"{best[1]:.2f}",
                )
            else:
                table.add_row(
                    str(code_entry.path),
                    "None found",
                    "N/A",
                )

        self.console.print(
            f"\n[bold yellow]Code Missing Documentation ({len(missing)} files):[/bold yellow]"
        )
        self.console.print(table)

    def find_similar_code(
        self,
        snippet_code: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> List[Tuple[EmbeddingEntry, float]]:
        """Find source code similar to a documentation snippet.

        This is useful for fuzzy matching when exact symbol matching fails.

        Args:
            snippet_code: The code snippet from documentation
            top_k: Number of top matches to return
            threshold: Minimum similarity threshold

        Returns:
            List of (code_entry, similarity_score) tuples sorted by similarity
        """
        if not self.code_entries:
            return []

        # Generate embedding for the snippet
        snippet_embedding = self.embeddings.model.encode(
            [snippet_code],
            show_progress_bar=False,
        )[0]

        return self.embeddings.find_similar(
            snippet_embedding,
            self.code_entries,
            top_k=top_k,
            threshold=threshold,
        )

    def embed_snippet(self, snippet_code: str) -> Any:
        """Generate embedding for a code snippet.

        Args:
            snippet_code: The code snippet to embed

        Returns:
            Embedding array for the snippet
        """
        return self.embeddings.model.encode(
            [snippet_code],
            show_progress_bar=False,
        )[0]
