
"""Хранение напоминаний о платежах в SQLite."""

import sqlite3
from contextlib import closing

from database import DB_PATH


def init_reminders():
    """Создаёт таблицу напоминаний, если её ещё нет."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                due_at INTEGER NOT NULL,
                note TEXT NOT NULL,
                sent INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.commit()


def add_reminder(user_id, chat_id, due_at, note):
    """Сохраняет новое напоминание и возвращает его ID."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO reminders (
                user_id, chat_id, due_at, note
            )
            VALUES (?, ?, ?, ?)
            """,
            (user_id, chat_id, due_at, note),
        )
        connection.commit()
        return cursor.lastrowid


def get_pending_reminders(user_id):
    """Возвращает ожидающие отправки напоминания пользователя."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT id, due_at, note
            FROM reminders
            WHERE user_id = ? AND sent = 0
            ORDER BY due_at
            LIMIT 20
            """,
            (user_id,),
        ).fetchall()

    return rows


def get_due_reminders(now_timestamp):
    """Возвращает напоминания, время которых наступило."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT id, chat_id, note
            FROM reminders
            WHERE sent = 0 AND due_at <= ?
            ORDER BY due_at
            LIMIT 50
            """,
            (now_timestamp,),
        ).fetchall()

    return rows


def mark_reminder_sent(reminder_id):
    """Помечает отправленное напоминание."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            UPDATE reminders
            SET sent = 1
            WHERE id = ?
            """,
            (reminder_id,),
        )
        connection.commit()


def cancel_reminder(user_id, reminder_id):
    """Удаляет напоминание пользователя, если оно ещё не отправлено."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            DELETE FROM reminders
            WHERE id = ? AND user_id = ? AND sent = 0
            """,
            (reminder_id, user_id),
        )
        connection.commit()
        return cursor.rowcount > 0
