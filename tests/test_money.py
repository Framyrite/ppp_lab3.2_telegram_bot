
"""Тесты преобразования и форматирования денежных сумм."""

import unittest

from bot import format_money, parse_amount


class TestMoney(unittest.TestCase):
    """Проверяет финансовые вычисления MoneyTrack."""

    def test_valid_amounts(self):
        """Проверяет преобразование корректных сумм."""
        self.assertEqual(parse_amount("1500"), 150000)
        self.assertEqual(parse_amount("199,90"), 19990)
        self.assertEqual(parse_amount("0.01"), 1)
        self.assertEqual(parse_amount("50000"), 5000000)

    def test_invalid_amounts(self):
        """Проверяет отклонение некорректных сумм."""
        invalid_values = [
            "0",
            "-100",
            "abc",
            "NaN",
            "Infinity",
            "1.234",
            "1000000001",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                self.assertIsNone(parse_amount(value))

    def test_format_money(self):
        """Проверяет отображение сумм в рублях."""
        self.assertEqual(format_money(0), "0 ₽")
        self.assertEqual(format_money(5000000), "50 000 ₽")
        self.assertEqual(format_money(19990), "199,90 ₽")
        self.assertEqual(format_money(-150000), "-1 500 ₽")


if __name__ == "__main__":
    unittest.main()
