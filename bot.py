import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from database import engine, Base
from handlers import common, customer, installer, admin

logging.basicConfig(level=logging.INFO)

async def on_startup():
    # Создаём таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Можно добавить предустановленные районы, если их нет
    from sqlalchemy import select
    from models import District
    from database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(District))
        if not result.scalars().first():
            districts = ["Центральный", "Северный", "Южный", "Западный", "Восточный"]
            for name in districts:
                session.add(District(name=name))
            await session.commit()

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(common.router)
    dp.include_router(customer.router)
    dp.include_router(installer.router)
    dp.include_router(admin.router)

    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())