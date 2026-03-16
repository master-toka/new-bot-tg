#!/usr/bin/env python3
"""
Инициализация районов в базе данных
"""

import asyncio
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import District
from config import DISTRICTS

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def init_districts():
    """
    Инициализация районов в базе данных при запуске
    """
    async with AsyncSessionLocal() as session:
        try:
            # Проверяем, есть ли уже районы в БД
            query = select(District)
            result = await session.execute(query)
            existing_districts = result.scalars().all()
            
            existing_names = [d.name for d in existing_districts]
            
            # Добавляем новые районы
            added_count = 0
            for district_name in DISTRICTS:
                if district_name not in existing_names:
                    district = District(name=district_name, is_active=True)
                    session.add(district)
                    added_count += 1
                    logger.info(f"Добавлен район: {district_name}")
            
            if added_count > 0:
                await session.commit()
                logger.info(f"✅ Районы инициализированы. Добавлено: {added_count}, Всего: {len(DISTRICTS)}")
            else:
                logger.info(f"✅ Районы уже существуют в БД. Всего: {len(existing_districts)}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при инициализации районов: {e}")
            await session.rollback()
            raise

async def main():
    """
    Главная функция для запуска инициализации
    """
    logger.info("Запуск инициализации районов...")
    await init_districts()
    logger.info("Инициализация завершена")

if __name__ == "__main__":
    asyncio.run(main())
