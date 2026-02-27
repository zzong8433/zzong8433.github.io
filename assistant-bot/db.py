"""
Database module - SQLite를 사용한 태스크/WBS 저장소
"""
import sqlite3
import os
from datetime import datetime, timezone
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "assistant.db")


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY,
            username      TEXT,
            display_name  TEXT,
            timezone      TEXT DEFAULT 'Asia/Seoul',
            created_at    TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            name          TEXT NOT NULL,
            description   TEXT,
            status        TEXT DEFAULT 'active',
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            project_id    INTEGER,
            parent_id     INTEGER,
            title         TEXT NOT NULL,
            description   TEXT,
            deadline      TEXT,
            status        TEXT DEFAULT 'pending',
            priority      INTEGER DEFAULT 2,
            estimated_min INTEGER,
            created_at    TEXT DEFAULT (datetime('now')),
            completed_at  TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (project_id) REFERENCES projects(id),
            FOREIGN KEY (parent_id) REFERENCES tasks(id)
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            task_id       INTEGER,
            remind_at     TEXT NOT NULL,
            message       TEXT,
            sent          INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline);
        CREATE INDEX IF NOT EXISTS idx_reminders_pending ON reminders(remind_at) WHERE sent = 0;
        """)


# ── User operations ──


def upsert_user(user_id: int, username: str = None, display_name: str = None):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO users (user_id, username, display_name)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username = COALESCE(excluded.username, username),
                 display_name = COALESCE(excluded.display_name, display_name)
            """,
            (user_id, username, display_name),
        )


# ── Project operations ──


def create_project(user_id: int, name: str, description: str = None) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (user_id, name, description) VALUES (?, ?, ?)",
            (user_id, name, description),
        )
        return cur.lastrowid


def get_projects(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM projects WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Task operations ──


def create_task(
    user_id: int,
    title: str,
    description: str = None,
    deadline: str = None,
    project_id: int = None,
    parent_id: int = None,
    priority: int = 2,
    estimated_min: int = None,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO tasks
               (user_id, title, description, deadline, project_id, parent_id, priority, estimated_min)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, title, description, deadline, project_id, parent_id, priority, estimated_min),
        )
        return cur.lastrowid


def get_tasks(user_id: int, status: str = None, project_id: int = None) -> list[dict]:
    with get_conn() as conn:
        query = "SELECT * FROM tasks WHERE user_id = ?"
        params: list = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status)
        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        query += " ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END, deadline ASC, priority ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def get_subtasks(parent_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY id ASC",
            (parent_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def complete_task(task_id: int):
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
            (now, task_id),
        )


def update_task_status(task_id: int, status: str):
    with get_conn() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))


def get_tasks_due_soon(user_id: int, hours: int = 24) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id = ? AND status = 'pending'
                 AND deadline IS NOT NULL
                 AND deadline <= datetime('now', '+' || ? || ' hours')
               ORDER BY deadline ASC""",
            (user_id, hours),
        ).fetchall()
        return [dict(r) for r in rows]


def get_today_tasks(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE user_id = ? AND status IN ('pending', 'in_progress')
                 AND (deadline IS NULL OR date(deadline) <= date('now', '+1 day'))
               ORDER BY CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                        deadline ASC, priority ASC""",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_stats(user_id: int) -> dict:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as done,
                 SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                 SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress
               FROM tasks WHERE user_id = ?""",
            (user_id,),
        ).fetchone()
        return dict(row)


# ── Reminder operations ──


def create_reminder(user_id: int, task_id: int = None, remind_at: str = "", message: str = "") -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO reminders (user_id, task_id, remind_at, message) VALUES (?, ?, ?, ?)",
            (user_id, task_id, remind_at, message),
        )
        return cur.lastrowid


def get_pending_reminders() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT r.*, t.title as task_title
               FROM reminders r
               LEFT JOIN tasks t ON r.task_id = t.id
               WHERE r.sent = 0 AND r.remind_at <= datetime('now')
               ORDER BY r.remind_at ASC""",
        ).fetchall()
        return [dict(r) for r in rows]


def mark_reminder_sent(reminder_id: int):
    with get_conn() as conn:
        conn.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
