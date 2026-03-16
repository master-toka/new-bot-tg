#!/usr/bin/env python3
"""
Скрипт для проверки районов в базе данных
"""

import asyncio
import logging
from sqlalchemy import select
from database import AsyncSessionLocal
from models import District
from config import DISTRICTS

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_districts():
    """
    Проверка районов в базе данных
    """
    async with AsyncSessionLocal() as session:
        try:
            # Получаем все районы из БД
            query = select(District).order_by(District.name)
            result = await session.execute(query)
            districts = result.scalars().all()
            
            print("\n" + "="*50)
            print("🏘 РАЙОНЫ В БАЗЕ ДАННЫХ")
            print("="*50)
            
            if not districts:
                print("❌ В базе данных нет районов!")
            else:
                for i, d in enumerate(districts, 1):
                    status = "✅" if d.is_active else "❌"
                    print(f"{i}. {status} ID: {d.id}, Название: '{d.name}'")
            
            print("="*50)
            print(f"Всего в БД: {len(districts)} районов")
            print(f"В конфиге: {len(DISTRICTS)} районов")
            
            # Проверяем соответствие
            config_names = set(DISTRICTS)
            db_names = {d.name for d in districts}
            
            missing_in_db = config_names - db_names
            extra_in_db = db_names - config_names
            
            if missing_in_db:
                print("\n❌ Отсутствуют в БД:")
                for name in sorted(missing_in_db):
                    print(f"   • {name}")
            
            if extra_in_db:
                print("\n⚠️ Лишние в БД (нет в конфиге):")
                for name in sorted(extra_in_db):
                    print(f"   • {name}")
            
            if not missing_in_db and not extra_in_db:
                print("\n✅ Полное соответствие конфигу!")
            
            print("="*50 + "\n")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке районов: {e}")

async def add_missing_districts():
    """
    Добавление отсутствующих районов
    """
    async with AsyncSessionLocal() as session:
        try:
            # Получаем существующие районы
            query = select(District)
            result = await session.execute(query)
            existing = {d.name for d in result.scalars().all()}
            
            # Добавляем отсутствующие
            added = []
            for district_name in DISTRICTS:
                if district_name not in existing:
                    district = District(name=district_name, is_active=True)
                    session.add(district)
                    added.append(district_name)
            
            if added:
                await session.commit()
                print(f"\n✅ Добавлены районы: {', '.join(added)}")
            else:
                print("\n✅ Все районы уже есть в БД")
                
        except Exception as e:
            logger.error(f"Ошибка при добавлении районов: {e}")
            await session.rollback()

async def main():
    """
    Главная функция
    """
    print("\n🔍 ПРОВЕРКА РАЙОНОВ")
    print("1. Проверить наличие районов")
    print("2. Добавить отсутствующие районы")
    print("3. Выполнить оба действия")
    
    choice = input("\nВыберите действие (1-3): ").strip()
    
    if choice == "1":
        await check_districts()
    elif choice == "2":
        await add_missing_districts()
        await check_districts()
    elif choice == "3":
        await check_districts()
        await add_missing_districts()
        await check_districts()
    else:
        print("❌ Неверный выбор")

if __name__ == "__main__":
    asyncio.run(main())
