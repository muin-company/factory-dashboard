"""SQLite database helper for Factory Dashboard V2 Task Queue."""

import sqlite3
import uuid
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'factory.db')
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), 'migrations')


def get_db():
    """Get a new database connection with WAL mode."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Run all migration scripts in order."""
    conn = get_db()
    try:
        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')
        )
        for mf in migration_files:
            path = os.path.join(MIGRATIONS_DIR, mf)
            with open(path, 'r') as f:
                conn.executescript(f.read())
        conn.commit()
    finally:
        conn.close()


def _now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _row_to_dict(row):
    if row is None:
        return None
    return dict(row)


# ── CRUD ──────────────────────────────────────────────

def create_task(title, description='', status='pending', priority=5):
    """Create a new task. Returns the created task dict."""
    task_id = uuid.uuid4().hex[:12]
    now = _now()
    conn = get_db()
    try:
        conn.execute(
            """INSERT INTO tasks (id, title, description, status, priority, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (task_id, title, description, status, priority, now, now),
        )
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def get_task(task_id):
    """Get a single task by ID."""
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def list_tasks(status=None, priority=None):
    """List tasks with optional filters. Returns list of dicts."""
    conn = get_db()
    try:
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if priority is not None:
            query += " AND priority = ?"
            params.append(int(priority))
        query += " ORDER BY priority ASC, created_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_task(task_id, **fields):
    """Update task fields. Allowed: title, description, status, priority."""
    allowed = {'title', 'description', 'status', 'priority'}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_task(task_id)
    updates['updated_at'] = _now()
    set_clause = ', '.join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]
    conn = get_db()
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def delete_task(task_id):
    """Delete a task. Returns True if deleted."""
    conn = get_db()
    try:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
