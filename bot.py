
"""Telegram-бот MoneyTrack для учёта личных финансов."""

import logging
import sqlite3
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN
from database import (
    add_transaction,
    get_totals,
    init_database,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def parse_amount(value):
    """Преобразует сумму в целое количество копеек."""
    try:
        amount = Decimal(value.replace(",", "."))

        if not amount.is_finite():
            return None

        if amount <= 0 or amount > Decimal("1000000000"):
            return None

        kopecks = amount * 100

        if kopecks != kopecks.to_integral_value():
            return None

        return int(kopecks)
    except InvalidOperation:
        return None


def format_money(kopecks):
    """Форматирует сумму в рублях."""
    sign = "-" if kopecks < 0 else ""
    rubles, remainder = divmod(abs(kopecks), 100)

    formatted = f"{rubles:,}".replace(",", " ")

    if remainder:
        formatted += f",{remainder:02d}"

    return f"{sign}{formatted} ₽"


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Приветствует пользователя."""
    if update.message is None:
        return

    user = update.effective_user

    await update.message.reply_text(
        f"Привет, {user.first_name}! 👋\n\n"
        "💰 Добро пожаловать в MoneyTrack!\n\n"
        "Я помогу вести учёт личных финансов.\n\n"
        "📈 /income — добавить доход\n"
        "📉 /expense — добавить расход\n"
        "💳 /balance — посмотреть баланс\n"
        "❓ /help — справка"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает справку по командам."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 MoneyTrack — список команд\n\n"
        "/start — запустить бота\n"
        "/help — справка\n\n"
        "📈 ДОХОДЫ:\n"
        "/income 50000 Зарплата\n\n"
        "📉 РАСХОДЫ:\n"
        "/expense 1500 Продукты\n\n"
        "💳 БАЛАНС:\n"
        "/balance\n\n"
        "Сумму можно вводить с копейками:\n"
        "/expense 199,90 Кофе"
    )


async def save_operation(update, context, kind):
    """Проверяет и сохраняет финансовую операцию."""
    if update.message is None:
        return

    if update.effective_user is None:
        return

    if len(context.args) < 2:
        command = "/income" if kind == "income" else "/expense"

        await update.message.reply_text(
            "❌ Неправильный формат.\n\n"
            f"Пример: {command} 1500 Продукты"
        )
        return

    amount = parse_amount(context.args[0])

    if amount is None:
        await update.message.reply_text(
            "❌ Укажи положительную сумму "
            "с точностью до копеек."
        )
        return

    category = " ".join(context.args[1:]).strip()

    if not category or len(category) > 80:
        await update.message.reply_text(
            "❌ Укажи категорию длиной до 80 символов."
        )
        return

    try:
        add_transaction(
            user_id=update.effective_user.id,
            kind=kind,
            amount_kopecks=amount,
            category=category,
        )
    except sqlite3.Error:
        logger.exception("Ошибка сохранения операции")
        await update.message.reply_text(
            "Не удалось сохранить операцию."
        )
        return

    operation_name = (
        "Доход" if kind == "income" else "Расход"
    )

    await update.message.reply_text(
        f"✅ {operation_name} добавлен!\n\n"
        f"💰 Сумма: {format_money(amount)}\n"
        f"📁 Категория: {category}"
    )


async def income(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Добавляет доход пользователя."""
    await save_operation(update, context, "income")


async def expense(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Добавляет расход пользователя."""
    await save_operation(update, context, "expense")


async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает финансовый баланс пользователя."""
    if update.message is None:
        return

    if update.effective_user is None:
        return

    try:
        total_income, total_expense = get_totals(
            update.effective_user.id
        )
    except sqlite3.Error:
        logger.exception("Ошибка получения баланса")
        await update.message.reply_text(
            "Не удалось получить баланс."
        )
        return

    current_balance = total_income - total_expense

    await update.message.reply_text(
        "💳 MoneyTrack — твой баланс\n\n"
        f"📈 Доходы: {format_money(total_income)}\n"
        f"📉 Расходы: {format_money(total_expense)}\n\n"
        f"💰 Баланс: {format_money(current_balance)}"
    )


async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Обрабатывает обычные сообщения."""
    if update.message is None:
        return

    await update.message.reply_text(
        "Я финансовый помощник MoneyTrack! 💰\n\n"
        "Используй /help для просмотра команд."
    )


def main():
    """Создаёт базу данных и запускает бота."""
    init_database()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("income", income))
    application.add_handler(CommandHandler("expense", expense))
    application.add_handler(CommandHandler("balance", balance))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            echo,
        )
    )

    logger.info("MoneyTrack запущен")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
