import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from bot.config import settings
from bot.database import create_tables
from bot.handlers import main_router
from bot.middlewares import DatabaseMiddleware, ThrottlingMiddleware
from bot.scheduler import setup_scheduler

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    import os
    os.makedirs("logs", exist_ok=True)

    logger.info("Starting PrizeHub bot...")

    # Create tables
    await create_tables()
    logger.info("Database tables ready.")

    # Redis storage for FSM
    redis = Redis.from_url(settings.redis_url)
    storage = RedisStorage(redis=redis)

    # Bots
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    checker_bot = Bot(token=settings.CHECKER_BOT_TOKEN)

    dp = Dispatcher(storage=storage)

    # Middlewares
    dp.update.middleware(DatabaseMiddleware())
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))

    # Pass checker_bot to handlers via data
    dp["checker_bot"] = checker_bot

    # Routers
    dp.include_router(main_router)

    # Scheduler
    scheduler = setup_scheduler(bot, checker_bot)
    scheduler.start()
    logger.info("Scheduler started.")

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Polling started.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown()
        await bot.session.close()
        await checker_bot.session.close()
        await redis.aclose()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
