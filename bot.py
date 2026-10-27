
"""Telegram-бот MoneyTrack для управления личными финансами."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import BOT_TOKEN


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Приветствует пользователя по команде /start."""
    if update.message is None:
        return

    name = update.effective_user.first_name

    await update.message.reply_text(
        f"Привет, {name}! 👋\n\n"
        "💰 Добро пожаловать в MoneyTrack!\n\n"
        "Я помогу тебе управлять личными финансами.\n\n"
        "Скоро здесь появятся:\n"
        "📈 Учёт доходов\n"
        "📉 Учёт расходов\n"
        "💳 Контроль бюджета\n"
        "📊 Финансовая статистика\n"
        "⏰ Напоминания о платежах\n\n"
        "Введи /help, чтобы посмотреть команды."
    )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Показывает список доступных команд."""
    if update.message is None:
        return

    await update.message.reply_text(
        "💰 MoneyTrack — помощь\n\n"
        "/start — запустить бота\n"
        "/help — показать справку\n\n"
        "Пока работает тестовый режим:\n"
        "отправь сообщение, и я повторю его.\n\n"
        "Финансовые команды добавим следующим этапом."
    )


async def echo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Повторяет текст сообщения пользователя."""
    if update.message is None:
        return

    await update.message.reply_text(update.message.text)


def main() -> None:
    """Запускает Telegram-бота в режиме polling."""
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
