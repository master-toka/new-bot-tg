import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import District
from config import DISTRICTS

logger = logging.getLogger(__name__)

async def init_districts(session: AsyncSession):
    """
    Инициализация районов в базе данных
    """
    try:
        # Проверяем, есть ли уже районы в БД
        result = await session.execute(select(District))
        existing_districts = result.scalars().all()
        
        if existing_districts:
            logger.info(f"Районы уже существуют в БД: {len(existing_districts)} шт.")
            
            # Проверяем, все ли районы из списка есть в БД
            existing_names = [d.name for d in existing_districts]
            missing_districts = [d for d in DISTRICTS if d not in existing_names]
            
            if missing_districts:
                logger.info(f"Добавляем недостающие районы: {missing_districts}")
                for district_name in missing_districts:
                    district = District(name=district_name, is_active=True)
                    session.add(district)
                await session.commit()
                logger.info(f"Добавлено {len(missing_districts)} районов")
            else:
                logger.info("Все районы уже есть в БД")
            
            return
        
        # Если районов нет, создаем все
        logger.info("Создаем районы в БД...")
        for district_name in DISTRICTS:
            district = District(name=district_name, is_active=True)
            session.add(district)
        
        await session.commit()
        logger.info(f"Создано {len(DISTRICTS)} районов в БД")
        
    except Exception as e:
        logger.error(f"Ошибка при инициализации районов: {e}")
        await session.rollback()
        raise

async def check_districts(session: AsyncSession) -> dict:
    """
    Проверка наличия районов в БД
    """
    try:
        result = await session.execute(select(District).order_by(District.name))
        districts = result.scalars().all()
        
        return {
            "count": len(districts),
            "districts": [{"id": d.id, "name": d.name, "is_active": d.is_active} for d in districts],
            "missing": [d for d in DISTRICTS if d not in [dist.name for dist in districts]]
        }
    except Exception as e:
        logger.error(f"Ошибка при проверке районов: {e}")
        return {"count": 0, "districts": [], "missing": DISTRICTS}
