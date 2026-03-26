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


def _column_exists(conn, table, column):
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _safe_add_column(conn, table, column, coltype, default=None):
    """Add a column if it doesn't already exist."""
    if not _column_exists(conn, table, column):
        default_clause = f" DEFAULT {default}" if default is not None else ""
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}{default_clause}")


def init_db():
    """Run all migration scripts in order, then apply safe column additions."""
    conn = get_db()
    try:
        # Phase 1: Run SQL migration files
        migration_files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR) if f.endswith('.sql')
        )
        for mf in migration_files:
            path = os.path.join(MIGRATIONS_DIR, mf)
            with open(path, 'r') as f:
                sql = f.read().strip()
                if sql:
                    conn.executescript(sql)
        conn.commit()

        # Phase 2: Idempotent column additions for scheduler
        _safe_add_column(conn, 'tasks', 'agent_id', 'TEXT')
        _safe_add_column(conn, 'tasks', 'session_key', 'TEXT')
        _safe_add_column(conn, 'tasks', 'model', 'TEXT')
        _safe_add_column(conn, 'tasks', 'queued_at', 'TEXT')
        _safe_add_column(conn, 'tasks', 'started_at', 'TEXT')
        _safe_add_column(conn, 'tasks', 'completed_at', 'TEXT')
        _safe_add_column(conn, 'tasks', 'result_summary', 'TEXT')
        _safe_add_column(conn, 'tasks', 'error_message', 'TEXT')
        _safe_add_column(conn, 'tasks', 'cost_usd', 'REAL', '0.0')
        _safe_add_column(conn, 'tasks', 'tokens_used', 'INTEGER', '0')
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


# ── Scheduler Helpers ─────────────────────────────────

def count_tasks_by_status(status):
    """Count tasks with a given status."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = ?", (status,)
        ).fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_pending_tasks(limit=10):
    """Get pending tasks ordered by priority (1=highest), then creation date."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = 'pending' ORDER BY priority ASC, created_at ASC LIMIT ?",
            (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def transition_task(task_id, new_status, **extra_fields):
    """Transition a task to a new status with timestamp and optional fields."""
    now = _now()
    conn = get_db()
    try:
        updates = {'status': new_status, 'updated_at': now}

        # Auto-set timestamps based on status
        if new_status == 'queued':
            updates['queued_at'] = now
        elif new_status == 'running':
            updates['started_at'] = now
        elif new_status in ('done', 'failed', 'cancelled'):
            updates['completed_at'] = now

        # Merge extra fields
        allowed_extra = {'agent_id', 'session_key', 'model', 'result_summary',
                         'error_message', 'cost_usd', 'tokens_used'}
        for k, v in extra_fields.items():
            if k in allowed_extra and v is not None:
                updates[k] = v

        set_clause = ', '.join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [task_id]
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def get_today_spawned_cost():
    """Get total cost_usd of tasks spawned today (UTC)."""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM tasks WHERE started_at LIKE ? AND status IN ('running', 'done', 'failed')",
            (today + '%',)
        ).fetchone()
        return row[0] if row else 0.0
    finally:
        conn.close()
