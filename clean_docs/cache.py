"""Cache manager for link status and embeddings with optimized SQLite."""

import hashlib
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple


class CacheManager:
    """SQLite-based cache for link checking results.
    
    Optimizations:
    - WAL mode for better concurrent read/write performance
    - Connection pooling with thread-local storage
    - Batch operations for bulk inserts
    - Indexes on frequently queried columns
    - Prepared statements
    - Periodic cleanup of expired entries
    """
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self.db_path = cache_dir / "cache.db"
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local database connection with optimizations."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None,  # Autocommit mode for WAL
            )
            # Performance optimizations
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA mmap_size=268435456")  # 256MB mmap
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn
    
    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        """Context manager for transactions with automatic commit/rollback."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("BEGIN")
        try:
            yield cursor
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
    
    def close(self) -> None:
        """Close the database connection for current thread."""
        if hasattr(self._local, 'conn') and self._local.conn is not None:
            self._local.conn.close()
            self._local.conn = None
    
    def _init_db(self) -> None:
        """Initialize SQLite database with optimized schema."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enable WAL mode
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # Link status cache with optimized schema
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_status (
                url TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                status_code INTEGER,
                error TEXT,
                timestamp REAL NOT NULL,
                response_time REAL
            )
        """)
        
        # Index for TTL queries (finding expired entries)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_link_status_timestamp 
            ON link_status(timestamp)
        """)
        
        # Index for status filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_link_status_status 
            ON link_status(status)
        """)
        
        # Cache metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        conn.commit()
        conn.close()
    
    def get_link_status(self, url: str) -> Optional[dict]:
        """Get cached link status if not expired."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        min_timestamp = time.time() - self.ttl_seconds
        cursor.execute(
            """SELECT status, status_code, error, timestamp, response_time 
               FROM link_status 
               WHERE url = ? AND timestamp > ?""",
            (url, min_timestamp)
        )
        row = cursor.fetchone()
        
        if row is None:
            return None
        
        result = {
            "status": row["status"],
            "status_code": row["status_code"],
            "error": row["error"],
            "timestamp": row["timestamp"],
        }
        if row["response_time"] is not None:
            result["response_time"] = row["response_time"]
        return result
    
    def get_link_statuses_batch(self, urls: List[str]) -> Dict[str, dict]:
        """Get cached link statuses for multiple URLs at once.
        
        Returns a dict mapping URL -> status dict (only for cached URLs).
        """
        if not urls:
            return {}
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        min_timestamp = time.time() - self.ttl_seconds
        placeholders = ",".join("?" * len(urls))
        
        cursor.execute(
            f"""SELECT url, status, status_code, error, timestamp, response_time 
                FROM link_status 
                WHERE url IN ({placeholders}) AND timestamp > ?""",
            (*urls, min_timestamp)
        )
        
        results = {}
        for row in cursor.fetchall():
            result = {
                "status": row["status"],
                "status_code": row["status_code"],
                "error": row["error"],
                "timestamp": row["timestamp"],
            }
            if row["response_time"] is not None:
                result["response_time"] = row["response_time"]
            results[row["url"]] = result
        
        return results
    
    def set_link_status(
        self, 
        url: str, 
        status: str, 
        status_code: Optional[int] = None,
        error: Optional[str] = None,
        response_time: Optional[float] = None,
    ) -> None:
        """Cache link status."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT OR REPLACE INTO link_status 
               (url, status, status_code, error, timestamp, response_time)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (url, status, status_code, error, time.time(), response_time),
        )
    
    def set_link_statuses_batch(
        self,
        entries: List[Tuple[str, str, Optional[int], Optional[str], Optional[float]]]
    ) -> None:
        """Cache multiple link statuses in a single transaction.
        
        Args:
            entries: List of (url, status, status_code, error, response_time) tuples
        """
        if not entries:
            return
        
        timestamp = time.time()
        with self._transaction() as cursor:
            cursor.executemany(
                """INSERT OR REPLACE INTO link_status 
                   (url, status, status_code, error, timestamp, response_time)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(url, status, code, err, timestamp, rt) for url, status, code, err, rt in entries]
            )
    
    def cleanup_expired(self) -> int:
        """Remove expired cache entries. Returns count of removed entries."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        min_timestamp = time.time() - self.ttl_seconds
        cursor.execute(
            "DELETE FROM link_status WHERE timestamp < ?",
            (min_timestamp,)
        )
        deleted = cursor.rowcount
        
        # Reclaim space
        cursor.execute("PRAGMA incremental_vacuum")
        
        return deleted
    
    def clear(self) -> None:
        """Clear all cached data."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM link_status")
        cursor.execute("DELETE FROM cache_meta")
        cursor.execute("VACUUM")
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        min_timestamp = time.time() - self.ttl_seconds
        
        # Get counts in a single query
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN timestamp > ? THEN 1 ELSE 0 END) as valid,
                SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) as ok_count,
                SUM(CASE WHEN status = 'broken' THEN 1 ELSE 0 END) as broken_count,
                AVG(response_time) as avg_response_time
            FROM link_status
        """, (min_timestamp,))
        
        row = cursor.fetchone()
        
        return {
            "total_links": row["total"] or 0,
            "valid_links": row["valid"] or 0,
            "expired_links": (row["total"] or 0) - (row["valid"] or 0),
            "ok_links": row["ok_count"] or 0,
            "broken_links": row["broken_count"] or 0,
            "avg_response_time_ms": (row["avg_response_time"] or 0) * 1000,
            "cache_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0,
        }
    
    def get_broken_links(self, limit: int = 100) -> List[dict]:
        """Get recently cached broken links."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        min_timestamp = time.time() - self.ttl_seconds
        cursor.execute(
            """SELECT url, status_code, error, timestamp 
               FROM link_status 
               WHERE status = 'broken' AND timestamp > ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (min_timestamp, limit)
        )
        
        return [
            {
                "url": row["url"],
                "status_code": row["status_code"],
                "error": row["error"],
                "timestamp": row["timestamp"],
            }
            for row in cursor.fetchall()
        ]
    
    def __del__(self):
        """Ensure connection is closed on garbage collection."""
        self.close()
    
    def __enter__(self) -> "CacheManager":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close connection."""
        self.close()
