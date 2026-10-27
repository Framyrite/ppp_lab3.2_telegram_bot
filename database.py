
"""Хранение финансовых операций и бюджетов в SQLite."""

import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).resolve().parent / "moneytrack.sqlite3"


def init_database():
    """Создаёт необходимые таблицы базы данных."""
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

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                user_id INTEGER NOT NULL,
                month TEXT NOT NULL,
                limit_kopecks INTEGER NOT NULL
                    CHECK (limit_kopecks > 0),
                PRIMARY KEY (user_id, month)
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


def get_monthly_expense_stats(user_id, month):
    """Возвращает расходы по категориям за месяц."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        rows = connection.execute(
            """
            SELECT
                category,
                SUM(amount_kopecks) AS total
            FROM transactions
            WHERE user_id = ?
              AND kind = 'expense'
              AND substr(created_at, 1, 7) = ?
            GROUP BY category COLLATE NOCASE
            ORDER BY total DESC, category
            """,
            (user_id, month),
        ).fetchall()

    return rows


def set_monthly_budget(user_id, month, limit_kopecks):
    """Создаёт или обновляет месячный бюджет."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            INSERT INTO budgets (
                user_id,
                month,
                limit_kopecks
            )
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, month)
            DO UPDATE SET
                limit_kopecks = excluded.limit_kopecks
            """,
            (user_id, month, limit_kopecks),
        )

        connection.commit()


def get_monthly_budget(user_id, month):
    """Возвращает установленный бюджет за месяц."""
    with closing(sqlite3.connect(DB_PATH)) as connection:
        row = connection.execute(
            """
            SELECT limit_kopecks
            FROM budgets
            WHERE user_id = ? AND month = ?
            """,
            (user_id, month),
        ).fetchone()

    if row is None:
        return None

    return row[0]
