from __future__ import annotations
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from .handlers import router
from .config import Settings
from .logging_conf import setup_logging
from dotenv import load_dotenv
from aiogram.client.default import DefaultBotProperties
load_dotenv()

def run():
    load_dotenv()
    setup_logging()
    settings = Settings.from_env()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    bot = Bot(token=settings.bot_token,default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    async def _main():
        await bot.set_my_commands([
            types.BotCommand(command="start", description="Начать работу"),
        ])
        await dp.start_polling(bot)

    asyncio.run(_main())
