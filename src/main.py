import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties

from src.config import load_config
from src.handlers import router
from src.ai_processor import AIProcessor


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = load_config()
    if not config.bot.token:
        raise SystemExit("BOT_TOKEN не задан в .env")

    bot = Bot(
        token=config.bot.token,
        default=DefaultBotProperties(parse_mode="HTML"),
    )
    dp = Dispatcher()

    ai = AIProcessor(api_key=config.bot.bothub_api_key)
    dp["ai"] = ai

    dp.include_router(router)

    logging.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await ai.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
