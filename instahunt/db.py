"""
SQLite persistence and queue management for InstaHunt.
Handles profile records, BFS queue, priority boosting, and statistics.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from instahunt.config import DEFAULT_DB_PATH


def get_db_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialize database tables and indexes."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # Table: profiles (Permanent record of evaluated accounts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                username TEXT PRIMARY KEY,
                full_name TEXT,
                biography TEXT,
                followers_count INTEGER DEFAULT 0,
                posts_count INTEGER DEFAULT 0,
                avg_comments REAL DEFAULT 0.0,
                post_locations TEXT DEFAULT '[]',
                detected_city TEXT,
                city_tier TEXT,
                is_skincare INTEGER DEFAULT 0,
                status TEXT CHECK(status IN ('pending', 'qualified', 'rejected', 'error')),
                rejection_reason TEXT,
                evidence TEXT,
                profile_url TEXT,
                authenticity_score REAL DEFAULT NULL,
                quality_grade TEXT DEFAULT NULL,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        # Migration: Add columns if table already existed without them
        try:
            cursor.execute("ALTER TABLE profiles ADD COLUMN authenticity_score REAL DEFAULT NULL")
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute("ALTER TABLE profiles ADD COLUMN quality_grade TEXT DEFAULT NULL")
        except sqlite3.OperationalError:
            pass

        # Table: discovery_queue (BFS queue with priority ordering)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                source TEXT,
                priority INTEGER DEFAULT 10,
                status TEXT CHECK(status IN ('queued', 'processing', 'completed', 'failed')) DEFAULT 'queued',
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TEXT
            )
        """)

        # Indexes for fast lookup and priority queueing
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_profiles_status ON profiles(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status_prio ON discovery_queue(status, priority DESC, id ASC)")
        conn.commit()


def enqueue_profiles(
    usernames: List[str],
    source: str = "seed",
    priority: int = 10,
    force: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Add new usernames to the discovery queue if not already seen or queued."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        for u in usernames:
            clean_u = u.strip().lower().replace("@", "")
            if not clean_u:
                continue

            # Check if already evaluated in profiles table (unless force=True)
            if not force:
                cursor.execute("SELECT 1 FROM profiles WHERE username = ? AND status IN ('qualified', 'rejected')", (clean_u,))
                if cursor.fetchone():
                    continue

            # Check if already in discovery queue
            cursor.execute("SELECT 1 FROM discovery_queue WHERE username = ?", (clean_u,))
            if cursor.fetchone():
                # Already queued; update priority if higher
                cursor.execute(
                    "UPDATE discovery_queue SET priority = MAX(priority, ?) WHERE username = ? AND status = 'queued'",
                    (priority, clean_u),
                )
                continue

            try:
                cursor.execute(
                    """
                    INSERT INTO discovery_queue (username, source, priority, status, created_at)
                    VALUES (?, ?, ?, 'queued', ?)
                    """,
                    (clean_u, source, priority, now),
                )
                inserted += 1
            except sqlite3.Error:
                pass

        conn.commit()
    return inserted


def get_next_queued_profile(db_path: Path = DEFAULT_DB_PATH) -> Optional[Tuple[int, str, str]]:
    """Fetch next highest priority queued username from discovery queue."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, username, source FROM discovery_queue
            WHERE status = 'queued'
            ORDER BY priority DESC, id ASC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                "UPDATE discovery_queue SET status = 'processing', attempts = attempts + 1 WHERE id = ?",
                (row["id"],),
            )
            conn.commit()
            return row["id"], row["username"], row["source"]
    return None


def mark_queue_status(
    queue_id: int,
    status: str,
    last_error: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    """Update status of item in discovery queue."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE discovery_queue SET status = ?, last_error = ? WHERE id = ?",
            (status, last_error, queue_id),
        )
        conn.commit()


def boost_related_priority(
    usernames: List[str],
    boost_priority: int = 100,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    """Boost priority for suggested accounts from a qualified creator."""
    return enqueue_profiles(
        usernames=usernames,
        source="edge_chaining_boosted",
        priority=boost_priority,
        db_path=db_path,
    )


def upsert_profile(profile_data: Dict, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Save or update evaluated profile record."""
    now = datetime.now(timezone.utc).isoformat()
    clean_u = profile_data["username"].strip().lower()
    
    locations = profile_data.get("post_locations", [])
    loc_json = json.dumps(locations) if isinstance(locations, list) else str(locations)

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profiles (
                username, full_name, biography, followers_count, posts_count,
                avg_comments, post_locations, detected_city, city_tier,
                is_skincare, status, rejection_reason, evidence, profile_url,
                authenticity_score, quality_grade, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                full_name = excluded.full_name,
                biography = excluded.biography,
                followers_count = excluded.followers_count,
                posts_count = excluded.posts_count,
                avg_comments = excluded.avg_comments,
                post_locations = excluded.post_locations,
                detected_city = excluded.detected_city,
                city_tier = excluded.city_tier,
                is_skincare = excluded.is_skincare,
                status = excluded.status,
                rejection_reason = excluded.rejection_reason,
                evidence = excluded.evidence,
                profile_url = excluded.profile_url,
                authenticity_score = COALESCE(excluded.authenticity_score, profiles.authenticity_score),
                quality_grade = COALESCE(excluded.quality_grade, profiles.quality_grade),
                updated_at = excluded.updated_at
            """,
            (
                clean_u,
                profile_data.get("full_name", ""),
                profile_data.get("biography", ""),
                profile_data.get("followers_count", 0),
                profile_data.get("posts_count", 0),
                profile_data.get("avg_comments", 0.0),
                loc_json,
                profile_data.get("detected_city", ""),
                profile_data.get("city_tier", "Unknown"),
                1 if profile_data.get("is_skincare", False) else 0,
                profile_data.get("status", "pending"),
                profile_data.get("rejection_reason", ""),
                profile_data.get("evidence", ""),
                profile_data.get("profile_url", f"https://www.instagram.com/{clean_u}/"),
                profile_data.get("authenticity_score"),
                profile_data.get("quality_grade"),
                now,
                now,
            ),
        )
        conn.commit()


def is_profile_seen(username: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Check if profile is already evaluated or in queue."""
    clean_u = username.strip().lower().replace("@", "")
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM profiles WHERE username = ?", (clean_u,))
        if cursor.fetchone():
            return True
        cursor.execute("SELECT 1 FROM discovery_queue WHERE username = ?", (clean_u,))
        return bool(cursor.fetchone())


def get_qualified_profiles(db_path: Path = DEFAULT_DB_PATH) -> List[Dict]:
    """Retrieve all qualified profiles for export."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM profiles
            WHERE status = 'qualified'
            ORDER BY avg_comments DESC, followers_count DESC
            """
        )
        return [dict(r) for r in cursor.fetchall()]


def get_stats(db_path: Path = DEFAULT_DB_PATH) -> Dict:
    """Return aggregated metrics and rejection breakdown."""
    stats = {
        "total_profiles": 0,
        "qualified": 0,
        "rejected": 0,
        "pending_queue": 0,
        "processing_queue": 0,
        "completed_queue": 0,
        "rejection_reasons": {},
    }

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM profiles")
        stats["total_profiles"] = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM profiles GROUP BY status")
        for row in cursor.fetchall():
            if row[0] == "qualified":
                stats["qualified"] = row[1]
            elif row[0] == "rejected":
                stats["rejected"] = row[1]

        cursor.execute("SELECT rejection_reason, COUNT(*) FROM profiles WHERE status = 'rejected' GROUP BY rejection_reason")
        for row in cursor.fetchall():
            if row[0]:
                stats["rejection_reasons"][row[0]] = row[1]

        cursor.execute("SELECT status, COUNT(*) FROM discovery_queue GROUP BY status")
        for row in cursor.fetchall():
            if row[0] == "queued":
                stats["pending_queue"] = row[1]
            elif row[0] == "processing":
                stats["processing_queue"] = row[1]
            elif row[0] == "completed":
                stats["completed_queue"] = row[1]

    return stats
