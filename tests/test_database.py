
"""Тесты базы данных финансовых операций и бюджетов."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database


class TestDatabase(unittest.TestCase):
    """Проверяет хранение операций и месячных бюджетов."""

    def setUp(self):
        """Создаёт отдельную временную базу для каждого теста."""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        self.db_path = Path(temp_dir.name) / "test.sqlite3"

        db_patch = patch.object(
            database,
            "DB_PATH",
            self.db_path,
        )
        db_patch.start()
        self.addCleanup(db_patch.stop)

        database.init_database()

    def test_add_transactions_and_balance(self):
        """Проверяет расчёт доходов и расходов."""
        database.add_transaction(
            1, "income", 5000000, "Зарплата"
        )
        database.add_transaction(
            1, "expense", 150000, "Продукты"
        )
        database.add_transaction(
            1, "expense", 50000, "Транспорт"
        )

        income, expense = database.get_totals(1)

        self.assertEqual(income, 5000000)
        self.assertEqual(expense, 200000)
        self.assertEqual(income - expense, 4800000)

    def test_users_are_isolated(self):
        """Проверяет независимость данных пользователей."""
        database.add_transaction(
            1, "income", 100000, "Работа"
        )
        database.add_transaction(
            2, "income", 300000, "Работа"
        )

        self.assertEqual(
            database.get_totals(1),
            (100000, 0),
        )
        self.assertEqual(
            database.get_totals(2),
            (300000, 0),
        )

    def test_monthly_statistics(self):
        """Проверяет группировку расходов за месяц."""
        database.add_transaction(
            1, "expense", 10000, "Продукты"
        )
        database.add_transaction(
            1, "expense", 2500, "Продукты"
        )
        database.add_transaction(
            1, "expense", 5000, "Транспорт"
        )
        database.add_transaction(
            1, "expense", 3000, "Подписка"
        )

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                UPDATE transactions
                SET created_at = '2026-10-10 12:00:00'
                """
            )
            connection.execute(
                """
                UPDATE transactions
                SET created_at = '2026-09-10 12:00:00'
                WHERE category = 'Подписка'
                """
            )

        result = database.get_monthly_expense_stats(
            1,
            "2026-10",
        )

        self.assertEqual(
            result,
            [
                ("Продукты", 12500),
                ("Транспорт", 5000),
            ],
        )

    def test_monthly_budget(self):
        """Проверяет установку и изменение бюджета."""
        database.set_monthly_budget(
            1, "2026-10", 3000000
        )

        self.assertEqual(
            database.get_monthly_budget(1, "2026-10"),
            3000000,
        )

        database.set_monthly_budget(
            1, "2026-10", 4000000
        )

        self.assertEqual(
            database.get_monthly_budget(1, "2026-10"),
            4000000,
        )

        self.assertIsNone(
            database.get_monthly_budget(2, "2026-10")
        )


if __name__ == "__main__":
    unittest.main()
