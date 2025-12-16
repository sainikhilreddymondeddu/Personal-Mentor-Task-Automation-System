import asyncio
import sqlite3
import time
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from core import (
    init_db,
    create_goal,
    add_task,
    get_goals,
    delete_last_goal,
    delete_all_goals
)

from planner import (
    fill_daily_tasks,
    get_today_tasks,
    update_task_status
)

from extractor import extract_goal_and_tasks

# ---------------- CONFIG ----------------

BOT_TOKEN = "Your_bot_tocken"
DB = "assistant.db"

PENDING_INGESTION = {}
PENDING_DELETE_ALL = set()

# ---------------- COMMANDS ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Personal AI Mentor Active\n\n"
        "📌 Commands:\n"
        "/goals – View goals\n"
        "/tasks – View today’s tasks\n"
        "/addgoal <goal text>\n"
        "/addtask <goal_id> <task text>\n\n"
        "🗑 Delete:\n"
        "/delete_recent_goal\n"
        "/delete_all_goals\n\n"
        "🧠 Smart input:\n"
        "• Paste ChatGPT plans (text)\n\n"
        "✅ Status updates:\n"
        "done / stuck / blocked\n\n"
        "⏰ Reminders:\n"
        "30m / 1h / tomorrow"
    )
    await show_tasks(update, context)


async def goals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goals = get_goals()
    if not goals:
        await update.message.reply_text("No goals found.")
        return

    msg = "🎯 Goals:\n"
    for gid, text in goals:
        msg += f"{gid}. {text}\n"

    await update.message.reply_text(msg)


async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tasks = get_today_tasks()
    if not tasks:
        await update.message.reply_text("🎉 No tasks today.")
        return

    msg = "📌 Today’s Tasks:\n"
    for i, t in enumerate(tasks, 1):
        msg += f"{i}. {t}\n"

    msg += "\nReply: done / stuck / blocked"
    await update.message.reply_text(msg)


async def addgoal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /addgoal <goal text>")
        return

    goal_text = " ".join(context.args)
    gid = create_goal(goal_text)
    await update.message.reply_text(f"✅ Goal added (ID {gid})")


async def addtask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addtask <goal_id> <task text>")
        return

    try:
        goal_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("goal_id must be a number")
        return

    task_text = " ".join(context.args[1:])
    add_task(goal_id, task_text)
    fill_daily_tasks()
    await update.message.reply_text("✅ Task added")


async def delete_recent_goal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    delete_last_goal()
    await update.message.reply_text("🗑 Last goal deleted")


async def delete_all_goals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    PENDING_DELETE_ALL.add(update.message.chat_id)
    await update.message.reply_text("⚠ Confirm delete ALL goals? Reply yes / no")

# ---------------- REMINDERS ----------------

def save_reminder(chat_id: int, seconds: int):
    ts = int(time.time()) + seconds
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders (chat_id, remind_at) VALUES (?, ?)",
        (str(chat_id), ts)
    )
    conn.commit()
    conn.close()

# ---------------- TEXT HANDLER ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    low = raw.lower()
    chat_id = update.message.chat_id

    # delete all confirm
    if chat_id in PENDING_DELETE_ALL:
        if low == "yes":
            delete_all_goals()
            PENDING_DELETE_ALL.remove(chat_id)
            await update.message.reply_text("❌ All goals deleted")
        else:
            PENDING_DELETE_ALL.remove(chat_id)
            await update.message.reply_text("Cancelled")
        return

    # reminders
    if low == "30m":
        save_reminder(chat_id, 30 * 60)
        await update.message.reply_text("⏰ Reminder set for 30 minutes")
        return

    if low == "1h":
        save_reminder(chat_id, 60 * 60)
        await update.message.reply_text("⏰ Reminder set for 1 hour")
        return

    if low == "tomorrow":
        save_reminder(chat_id, 12 * 60 * 60)
        await update.message.reply_text("🌅 Reminder set for tomorrow")
        return

    # task status
    if low in ("done", "stuck", "blocked"):
        msg = update_task_status(low)
        await update.message.reply_text(msg)
        await show_tasks(update, context)
        return

    # save ingestion
    if chat_id in PENDING_INGESTION and low in ("yes", "no"):
        if low == "yes":
            goal, tasks = PENDING_INGESTION.pop(chat_id)
            gid = create_goal(goal)
            for t in tasks:
                add_task(gid, t)
            fill_daily_tasks()
            await update.message.reply_text("✅ Goal & tasks saved")
            await show_tasks(update, context)
        else:
            PENDING_INGESTION.pop(chat_id)
            await update.message.reply_text("❌ Discarded")
        return

    # extract from text
    goal, tasks = extract_goal_and_tasks(raw)
    if goal and tasks:
        PENDING_INGESTION[chat_id] = (goal, tasks)
        msg = f"🎯 Goal:\n{goal}\n\n📌 Tasks:\n"
        for i, t in enumerate(tasks, 1):
            msg += f"{i}. {t}\n"
        msg += "\nSave this? yes / no"
        await update.message.reply_text(msg)

# ---------------- DAILY 7 AM NOTIFIER ----------------

def already_sent_today(chat_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM reminders_sent WHERE chat_id=? AND day=?",
        (str(chat_id), today)
    )
    res = cur.fetchone()
    conn.close()
    return bool(res)


def mark_sent_today(chat_id):
    today = datetime.now().strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO reminders_sent VALUES (?, ?)",
        (str(chat_id), today)
    )
    conn.commit()
    conn.close()


async def daily_7am_notifier(app):
    while True:
        now = datetime.now()
        if now.hour == 7 and now.minute == 0:
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT chat_id FROM reminders")
            chats = cur.fetchall()
            conn.close()

            for (chat_id,) in chats:
                if already_sent_today(chat_id):
                    continue

                tasks = get_today_tasks()
                if not tasks:
                    msg = "🌅 Good morning!\n🎉 No tasks today."
                else:
                    msg = "🌅 Good morning!\n📌 Today’s Tasks:\n"
                    for i, t in enumerate(tasks, 1):
                        msg += f"{i}. {t}\n"

                try:
                    await app.bot.send_message(chat_id=int(chat_id), text=msg)
                    mark_sent_today(chat_id)
                except:
                    pass

            await asyncio.sleep(60)

        await asyncio.sleep(30)

# ---------------- POST INIT ----------------

async def post_init(app):
    asyncio.create_task(daily_7am_notifier(app))

# ---------------- BOOT ----------------

def main():
    init_db()

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("goals", goals_cmd))
    app.add_handler(CommandHandler("tasks", show_tasks))
    app.add_handler(CommandHandler("addgoal", addgoal_cmd))
    app.add_handler(CommandHandler("addtask", addtask_cmd))
    app.add_handler(CommandHandler("delete_recent_goal", delete_recent_goal_cmd))
    app.add_handler(CommandHandler("delete_all_goals", delete_all_goals_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()

if __name__ == "__main__":

    main()
