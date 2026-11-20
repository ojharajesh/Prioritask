"""
SQLite Database manager for To-Do application.
Handles task storage, sorting, updates, and daily plans.
"""

import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "todo.db"))

PRIORITY_MAP = {
    'high': 3,
    'medium': 2,
    'low': 1
}


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables and indexes."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                raw_text TEXT,
                title TEXT NOT NULL,
                deadline_dt TEXT,
                has_time INTEGER DEFAULT 0,
                priority TEXT DEFAULT 'medium',
                priority_score INTEGER DEFAULT 2,
                status TEXT DEFAULT 'pending',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                rolled_over_count INTEGER DEFAULT 0,
                last_rolled_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_deadline ON tasks(deadline_dt)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority_score)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plan_date TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary TEXT,
                big_three TEXT,
                schedule_blocks TEXT,
                rolled_tasks_count INTEGER DEFAULT 0,
                total_tasks_count INTEGER DEFAULT 0,
                raw_json TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plans_date ON daily_plans(plan_date)")
        conn.commit()


def add_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """Adds a new task to the database."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    prio = task_data.get('priority', 'medium').lower()
    prio_score = PRIORITY_MAP.get(prio, 2)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tasks (
                raw_text, title, deadline_dt, has_time, priority, priority_score,
                status, created_at, completed_at, rolled_over_count, last_rolled_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, NULL, 0, NULL)
        """, (
            task_data.get('raw_text', ''),
            task_data.get('title', 'Untitled Task'),
            task_data.get('deadline_dt'),
            1 if task_data.get('has_time') else 0,
            prio,
            prio_score,
            now_str
        ))
        task_id = cursor.lastrowid
        conn.commit()
        return get_task(task_id)


def get_task(task_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_task(task_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates task fields."""
    allowed = ['title', 'deadline_dt', 'has_time', 'priority', 'status', 'rolled_over_count']
    set_clauses = []
    values = []

    for k in allowed:
        if k in updates:
            if k == 'priority':
                prio = updates[k].lower()
                set_clauses.append("priority = ?")
                values.append(prio)
                set_clauses.append("priority_score = ?")
                values.append(PRIORITY_MAP.get(prio, 2))
            elif k == 'has_time':
                set_clauses.append("has_time = ?")
                values.append(1 if updates[k] else 0)
            elif k == 'status':
                set_clauses.append("status = ?")
                values.append(updates[k])
                if updates[k] == 'completed':
                    set_clauses.append("completed_at = ?")
                    values.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                elif updates[k] == 'pending':
                    set_clauses.append("completed_at = NULL")
            else:
                set_clauses.append(f"{k} = ?")
                values.append(updates[k])

    if not set_clauses:
        return get_task(task_id)

    values.append(task_id)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return get_task(task_id)


def delete_task(task_id: int) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_tasks(
    status: Optional[str] = None,
    sort_by: str = 'deadline_priority',
    search: Optional[str] = None,
    filter_date: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Returns tasks sorted according to sort_by.
    sort_by options:
    - 'deadline_priority': deadline asc (overdue/soonest first), then priority desc
    - 'priority_deadline': priority desc (high first), then deadline asc
    - 'deadline_asc': deadline asc
    - 'created_desc': newest first
    """
    where_clauses = []
    params = []

    if status and status != 'all':
        where_clauses.append("status = ?")
        params.append(status)

    if search and search.strip():
        where_clauses.append("(title LIKE ? OR raw_text LIKE ?)")
        params.extend([f"%{search.strip()}%", f"%{search.strip()}%"])

    if filter_date:
        # e.g. 'today', 'tomorrow', 'upcoming', 'overdue'
        today_str = date.today().strftime('%Y-%m-%d')
        tomorrow_str = (date.today() + timedelta(days=1)).strftime('%Y-%m-%d')
        if filter_date == 'today':
            where_clauses.append("deadline_dt LIKE ?")
            params.append(f"{today_str}%")
        elif filter_date == 'overdue':
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            where_clauses.append("deadline_dt < ? AND status = 'pending'")
            params.append(now_str)
        elif filter_date == 'tomorrow':
            where_clauses.append("deadline_dt LIKE ?")
            params.append(f"{tomorrow_str}%")
        elif filter_date == 'upcoming':
            where_clauses.append("deadline_dt >= ?")
            params.append(f"{tomorrow_str} 23:59:59")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Sort order
    if sort_by == 'priority_deadline':
        order_sql = "ORDER BY priority_score DESC, CASE WHEN deadline_dt IS NULL THEN 1 ELSE 0 END, deadline_dt ASC"
    elif sort_by == 'deadline_asc':
        order_sql = "ORDER BY CASE WHEN deadline_dt IS NULL THEN 1 ELSE 0 END, deadline_dt ASC, priority_score DESC"
    elif sort_by == 'created_desc':
        order_sql = "ORDER BY created_at DESC"
    else: # 'deadline_priority' (Default)
        # Pending tasks with deadline first, ordered by deadline asc, then priority desc. Completed at the end.
        order_sql = """
            ORDER BY
                CASE WHEN status = 'completed' THEN 1 ELSE 0 END ASC,
                CASE WHEN deadline_dt IS NULL THEN 1 ELSE 0 END ASC,
                deadline_dt ASC,
                priority_score DESC
        """

    query = f"SELECT * FROM tasks {where_sql} {order_sql}"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def get_unfinished_tasks_before(cutoff_dt: datetime) -> List[Dict[str, Any]]:
    """Fetches unfinished tasks due before or at cutoff_dt."""
    cutoff_str = cutoff_dt.strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tasks
            WHERE status = 'pending' AND deadline_dt <= ?
            ORDER BY priority_score DESC, deadline_dt ASC
        """, (cutoff_str,))
        return [dict(r) for r in cursor.fetchall()]


def save_daily_plan(plan_data: Dict[str, Any]) -> int:
    """Saves a generated daily plan."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO daily_plans (
                plan_date, created_at, summary, big_three, schedule_blocks,
                rolled_tasks_count, total_tasks_count, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_data['plan_date'],
            now_str,
            plan_data.get('summary', ''),
            json.dumps(plan_data.get('big_three', [])),
            json.dumps(plan_data.get('schedule_blocks', {})),
            plan_data.get('rolled_tasks_count', 0),
            plan_data.get('total_tasks_count', 0),
            json.dumps(plan_data)
        ))
        plan_id = cursor.lastrowid
        conn.commit()
        return plan_id


def get_latest_plan() -> Optional[Dict[str, Any]]:
    """Retrieves the most recent daily plan."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM daily_plans ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if not row:
            return None
        res = dict(row)
        res['big_three'] = json.loads(res['big_three']) if res['big_three'] else []
        res['schedule_blocks'] = json.loads(res['schedule_blocks']) if res['schedule_blocks'] else {}
        if res.get('raw_json'):
            try:
                res['details'] = json.loads(res['raw_json'])
            except Exception:
                pass
        return res


def get_plan_history(limit: int = 10) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, plan_date, created_at, summary, rolled_tasks_count, total_tasks_count FROM daily_plans ORDER BY id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]
