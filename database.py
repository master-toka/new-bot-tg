from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from typing import AsyncGenerator
import logging

from config import DATABASE_URL

# Настройка логирования
logger = logging.getLogger(__name__)

# Создаем асинхронный движок
try:
    engine = create_async_engine(
        DATABASE_URL,
        echo=True,
        future=True
    )
    logger.info(f"Database engine created for {DATABASE_URL}")
except Exception as e:
    logger.error(f"Failed to create database engine: {e}")
    raise

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Базовый класс для моделей
Base = declarative_base()

# Функция для получения сессии БД
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function для получения сессии базы данных
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# Функция для создания таблиц
async def init_db():
    """
    Инициализация базы данных, создание всех таблиц
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise