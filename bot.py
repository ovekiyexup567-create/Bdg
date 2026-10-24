import os
import sqlite3
import logging
from datetime import datetime, timezone
from collections import Counter

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, ContextTypes
)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DB_PATH = os.getenv("BDG_DB_PATH", "bdg_results.sqlite3")
REPORT_CHAT_ID = os.getenv("REPORT_CHAT_ID", "").strip()
REPORT_INTERVAL_SECONDS = 60
HISTORY_LIMIT = 50

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("bdg-analyzer")


def db_connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with db_connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS results (
                period TEXT PRIMARY KEY,
                number INTEGER NOT NULL CHECK(number BETWEEN 0 AND 9),
                size TEXT NOT NULL CHECK(size IN ('Big', 'Small')),
                colors TEXT NOT NULL,
                recorded_at TEXT NOT NULL
            )
        """)


def classify_size(number: int) -> str:
    return "Big" if number >= 5 else "Small"


def classify_colors(number: int) -> str:
    # Common mapping inferred from the provided screenshots.
    # Verify it against BDG's own game rules/legend before relying on it.
    if number in (1, 3, 7, 9):
        return "Green"
    if number in (2, 4, 6, 8):
        return "Red"
    if number == 0:
        return "Red + Violet"
    return "Green + Violet"  # number == 5


def insert_result(period: str, number: int):
    if not period.isdigit():
        raise ValueError("Period must contain digits only.")
    if not 0 <= number <= 9:
        raise ValueError("Number must be between 0 and 9.")
    now = datetime.now(timezone.utc).isoformat()
    with db_connect() as db:
        db.execute(
            """INSERT INTO results(period, number, size, colors, recorded_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(period) DO UPDATE SET
                 number=excluded.number, size=excluded.size,
                 colors=excluded.colors, recorded_at=excluded.recorded_at""",
            (period, number, classify_size(number), classify_colors(number), now)
        )


def get_recent(limit=HISTORY_LIMIT):
    with db_connect() as db:
        return db.execute(
            "SELECT * FROM results ORDER BY period DESC LIMIT ?", (limit,)
        ).fetchall()


def stats_text():
    rows = list(reversed(get_recent(HISTORY_LIMIT)))
    if not rows:
        return "No results recorded yet. Add one with /add PERIOD NUMBER"
    numbers = Counter(row["number"] for row in rows)
    sizes = Counter(row["size"] for row in rows)
    colors = Counter(row["colors"] for row in rows)
    latest = rows[-1]

    # Count the current run of the latest number's size.
    latest_size = latest["size"]
    streak = 0
    for row in reversed(rows):
        if row["size"] != latest_size:
            break
        streak += 1

    number_lines = ", ".join(f"{n}: {numbers.get(n, 0)}" for n in range(10))
    color_lines = ", ".join(f"{k}: {v}" for k, v in sorted(colors.items()))
    return (
        f"BDG Historical Stats (last {len(rows)} recorded periods)\n\n"
        f"Latest period: {latest['period']}\n"
        f"Latest result: {latest['number']} / {latest['size']} / {latest['colors']}\n"
        f"Current {latest_size} streak: {streak}\n\n"
        f"Big: {sizes.get('Big', 0)} | Small: {sizes.get('Small', 0)}\n"
        f"Colors: {color_lines}\n"
        f"Number counts: {number_lines}\n\n"
        "These are historical statistics, not reliable predictions of the next result."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "BDG Period Analyzer is running.\\n\\n"
        "/add PERIOD NUMBER — record a published result (0–9)\\n"
        "/history — show the latest 10 records\\n"
        "/stats — analyze the latest 50 records\\n"
        "/help — commands\\n\\n"
        "This version does not log in to BDG or place bets."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\\n"
        "/add PERIOD NUMBER — e.g. /add 202610241000010471 7\\n"
        "/history — latest 10 stored records\\n"
        "/stats — frequency and streak summary\\n"
        "/report — send the current summary\\n\\n"
        "The bot stores manually supplied results in SQLite. "
        "It does not connect to BDG automatically."
    )


async def add_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /add PERIOD NUMBER")
        return
    period, raw_number = context.args
    try:
        number = int(raw_number)
        insert_result(period, number)
    except (ValueError, sqlite3.Error) as exc:
        await update.message.reply_text(f"Could not save result: {exc}")
        return
    await update.message.reply_text(
        f"Saved period {period}: {number} / {classify_size(number)} / "
        f"{classify_colors(number)}"
    )


async def history_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_recent(10)
    if not rows:
        await update.message.reply_text("No results recorded yet.")
        return
    lines = ["Latest recorded results:"]
    for row in rows:
        lines.append(
            f"{row['period']} — {row['number']} — {row['size']} — {row['colors']}"
        )
    await update.message.reply_text("\\n".join(lines))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(stats_text())


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(stats_text())


async def scheduled_report(context: ContextTypes.DEFAULT_TYPE):
    if not REPORT_CHAT_ID:
        return
    try:
        await context.bot.send_message(
            chat_id=REPORT_CHAT_ID,
            text=stats_text()
        )
    except Exception:
        log.exception("Scheduled report failed")


def main():
    if not BOT_TOKEN:
        raise SystemExit("Missing TELEGRAM_BOT_TOKEN environment variable.")
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("history", history_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("report", report_cmd))

    if app.job_queue:
        app.job_queue.run_repeating(
            scheduled_report,
            interval=REPORT_INTERVAL_SECONDS,
            first=REPORT_INTERVAL_SECONDS
        )
    else:
        log.warning("JobQueue unavailable; scheduled reports disabled.")

    log.info("BDG Period Analyzer starting")
    app.run_polling()


if __name__ == "__main__":
    main()
