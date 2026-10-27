
"""Telegram-бот MoneyTrack для управления личными финансами."""

import logging
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.error import TelegramError
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
from reminders import (
    add_reminder,
    cancel_reminder,
    get_due_reminders,
    get_pending_reminders,
    init_reminders,
    mark_reminder_sent,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


FINANCIAL_TIPS = [
    "Записывай даже небольшие расходы. "
    "Они могут заметно влиять на бюджет.",

    "Попробуй откладывать часть дохода сразу "
    "после его получения.",

    "Разделяй обязательные расходы и "
    "необязательные покупки.",

    "Перед крупной покупкой сравни предложения "
    "и оцени необходимость покупки.",

    "Проверяй регулярные подписки и отключай "
    "те, которыми не пользуешься.",

    "Создай финансовую подушку для "
    "непредвиденных расходов.",

    "Устанавливай реалистичный месячный бюджет "
    "и регулярно проверяй остаток.",

    "Планируй обязательные платежи заранее, "
    "чтобы избежать просрочек.",
]


def parse_amount(value):
    """Преобразует сумму в рублях в целое число копеек."""
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
    """Форматирует денежную сумму."""
    sign = "-" if kopecks < 0 else ""
    rubles, remainder = divmod(abs(kopecks), 100)
    formatted = f"{rubles:,}".replace(",", " ")

    if remainder:
        formatted += f",{remainder:02d}"

    return f"{sign}{formatted} ₽"


def current_month():
    """Возвращает текущий месяц по UTC."""
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
        "Я помогу управлять личными финансами.\n\n"
        "📈 /income — добавить доход\n"
        "📉 /expense — добавить расход\n"
        "💳 /balance — посмотреть баланс\n"
        "📊 /stats — статистика расходов\n"
        "🎯 /budget — месячный бюджет\n"
        "⏰ /remind — напоминание о платеже\n"
        "📋 /reminders — список напоминаний\n"
        "💡 /tips — финансовый совет\n"
        "❓ /help — все команды"
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает справку по всем командам."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 MoneyTrack — список команд\n\n"
        "/start — приветствие\n"
        "/help — помощь\n\n"
        "📈 ДОХОДЫ:\n"
        "/income 50000 Зарплата\n\n"
        "📉 РАСХОДЫ:\n"
        "/expense 1500 Продукты\n"
        "/expense 199,90 Кофе\n\n"
        "💳 БАЛАНС:\n"
        "/balance\n\n"
        "📊 СТАТИСТИКА:\n"
        "/stats — расходы за месяц\n\n"
        "🎯 БЮДЖЕТ:\n"
        "/budget 30000 — установить лимит\n"
        "/budget — проверить остаток\n\n"
        "⏰ НАПОМИНАНИЯ:\n"
        "/remind 31.10.2026 18:00 Оплатить интернет\n"
        "/reminders — показать напоминания\n"
        "/cancelremind 1 — удалить напоминание № 1\n\n"
        "💡 СОВЕТЫ:\n"
        "/tips — случайный финансовый совет\n\n"
        "Время напоминаний — местное время "
        "компьютера, на котором работает бот."
    )


async def save_operation(update, context, kind):
    """Проверяет и сохраняет доход или расход."""
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
            "❌ Введи положительную сумму "
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
            "❌ Не удалось сохранить операцию."
        )
        return

    operation_name = "Доход" if kind == "income" else "Расход"

    await update.message.reply_text(
        f"✅ {operation_name} добавлен!\n\n"
        f"💰 Сумма: {format_money(amount)}\n"
        f"📁 Категория: {category}"
    )


