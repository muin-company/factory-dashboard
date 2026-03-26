-- Migration 001: Create tasks table for Task Queue
-- Factory Dashboard V2 — Phase 1

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT DEFAULT '',
    status      TEXT DEFAULT 'pending'
                    CHECK(status IN ('pending','queued','running','done','failed','cancelled')),
    priority    INTEGER DEFAULT 5
                    CHECK(priority BETWEEN 1 AND 10),
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_status   ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority, created_at);
