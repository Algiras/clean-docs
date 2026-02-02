"""Cache manager for link status and embeddings."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional


class CacheManager:
    """SQLite-based cache for link checking results."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.ttl_seconds = ttl_hours * 3600
        self.db_path = cache_dir / "cache.db"
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize SQLite database."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Link status cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_status (
                url TEXT PRIMARY KEY,
                status TEXT,
                status_code INTEGER,
                error TEXT,
                timestamp REAL,
                response_time REAL
            )
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
    
    def _get_key(self, url: str) -> str:
        """Generate cache key for URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:32]
    
    def get_link_status(self, url: str) -> Optional[dict]:
        """Get cached link status if not expired."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT status, status_code, error, timestamp FROM link_status WHERE url = ?",
            (url,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row is None:
            return None
        
        status, status_code, error, timestamp = row
        
        # Check if expired
        if time.time() - timestamp > self.ttl_seconds:
            return None
        
        return {
            "status": status,
            "status_code": status_code,
            "error": error,
            "timestamp": timestamp,
        }
    
    def set_link_status(
        self, 
        url: str, 
        status: str, 
        status_code: Optional[int] = None,
        error: Optional[str] = None,
        response_time: Optional[float] = None,
    ) -> None:
        """Cache link status."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            """
            INSERT OR REPLACE INTO link_status 
            (url, status, status_code, error, timestamp, response_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (url, status, status_code, error, time.time(), response_time),
        )
        
        conn.commit()
        conn.close()
    
    def clear(self) -> None:
        """Clear all cached data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM link_status")
        cursor.execute("DELETE FROM cache_meta")
        conn.commit()
        conn.close()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM link_status")
        link_count = cursor.fetchone()[0]
        
        cursor.execute(
            "SELECT COUNT(*) FROM link_status WHERE timestamp > ?",
            (time.time() - self.ttl_seconds,)
        )
        valid_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_links": link_count,
            "valid_links": valid_count,
            "expired_links": link_count - valid_count,
            "cache_size_mb": self.db_path.stat().st_size / (1024 * 1024) if self.db_path.exists() else 0,
        }
