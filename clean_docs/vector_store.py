"""Vector store for embedding-based similarity search.

Uses sqlite-vec extension for efficient vector similarity search in SQLite.
Falls back to numpy-based search if sqlite-vec is not available.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import struct
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional dependencies
try:
    import sqlite_vec
    VECTOR_DB_AVAILABLE = True
except ImportError:
    sqlite_vec = None
    VECTOR_DB_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    np = None
    NUMPY_AVAILABLE = False


@dataclass
class VectorEntry:
    """Represents a stored vector with metadata."""
    id: str
    vector: Any  # numpy array or list of floats
    metadata: Dict[str, Any]
    timestamp: float


def serialize_float32(vector: List[float]) -> bytes:
    """Serialize a float32 vector to bytes for sqlite-vec."""
    return struct.pack(f'{len(vector)}f', *vector)


def deserialize_float32(data: bytes) -> List[float]:
    """Deserialize bytes to a float32 vector."""
    n = len(data) // 4
    return list(struct.unpack(f'{n}f', data))


class VectorStore:
    """SQLite-based vector store with optional sqlite-vec acceleration.

    When sqlite-vec is available, uses native vector similarity search.
    Otherwise falls back to loading vectors and computing similarity in Python.
    """

    def __init__(
        self,
        db_path: Path,
        dimension: int = 1024,
        use_vec_extension: bool = True,
    ):
        """Initialize vector store.

        Args:
            db_path: Path to SQLite database file
            dimension: Vector dimension (default 1024 for mxbai-embed-large)
            use_vec_extension: Whether to use sqlite-vec extension if available
        """
        self.db_path = db_path
        self.dimension = dimension
        self.use_vec_extension = use_vec_extension and VECTOR_DB_AVAILABLE
        self._local = threading.local()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
            )
            conn.row_factory = sqlite3.Row

            # Load sqlite-vec extension if available
            if self.use_vec_extension:
                try:
                    conn.enable_load_extension(True)
                    sqlite_vec.load(conn)
                    conn.enable_load_extension(False)
                except Exception:
                    self.use_vec_extension = False

            self._local.conn = conn

        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if self.use_vec_extension:
            # Create virtual table for vector search
            cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vectors USING vec0(
                    id TEXT PRIMARY KEY,
                    embedding FLOAT[{self.dimension}]
                )
            """)

            # Metadata table (separate from virtual table)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vector_metadata (
                    id TEXT PRIMARY KEY,
                    metadata TEXT,
                    timestamp REAL
                )
            """)
        else:
            # Standard table for fallback mode
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vectors (
                    id TEXT PRIMARY KEY,
                    embedding BLOB,
                    metadata TEXT,
                    timestamp REAL
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_vectors_timestamp
                ON vectors(timestamp)
            """)

        conn.commit()

    def add(
        self,
        id: str,
        vector: Any,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a vector to the store.

        Args:
            id: Unique identifier
            vector: Embedding vector (numpy array or list)
            metadata: Optional metadata dict
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Convert to list if numpy array
        if NUMPY_AVAILABLE and hasattr(vector, 'tolist'):
            vector_list = vector.tolist()
        else:
            vector_list = list(vector)

        metadata_json = json.dumps(metadata or {})
        timestamp = time.time()

        if self.use_vec_extension:
            # sqlite-vec format
            cursor.execute(
                "INSERT OR REPLACE INTO vectors (id, embedding) VALUES (?, ?)",
                (id, serialize_float32(vector_list))
            )
            cursor.execute(
                "INSERT OR REPLACE INTO vector_metadata (id, metadata, timestamp) VALUES (?, ?, ?)",
                (id, metadata_json, timestamp)
            )
        else:
            # Fallback: store as blob
            vector_blob = serialize_float32(vector_list)
            cursor.execute(
                "INSERT OR REPLACE INTO vectors (id, embedding, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (id, vector_blob, metadata_json, timestamp)
            )

        conn.commit()

    def add_batch(
        self,
        entries: List[Tuple[str, Any, Optional[Dict[str, Any]]]],
    ) -> None:
        """Add multiple vectors in a batch.

        Args:
            entries: List of (id, vector, metadata) tuples
        """
        if not entries:
            return

        conn = self._get_conn()
        cursor = conn.cursor()
        timestamp = time.time()

        cursor.execute("BEGIN")
        try:
            for id, vector, metadata in entries:
                if NUMPY_AVAILABLE and hasattr(vector, 'tolist'):
                    vector_list = vector.tolist()
                else:
                    vector_list = list(vector)

                metadata_json = json.dumps(metadata or {})

                if self.use_vec_extension:
                    cursor.execute(
                        "INSERT OR REPLACE INTO vectors (id, embedding) VALUES (?, ?)",
                        (id, serialize_float32(vector_list))
                    )
                    cursor.execute(
                        "INSERT OR REPLACE INTO vector_metadata (id, metadata, timestamp) VALUES (?, ?, ?)",
                        (id, metadata_json, timestamp)
                    )
                else:
                    vector_blob = serialize_float32(vector_list)
                    cursor.execute(
                        "INSERT OR REPLACE INTO vectors (id, embedding, metadata, timestamp) VALUES (?, ?, ?, ?)",
                        (id, vector_blob, metadata_json, timestamp)
                    )

            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise

    def search(
        self,
        query_vector: Any,
        top_k: int = 5,
        threshold: float = 0.0,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar vectors.

        Args:
            query_vector: Query embedding
            top_k: Number of results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (id, similarity, metadata) tuples sorted by similarity descending
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if NUMPY_AVAILABLE and hasattr(query_vector, 'tolist'):
            query_list = query_vector.tolist()
        else:
            query_list = list(query_vector)

        if self.use_vec_extension:
            # Use sqlite-vec for efficient search
            cursor.execute("""
                SELECT
                    v.id,
                    v.distance,
                    m.metadata
                FROM vectors v
                JOIN vector_metadata m ON v.id = m.id
                WHERE v.embedding MATCH ?
                    AND k = ?
                ORDER BY v.distance
            """, (serialize_float32(query_list), top_k))

            results = []
            for row in cursor.fetchall():
                # sqlite-vec returns L2 distance, convert to similarity
                # For normalized vectors: similarity = 1 - distance/2
                distance = row['distance']
                similarity = max(0, 1 - distance / 2)

                if similarity >= threshold:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    results.append((row['id'], similarity, metadata))

            return results

        else:
            # Fallback: load all and compute
            return self._search_fallback(query_list, top_k, threshold)

    def _search_fallback(
        self,
        query_list: List[float],
        top_k: int,
        threshold: float,
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Fallback search using numpy or pure Python."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT id, embedding, metadata FROM vectors")

        results = []
        for row in cursor.fetchall():
            stored_vector = deserialize_float32(row['embedding'])
            similarity = self._cosine_similarity(query_list, stored_vector)

            if similarity >= threshold:
                metadata = json.loads(row['metadata']) if row['metadata'] else {}
                results.append((row['id'], similarity, metadata))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if NUMPY_AVAILABLE:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot / (norm1 * norm2))
        else:
            # Pure Python fallback
            dot = sum(a * b for a, b in zip(vec1, vec2))
            norm1 = sum(a * a for a in vec1) ** 0.5
            norm2 = sum(b * b for b in vec2) ** 0.5
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return dot / (norm1 * norm2)

    def get(self, id: str) -> Optional[VectorEntry]:
        """Get a vector entry by ID.

        Args:
            id: Entry identifier

        Returns:
            VectorEntry or None if not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if self.use_vec_extension:
            cursor.execute("""
                SELECT v.embedding, m.metadata, m.timestamp
                FROM vectors v
                JOIN vector_metadata m ON v.id = m.id
                WHERE v.id = ?
            """, (id,))
        else:
            cursor.execute(
                "SELECT embedding, metadata, timestamp FROM vectors WHERE id = ?",
                (id,)
            )

        row = cursor.fetchone()
        if row is None:
            return None

        vector = deserialize_float32(row['embedding'])
        metadata = json.loads(row['metadata']) if row['metadata'] else {}

        return VectorEntry(
            id=id,
            vector=vector,
            metadata=metadata,
            timestamp=row['timestamp'],
        )

    def delete(self, id: str) -> bool:
        """Delete a vector entry.

        Args:
            id: Entry identifier

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if self.use_vec_extension:
            cursor.execute("DELETE FROM vectors WHERE id = ?", (id,))
            cursor.execute("DELETE FROM vector_metadata WHERE id = ?", (id,))
        else:
            cursor.execute("DELETE FROM vectors WHERE id = ?", (id,))

        conn.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        """Clear all vectors from the store."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if self.use_vec_extension:
            cursor.execute("DELETE FROM vectors")
            cursor.execute("DELETE FROM vector_metadata")
        else:
            cursor.execute("DELETE FROM vectors")

        conn.commit()

    def count(self) -> int:
        """Get the number of vectors in the store."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if self.use_vec_extension:
            cursor.execute("SELECT COUNT(*) as cnt FROM vector_metadata")
        else:
            cursor.execute("SELECT COUNT(*) as cnt FROM vectors")

        return cursor.fetchone()['cnt']

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None

    def __enter__(self) -> "VectorStore":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class CodeVectorStore(VectorStore):
    """Vector store specialized for code snippet matching.

    Provides higher-level methods for storing and searching code embeddings.
    """

    def add_symbol(
        self,
        symbol_name: str,
        file_path: str,
        start_line: int,
        end_line: int,
        code: str,
        embedding: Any,
        symbol_type: str = "unknown",
    ) -> str:
        """Add a code symbol with its embedding.

        Args:
            symbol_name: Name of the symbol (function, class, etc.)
            file_path: Path to the source file
            start_line: Starting line number
            end_line: Ending line number
            code: The actual code content
            embedding: Embedding vector
            symbol_type: Type of symbol (function, class, method, etc.)

        Returns:
            Generated ID for the entry
        """
        # Generate unique ID
        id_content = f"{file_path}:{symbol_name}:{start_line}"
        entry_id = hashlib.sha256(id_content.encode()).hexdigest()[:16]

        metadata = {
            "name": symbol_name,
            "file_path": file_path,
            "start_line": start_line,
            "end_line": end_line,
            "code": code,
            "type": symbol_type,
        }

        self.add(entry_id, embedding, metadata)
        return entry_id

    def search_similar_code(
        self,
        query_embedding: Any,
        top_k: int = 5,
        threshold: float = 0.3,
        symbol_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar code symbols.

        Args:
            query_embedding: Embedding of the query code
            top_k: Number of results to return
            threshold: Minimum similarity threshold
            symbol_type: Optional filter by symbol type

        Returns:
            List of match dicts with similarity scores
        """
        results = self.search(query_embedding, top_k=top_k * 2, threshold=threshold)

        matches = []
        for id, similarity, metadata in results:
            if symbol_type and metadata.get("type") != symbol_type:
                continue

            matches.append({
                "id": id,
                "similarity": similarity,
                "name": metadata.get("name"),
                "file_path": metadata.get("file_path"),
                "start_line": metadata.get("start_line"),
                "end_line": metadata.get("end_line"),
                "code": metadata.get("code"),
                "type": metadata.get("type"),
            })

            if len(matches) >= top_k:
                break

        return matches

    def index_from_symbol_indexer(
        self,
        symbol_indexer,  # SymbolIndexer from symbol_indexer.py
        embedding_fn,  # Function to generate embeddings
    ) -> int:
        """Bulk index symbols from a SymbolIndexer.

        Args:
            symbol_indexer: SymbolIndexer with indexed files
            embedding_fn: Function that takes code string and returns embedding

        Returns:
            Number of symbols indexed
        """
        symbols = symbol_indexer.get_all_symbols()
        count = 0

        entries = []
        for symbol in symbols:
            try:
                embedding = embedding_fn(symbol.code)

                id_content = f"{symbol.file_path}:{symbol.name}:{symbol.start_line}"
                entry_id = hashlib.sha256(id_content.encode()).hexdigest()[:16]

                metadata = {
                    "name": symbol.name,
                    "file_path": str(symbol.file_path),
                    "start_line": symbol.start_line,
                    "end_line": symbol.end_line,
                    "code": symbol.code,
                    "type": symbol.type,
                }

                entries.append((entry_id, embedding, metadata))
                count += 1

            except Exception:
                continue

        # Batch insert
        self.add_batch(entries)

        return count
