import sqlite3
import datetime

DB = "assistant.db"


def _today():
    return datetime.date.today().isoformat()


def fill_daily_tasks():
    """
    Ensure EXACTLY 3 tasks for today.
    Clears today's list and refills from pending tasks.
    """
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    today = _today()

    # 🔥 CLEAR today's tasks first (CRITICAL FIX)
    cur.execute("DELETE FROM daily_tasks WHERE day = ?", (today,))

    # Get next pending tasks
    cur.execute("""
        SELECT id FROM tasks
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT 3
    """)
    tasks = cur.fetchall()

    for (task_id,) in tasks:
        cur.execute("""
            INSERT INTO daily_tasks (task_id, day)
            VALUES (?, ?)
        """, (task_id, today))

    conn.commit()
    conn.close()


def get_today_tasks():
    """
    Always refresh today's tasks before showing.
    """
    fill_daily_tasks()

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    today = _today()

    cur.execute("""
        SELECT t.text
        FROM daily_tasks d
        JOIN tasks t ON d.task_id = t.id
        WHERE d.day = ?
        ORDER BY d.id ASC
    """, (today,))

    rows = cur.fetchall()
    conn.close()

    return [r[0] for r in rows]


def update_task_status(status: str):
    """
    Marks the FIRST task of today as done/stuck/blocked
    and refreshes daily list.
    """
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    today = _today()

    # Pick first daily task
    cur.execute("""
        SELECT d.task_id
        FROM daily_tasks d
        WHERE d.day = ?
        ORDER BY d.id ASC
        LIMIT 1
    """, (today,))

    row = cur.fetchone()
    if not row:
        conn.close()
        return "🎉 No tasks left today."

    task_id = row[0]

    # Update task
    cur.execute("""
        UPDATE tasks SET status = ? WHERE id = ?
    """, (status, task_id))

    # Remove from today's list
    cur.execute("""
        DELETE FROM daily_tasks
        WHERE task_id = ? AND day = ?
    """, (task_id, today))

    conn.commit()
    conn.close()

    # Refill remaining slots
    fill_daily_tasks()

    return f"✅ Task marked as {status}"