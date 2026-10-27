
"""Тесты хранения напоминаний о платежах."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import database
import reminders


class TestReminders(unittest.TestCase):
    """Проверяет жизненный цикл напоминаний."""

    def setUp(self):
        """Создаёт отдельную временную базу данных."""
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        db_path = Path(temp_dir.name) / "test.sqlite3"

        for module in (database, reminders):
            db_patch = patch.object(
                module,
                "DB_PATH",
                db_path,
            )
            db_patch.start()
            self.addCleanup(db_patch.stop)

        database.init_database()
        reminders.init_reminders()

    def test_add_reminder(self):
        """Проверяет создание напоминания."""
        reminder_id = reminders.add_reminder(
            user_id=1,
            chat_id=100,
            due_at=2000,
            note="Оплатить интернет",
        )

        result = reminders.get_pending_reminders(1)

        self.assertEqual(
            result,
            [(reminder_id, 2000, "Оплатить интернет")],
        )

    def test_due_reminders(self):
        """Проверяет выбор наступивших напоминаний."""
        reminder_id = reminders.add_reminder(
            1, 100, 2000, "Оплатить аренду"
        )

        self.assertEqual(
            reminders.get_due_reminders(1999),
            [],
        )

        self.assertEqual(
            reminders.get_due_reminders(2000),
            [(reminder_id, 100, "Оплатить аренду")],
        )

    def test_mark_reminder_sent(self):
        """Проверяет завершение отправленного напоминания."""
        reminder_id = reminders.add_reminder(
            1, 100, 2000, "Оплатить связь"
        )

        reminders.mark_reminder_sent(reminder_id)

        self.assertEqual(
            reminders.get_pending_reminders(1),
            [],
        )
        self.assertEqual(
            reminders.get_due_reminders(3000),
            [],
        )

    def test_cancel_reminder(self):
        """Проверяет право удалять только свои напоминания."""
        reminder_id = reminders.add_reminder(
            1, 100, 2000, "Оплатить интернет"
        )

        self.assertFalse(
            reminders.cancel_reminder(2, reminder_id)
        )

        self.assertTrue(
            reminders.cancel_reminder(1, reminder_id)
        )

        self.assertEqual(
            reminders.get_pending_reminders(1),
            [],
        )


if __name__ == "__main__":
    unittest.main()
