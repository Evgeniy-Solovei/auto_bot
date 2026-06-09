import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot_app.handlers import router
from bot_app.middleware import AccessMiddleware


load_dotenv()


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands([BotCommand(command="start", description="Запуск")])


async def main() -> None:
    token = os.getenv("BOT_TOKEN") or os.getenv("TOKEN")
    if not token:
        raise RuntimeError("Set BOT_TOKEN in .env")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
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