async def income(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Добавляет доход."""
    await save_operation(update, context, "income")


async def expense(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Добавляет расход."""
    await save_operation(update, context, "expense")


async def balance(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает финансовый баланс."""
    if update.message is None or update.effective_user is None:
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
    """Показывает статистику расходов за текущий месяц."""
    if update.message is None or update.effective_user is None:
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
        f"📊 Расходы за {month}",
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

    await update.message.reply_text("\n".join(lines))


async def budget(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Устанавливает и показывает месячный бюджет."""
    if update.message is None or update.effective_user is None:
        return

    month = current_month()
    user_id = update.effective_user.id

    if len(context.args) > 1:
        await update.message.reply_text(
            "❌ Используй /budget или /budget 30000"
        )
        return

    try:
        if context.args:
            limit = parse_amount(context.args[0])

            if limit is None:
                await update.message.reply_text(
                    "❌ Пример: /budget 30000"
                )
                return

            set_monthly_budget(user_id, month, limit)

        limit = get_monthly_budget(user_id, month)

        if limit is None:
            await update.message.reply_text(
                "🎯 Бюджет ещё не установлен.\n\n"
                "Пример: /budget 30000"
            )
            return

        rows = get_monthly_expense_stats(user_id, month)
        spent = sum(amount for _, amount in rows)

    except sqlite3.Error:
        logger.exception("Ошибка работы с бюджетом")

        await update.message.reply_text(
            "❌ Не удалось обработать бюджет."
        )
        return

    remaining = limit - spent

    if remaining >= 0:
        status = f"✅ Осталось: {format_money(remaining)}"
    else:
        status = (
            f"⚠️ Превышение: {format_money(-remaining)}"
        )

    await update.message.reply_text(
        f"🎯 Бюджет за {month}\n\n"
        f"💳 Лимит: {format_money(limit)}\n"
        f"💸 Потрачено: {format_money(spent)}\n\n"
        f"{status}"
    )


async def remind(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Создаёт напоминание о будущем платеже."""
    if update.message is None or update.effective_user is None:
        return

    if update.effective_chat is None:
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔒 Напоминания доступны только в личном чате."
        )
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "⏰ Формат напоминания:\n\n"
            "/remind ДД.ММ.ГГГГ ЧЧ:ММ Описание\n\n"
            "Пример:\n"
            "/remind 31.10.2026 18:00 Оплатить интернет"
        )
        return

    date_text = " ".join(context.args[:2])
    note = " ".join(context.args[2:]).strip()

    if not note or len(note) > 120:
        await update.message.reply_text(
            "❌ Описание должно содержать "
            "от 1 до 120 символов."
        )
        return

    try:
        # Наивная дата трактуется как местное время Mac.
        due_datetime = datetime.strptime(
            date_text, "%d.%m.%Y %H:%M"
        ).astimezone()

    except ValueError:
        await update.message.reply_text(
            "❌ Неправильная дата.\n"
            "Пример: 31.10.2026 18:00"
        )
        return

    now = datetime.now().astimezone()

    if due_datetime <= now:
        await update.message.reply_text(
            "❌ Выбери дату и время в будущем."
        )
        return

    if due_datetime > now + timedelta(days=365):
        await update.message.reply_text(
            "❌ Напоминание можно создать "
            "не более чем на год вперёд."
        )
        return

    try:
        reminder_id = add_reminder(
            user_id=update.effective_user.id,
            chat_id=update.effective_chat.id,
            due_at=int(due_datetime.timestamp()),
            note=note,
        )

    except sqlite3.Error:
        logger.exception("Ошибка создания напоминания")

        await update.message.reply_text(
            "❌ Не удалось сохранить напоминание."
        )
        return

    await update.message.reply_text(
        "✅ Напоминание создано!\n\n"
        f"🔢 Номер: {reminder_id}\n"
        f"📅 Дата: {due_datetime:%d.%m.%Y}\n"
        f"🕒 Время: {due_datetime:%H:%M}\n"
        f"📝 Задача: {note}"
    )


async def reminders_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Показывает активные напоминания пользователя."""
    if update.message is None or update.effective_user is None:
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔒 Используй эту команду в личном чате."
        )
        return

    try:
        rows = get_pending_reminders(
            update.effective_user.id
        )

    except sqlite3.Error:
        logger.exception("Ошибка получения напоминаний")

        await update.message.reply_text(
            "❌ Не удалось получить напоминания."
        )
        return

    if not rows:
        await update.message.reply_text(
            "📋 Активных напоминаний пока нет."
        )
        return

    lines = ["📋 Твои напоминания:", ""]

    for reminder_id, due_at, note in rows:
        date_text = datetime.fromtimestamp(
            due_at
        ).strftime("%d.%m.%Y %H:%M")

        lines.append(
            f"#{reminder_id} — {date_text}\n"
            f"📝 {note}\n"
        )

    lines.append(
        "Удалить: /cancelremind НОМЕР"
    )

    await update.message.reply_text("\n".join(lines))


async def cancel_reminder_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Удаляет напоминание по номеру."""
    if update.message is None or update.effective_user is None:
        return

    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🔒 Используй эту команду в личном чате."
        )
        return

    if len(context.args) != 1 or not context.args[0].isdigit():
        await update.message.reply_text(
            "❌ Пример: /cancelremind 1"
        )
        return

    try:
        deleted = cancel_reminder(
            update.effective_user.id,
            int(context.args[0]),
        )

    except sqlite3.Error:
        logger.exception("Ошибка удаления напоминания")

        await update.message.reply_text(
            "❌ Не удалось удалить напоминание."
        )
        return

    if deleted:
        await update.message.reply_text(
            "✅ Напоминание удалено."
        )
    else:
        await update.message.reply_text(
            "❌ Такое активное напоминание не найдено."
        )


async def tips(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Отправляет случайный совет по личным финансам."""
    if update.message is None:
        return

    advice = random.choice(FINANCIAL_TIPS)

    await update.message.reply_text(
        "💡 Финансовый совет MoneyTrack\n\n"
        f"{advice}"
    )


async def send_due_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Проверяет сроки платежей и отправляет напоминания."""
    try:
        rows = get_due_reminders(int(time.time()))

    except sqlite3.Error:
        logger.exception("Ошибка проверки напоминаний")
        return

    for reminder_id, chat_id, note in rows:
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⏰ MoneyTrack — напоминание!\n\n"
                    f"💳 {note}\n\n"
                    "Проверь, не пора ли оплатить счёт."
                ),
            )

        except TelegramError:
            logger.exception(
                "Не удалось отправить напоминание %s",
                reminder_id,
            )
            continue

        try:
            mark_reminder_sent(reminder_id)

        except sqlite3.Error:
            logger.exception(
                "Не удалось отметить напоминание %s",
                reminder_id,
            )


async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    """Подсказывает пользователю доступные команды."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 Я финансовый помощник MoneyTrack!\n\n"
        "Используй /help для просмотра команд."
    )


def main():
    """Инициализирует хранилища и запускает Telegram-бота."""
    init_database()
    init_reminders()

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
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("budget", budget))
    application.add_handler(CommandHandler("remind", remind))

    application.add_handler(
        CommandHandler("reminders", reminders_command)
    )

    application.add_handler(
        CommandHandler(
            "cancelremind",
            cancel_reminder_command,
        )
    )

    application.add_handler(CommandHandler("tips", tips))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            echo,
        )
    )

    if application.job_queue is None:
        raise RuntimeError(
            "Установи python-telegram-bot[job-queue]"
        )

    application.job_queue.run_repeating(
        callback=send_due_reminders,
        interval=15,
        first=5,
    )

    logger.info("MoneyTrack запущен")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
