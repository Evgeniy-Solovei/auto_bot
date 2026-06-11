import asyncio
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot_app.handlers import router
from bot_app.middleware import AccessMiddleware


load_dotenv()


def setup_logging() -> None:
    log_dir = Path(os.getenv("LOG_DIR", "logs"))
    log_dir.mkdir(exist_ok=True)
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        handlers=[console_handler, file_handler],
        force=True,
    )


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([BotCommand(command="start", description="Запуск")])


async def main() -> None:
    token = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in .env")

    setup_logging()
    logging.getLogger(__name__).info("Starting Telegram bot")
    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    access_middleware = AccessMiddleware()
    dp.message.middleware(access_middleware)
    dp.callback_query.middleware(access_middleware)
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
