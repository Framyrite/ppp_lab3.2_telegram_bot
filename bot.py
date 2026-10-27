
"""Telegram-бот MoneyTrack для управления личными финансами."""

import logging
import sqlite3
from datetime import datetime, timezone
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
    get_monthly_budget,
    get_monthly_expense_stats,
    get_totals,
    init_database,
    set_monthly_budget,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def parse_amount(value):
    """Преобразует рубли в целое количество копеек."""
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
    """Форматирует денежную сумму в рублях."""
    sign = "-" if kopecks < 0 else ""

    rubles, remainder = divmod(abs(kopecks), 100)

    formatted = f"{rubles:,}".replace(",", " ")

    if remainder:
        formatted += f",{remainder:02d}"

    return f"{sign}{formatted} ₽"


def current_month():
    """Возвращает текущий месяц в формате YYYY-MM."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Приветствует пользователя."""
    if update.message is None:
        return

    if update.effective_user is None:
        return

    name = update.effective_user.first_name

    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        "💰 Добро пожаловать в MoneyTrack!\n\n"
        "Я помогу тебе управлять личными финансами.\n\n"
        "📈 /income — добавить доход\n"
        "📉 /expense — добавить расход\n"
        "💳 /balance — посмотреть баланс\n"
        "📊 /stats — статистика расходов\n"
        "🎯 /budget — управление бюджетом\n"
        "❓ /help — список команд"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает справку по командам бота."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 MoneyTrack — список команд\n\n"
        "🚀 ОСНОВНЫЕ:\n"
        "/start — запустить бота\n"
        "/help — показать справку\n\n"
        "📈 ДОХОДЫ:\n"
        "/income 50000 Зарплата\n\n"
        "📉 РАСХОДЫ:\n"
        "/expense 1500 Продукты\n"
        "/expense 199,90 Кофе\n\n"
        "💳 БАЛАНС:\n"
        "/balance\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats — расходы по категориям за месяц\n\n"
        "🎯 БЮДЖЕТ:\n"
        "/budget 30000 — установить лимит\n"
        "/budget — проверить остаток\n\n"
        "Все операции сохраняются автоматически."
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
            "❌ Неправильный формат команды.\n\n"
            f"Пример: {command} 1500 Продукты"
        )
        return

    amount = parse_amount(context.args[0])

    if amount is None:
        await update.message.reply_text(
            "❌ Введи положительную сумму "
            "с точностью до копеек.\n\n"
            "Пример: 1500 или 199,90"
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
            "❌ Не удалось сохранить операцию."
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
    """Показывает текущий баланс пользователя."""
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
            "❌ Не удалось получить баланс."
        )
        return

    current_balance = total_income - total_expense

    await update.message.reply_text(
        "💳 MoneyTrack — твой баланс\n\n"
        f"📈 Доходы: {format_money(total_income)}\n"
        f"📉 Расходы: {format_money(total_expense)}\n\n"
        f"💰 Баланс: {format_money(current_balance)}"
    )


async def stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает расходы по категориям за текущий месяц."""
    if update.message is None:
        return

    if update.effective_user is None:
        return

    month = current_month()

    try:
        rows = get_monthly_expense_stats(
            update.effective_user.id,
            month,
        )

    except sqlite3.Error:
        logger.exception("Ошибка получения статистики")

        await update.message.reply_text(
            "❌ Не удалось получить статистику."
        )
        return

    if not rows:
        await update.message.reply_text(
            "📊 В этом месяце расходов пока нет."
        )
        return

    total = sum(amount for _, amount in rows)

    lines = [
        f"📊 Статистика расходов за {month}",
        "",
    ]

    for category, amount in rows[:10]:
        lines.append(
            f"📁 {category}: {format_money(amount)}"
        )

    if len(rows) > 10:
        lines.append(
            f"И ещё категорий: {len(rows) - 10}"
        )

    lines.extend([
        "",
        f"💸 Всего потрачено: {format_money(total)}",
    ])

    await update.message.reply_text(
        "\n".join(lines)
    )


async def budget(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Устанавливает и показывает бюджет за текущий месяц."""
    if update.message is None:
        return

    if update.effective_user is None:
        return

    month = current_month()
    user_id = update.effective_user.id

    if len(context.args) > 1:
        await update.message.reply_text(
            "❌ Неправильный формат.\n\n"
            "Используй /budget или /budget 30000"
        )
        return

    try:
        if context.args:
            limit = parse_amount(context.args[0])

            if limit is None:
                await update.message.reply_text(
                    "❌ Укажи положительную сумму.\n\n"
                    "Пример: /budget 30000"
                )
                return

            set_monthly_budget(
                user_id,
                month,
                limit,
            )

        limit = get_monthly_budget(
            user_id,
            month,
        )

        if limit is None:
            await update.message.reply_text(
                "🎯 Бюджет ещё не установлен.\n\n"
                "Установи его командой:\n"
                "/budget 30000"
            )
            return

        rows = get_monthly_expense_stats(
            user_id,
            month,
        )

        spent = sum(
            amount for _, amount in rows
        )

    except sqlite3.Error:
        logger.exception("Ошибка работы с бюджетом")

        await update.message.reply_text(
            "❌ Не удалось обработать бюджет."
        )
        return

    remaining = limit - spent

    if remaining >= 0:
        status = (
            f"✅ Осталось: {format_money(remaining)}"
        )
    else:
        status = (
            f"⚠️ Бюджет превышен на "
            f"{format_money(-remaining)}"
        )

    await update.message.reply_text(
        f"🎯 Бюджет за {month}\n\n"
        f"💳 Лимит: {format_money(limit)}\n"
        f"💸 Потрачено: {format_money(spent)}\n\n"
        f"{status}"
    )


async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Отвечает на обычные текстовые сообщения."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 Я финансовый помощник MoneyTrack!\n\n"
        "Используй /help, чтобы узнать мои команды."
    )


def main():
    """Создаёт базу данных и запускает Telegram-бота."""
    init_database()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    application.add_handler(
        CommandHandler("income", income)
    )

    application.add_handler(
        CommandHandler("expense", expense)
    )

    application.add_handler(
        CommandHandler("balance", balance)
    )

    application.add_handler(
        CommandHandler("stats", stats)
    )

    application.add_handler(
        CommandHandler("budget", budget)
    )

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
