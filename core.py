import sqlite3
from datetime import datetime

DB = "assistant.db"


def get_conn():
    return sqlite3.connect(DB)


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # ---------- GOALS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            created_at TEXT
        )
    """)

    # ---------- TASKS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending'
        )
    """)

    # ---------- DAILY TASKS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            day TEXT
        )
    """)

    # ---------- REMINDERS ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            chat_id TEXT,
            remind_at INTEGER
        )
    """)

    # ---------- DAILY NOTIFICATIONS (✅ NEW – REQUIRED FOR 7 AM) ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_notifications (
            chat_id TEXT,
            date TEXT,
            PRIMARY KEY (chat_id, date)
        )
    """)

    conn.commit()
    conn.close()


# ---------- GOALS ----------

def create_goal(text):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO goals (text, created_at) VALUES (?, ?)",
        (text, datetime.now().isoformat())
    )
    goal_id = cur.lastrowid
    conn.commit()
    conn.close()
    return goal_id


def get_goals():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, text FROM goals ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def delete_last_goal():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM goals WHERE id=(SELECT MAX(id) FROM goals)")
    cur.execute("DELETE FROM tasks WHERE goal_id NOT IN (SELECT id FROM goals)")
    conn.commit()
    conn.close()


def delete_all_goals():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM goals")
    cur.execute("DELETE FROM tasks")
    cur.execute("DELETE FROM daily_tasks")
    conn.commit()
    conn.close()


# ---------- TASKS ----------

def add_task(goal_id, text):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tasks (goal_id, text, status) VALUES (?, ?, 'pending')",
        (goal_id, text)
    )
    conn.commit()
    conn.close()