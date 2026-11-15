"""Запуск: python -m bot. Проверка файлов без токена: python -m bot --check."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher

from bot.access import access_code
from bot.config import DATA_DIR, token
from bot.content import BEATS, validate
from bot.db import Store
from bot.handlers import router, setup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("kvest")


async def run() -> None:
    validate()
    access_code()
    bot = Bot(token())
    store = Store(DATA_DIR / "bot.sqlite")
    setup(bot, store)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    logger.info("бот запущен, шагов в сценарии: %s", len(BEATS))
    await dispatcher.start_polling(
        bot,
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


def main() -> None:
    if "--check" in sys.argv:
        validate()
        print(f"сценарий в порядке, шагов: {len(BEATS)}")
        return
    asyncio.run(run())


if __name__ == "__main__":
    main()
