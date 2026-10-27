
"""Хранение финансовых операций в SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "moneytrack.sqlite3"


def init_database():
    """Создаёт таблицу финансовых операций."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL
                    CHECK (kind IN ('income', 'expense')),
                amount_kopecks INTEGER NOT NULL
                    CHECK (amount_kopecks > 0),
                category TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        connection.commit()


def add_transaction(user_id, kind, amount_kopecks, category):
    """Сохраняет доход или расход пользователя."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            INSERT INTO transactions
                (user_id, kind, amount_kopecks, category)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, kind, amount_kopecks, category),
        )
        connection.commit()


def get_totals(user_id):
    """Возвращает общую сумму доходов и расходов."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        result = connection.execute(
            """
            SELECT
                COALESCE(SUM(
                    CASE WHEN kind = 'income'
                    THEN amount_kopecks ELSE 0 END
                ), 0),
                COALESCE(SUM(
                    CASE WHEN kind = 'expense'
                    THEN amount_kopecks ELSE 0 END
                ), 0)
            FROM transactions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return result
